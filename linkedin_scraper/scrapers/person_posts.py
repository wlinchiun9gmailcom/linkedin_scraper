import logging
import re
from typing import List, Optional

from playwright.async_api import Page

from ..callbacks import ProgressCallback, SilentCallback
from ..models.post import Post
from .base import BaseScraper

logger = logging.getLogger(__name__)


class PersonPostsScraper(BaseScraper):
    def __init__(self, page: Page, callback: Optional[ProgressCallback] = None):
        super().__init__(page, callback or SilentCallback())

    async def scrape(self, profile_url: str, limit: int = 10) -> List[Post]:
        logger.info(f"Starting person posts scraping: {profile_url}")
        await self.callback.on_start("person_posts", profile_url)

        await self.ensure_logged_in()

        posts_url = self._build_activity_url(profile_url)

        try:
            await self.navigate_and_wait(posts_url)
        except Exception as e:
            logger.warning(f"Navigation/checkpoint warning on activity page: {e}")
            raise

        await self.callback.on_progress("Navigated to activity page", 10)

        await self.check_rate_limit()
        await self._wait_for_posts_to_load()
        await self.callback.on_progress("Activity loaded", 20)

        profile_name = await self._extract_profile_name()
        posts = await self._scrape_posts(limit=limit, profile_name=profile_name)

        await self.callback.on_progress(f"Scraped {len(posts)} posts", 100)
        await self.callback.on_complete("person_posts", posts)
        logger.info(f"Successfully scraped {len(posts)} person posts")
        return posts

    def _build_activity_url(self, profile_url: str) -> str:
        profile_url = profile_url.rstrip("/")
        if "/recent-activity/" in profile_url:
            return profile_url
        return f"{profile_url}/recent-activity/all/"

    async def _extract_profile_name(self) -> Optional[str]:
        selectors = [
            "h1",
            ".text-heading-xlarge",
            ".pv-text-details__left-panel h1",
        ]

        for selector in selectors:
            try:
                loc = self.page.locator(selector).first
                if await loc.count() > 0:
                    text = (await loc.inner_text()).strip()
                    if text:
                        return text
            except Exception:
                pass

        return None

    async def _wait_for_posts_to_load(self, timeout: int = 30000) -> None:
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
        except Exception as e:
            logger.debug(f"DOM load timeout: {e}")
            await self.page.wait_for_timeout(3000)

        for attempt in range(3):
            await self._trigger_lazy_load()
            has_posts = await self.page.evaluate(
                """() => document.body.innerHTML.includes('urn:li:activity:')"""
            )
            if has_posts:
                logger.debug(f"Posts found after attempt {attempt + 1}")
                return

            await self.page.wait_for_timeout(1500)

        logger.warning("Person activity posts may not have loaded fully")

    async def _trigger_lazy_load(self) -> None:
        await self.page.evaluate(
            """() => {
                const maxY = Math.max(
                    document.body.scrollHeight,
                    document.documentElement.scrollHeight
                );
                window.scrollTo(0, Math.min(800, maxY));
            }"""
        )
        await self.page.wait_for_timeout(1200)

    async def _expand_all_posts(self) -> None:
        """
        Expand truncated post text before extraction.
        Uses Playwright-level clicks so LinkedIn has time to update the DOM.
        """
        selectors = [
            "button",
            "span[role='button']",
        ]

        for _ in range(3):
            clicked_any = False

            for selector in selectors:
                elements = await self.page.locator(selector).all()

                for el in elements:
                    try:
                        text = (await el.inner_text()).strip().lower()
                    except Exception:
                        continue

                    try:
                        aria = ((await el.get_attribute("aria-label")) or "").strip().lower()
                    except Exception:
                        aria = ""

                    is_more = (
                        text in {"…more", "...more", "more"} or
                        "see more" in text or
                        "see more" in aria
                    )

                    if not is_more:
                        continue

                    try:
                        await el.scroll_into_view_if_needed(timeout=2000)
                    except Exception:
                        pass

                    try:
                        await el.click(timeout=2000)
                        clicked_any = True
                        await self.page.wait_for_timeout(300)
                    except Exception:
                        pass

            if not clicked_any:
                break

            await self.page.wait_for_timeout(1000)

    async def _scrape_posts(self, limit: int, profile_name: Optional[str]) -> List[Post]:
        posts: List[Post] = []
        scroll_count = 0
        max_scrolls = max(4, (limit // 3) + 2)

        while len(posts) < limit and scroll_count < max_scrolls:
            await self.page.wait_for_timeout(1200)
            await self._expand_all_posts()
            await self.page.wait_for_timeout(800)

            new_posts = await self._extract_posts_from_page(profile_name=profile_name)

            for post in new_posts:
                if post.urn and not any(p.urn == post.urn for p in posts):
                    posts.append(post)
                    if len(posts) >= limit:
                        break

            if len(posts) < limit:
                await self._scroll_for_more_posts()
                scroll_count += 1

        return posts[:limit]

    async def _extract_posts_from_page(self, profile_name: Optional[str]) -> List[Post]:
        posts_data = await self.page.evaluate(
            """(profileName) => {
                const results = [];
                const cards = Array.from(
                    document.querySelectorAll('[data-urn^="urn:li:activity:"]')
                );
                const seen = new Set();

                const getBestText = (el) => {
                    const textSelectors = [
                        '.feed-shared-update-v2__description',
                        '.update-components-text',
                        '.feed-shared-text',
                        '[data-test-id="main-feed-activity-card__commentary"]',
                        '.break-words.whitespace-pre-wrap'
                    ];

                    let best = '';
                    for (const sel of textSelectors) {
                        const nodes = Array.from(el.querySelectorAll(sel));
                        for (const node of nodes) {
                            const t = (node.innerText || node.textContent || '').trim();
                            if (t.length > best.length) {
                                best = t;
                            }
                        }
                    }

                    return best.replace(/\\n\\s*…more\\s*$/i, '').trim();
                };

                const getCountText = (el, selectors) => {
                    for (const sel of selectors) {
                        const nodes = Array.from(el.querySelectorAll(sel));
                        for (const node of nodes) {
                            const txt = (
                                node.getAttribute('aria-label') ||
                                node.innerText ||
                                node.textContent ||
                                ''
                            ).trim();
                            if (txt) return txt;
                        }
                    }
                    return '';
                };

                for (const el of cards) {
                    const urn = el.getAttribute('data-urn');
                    if (!urn || seen.has(urn)) continue;
                    seen.add(urn);

                    let actor = '';
                    const actorSelectors = [
                        '.update-components-actor__title span[dir="ltr"]',
                        '.feed-shared-actor__name',
                        '[class*="actor__title"]'
                    ];

                    for (const sel of actorSelectors) {
                        const node = el.querySelector(sel);
                        const t = node?.innerText?.trim();
                        if (t) {
                            actor = t.split('\\n')[0].trim();
                            break;
                        }
                    }

                    const wrapperText = (el.innerText || '').toLowerCase();

                    if (
                        wrapperText.includes(' liked this') ||
                        wrapperText.includes('commented on') ||
                        wrapperText.includes('reposted this') ||
                        wrapperText.includes('shared this')
                    ) {
                        continue;
                    }

                    if (profileName && actor) {
                        const normalizedActor = actor.toLowerCase();
                        const normalizedProfile = profileName.toLowerCase();

                        if (
                            !normalizedActor.includes(normalizedProfile) &&
                            !normalizedProfile.includes(normalizedActor)
                        ) {
                            continue;
                        }
                    }

                    const text = getBestText(el);
                    if (!text || text.length < 10) {
                        continue;
                    }

                    const timeNode = el.querySelector(
                        '[class*="actor__sub-description"], [class*="update-components-actor__sub-description"]'
                    );
                    const timeText = timeNode?.innerText?.trim() || '';

                    const reactionsText = getCountText(el, [
                        '[aria-label*="reaction"]',
                        '[aria-label*="reactions"]',
                        '[class*="social-details-social-counts__reactions"]',
                        '[class*="social-details-social-counts"]'
                    ]);

                    const commentsText = getCountText(el, [
                        'button[aria-label*="comment"]',
                        '[aria-label*="comments"]'
                    ]);

                    const repostsText = getCountText(el, [
                        'button[aria-label*="repost"]',
                        '[aria-label*="reposts"]'
                    ]);

                    const images = [];
                    el.querySelectorAll('img[src]').forEach((img) => {
                        const src = img.getAttribute('src') || '';
                        if (
                            src &&
                            !src.includes('profile') &&
                            !src.includes('logo') &&
                            !images.includes(src)
                        ) {
                            images.push(src);
                        }
                    });

                    results.push({
                        urn,
                        actor,
                        text: text.slice(0, 20000),
                        timeText,
                        reactions: reactionsText,
                        comments: commentsText,
                        reposts: repostsText,
                        images
                    });
                }

                return results;
            }""",
            profile_name,
        )

        result: List[Post] = []

        for data in posts_data:
            activity_id = data["urn"].replace("urn:li:activity:", "")
            post = Post(
                linkedin_url=f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/",
                urn=data["urn"],
                text=data.get("text"),
                posted_date=self._extract_time_from_text(data.get("timeText", "")),
                reactions_count=self._parse_count(data.get("reactions", "")),
                comments_count=self._parse_count(data.get("comments", "")),
                reposts_count=self._parse_count(data.get("reposts", "")),
                image_urls=data.get("images", []),
            )
            result.append(post)

        return result

    def _extract_time_from_text(self, text: str) -> Optional[str]:
        if not text:
            return None

        match = re.search(
            r"(\\d+[smhdwmy]|\\d+\\s*(?:second|minute|hour|day|week|month|year)s?\\s*ago)",
            text,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()

        parts = text.split("•")
        if parts:
            return parts[0].strip()

        return None

    def _parse_count(self, text: str) -> Optional[int]:
        if not text:
            return None

        try:
            numbers = re.findall(r"[\\d,]+", text.replace(",", ""))
            if numbers:
                return int(numbers[0])
        except Exception:
            pass

        return None

    async def _scroll_for_more_posts(self) -> None:
        try:
            await self.page.keyboard.press("End")
            await self.page.wait_for_timeout(1500)
        except Exception as e:
            logger.debug(f"Error scrolling: {e}")