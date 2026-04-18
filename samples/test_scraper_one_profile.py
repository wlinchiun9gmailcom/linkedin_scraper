import asyncio
from pathlib import Path

from linkedin_scraper import PersistentBrowserManager
from linkedin_scraper.core.exceptions import RateLimitError


PROFILE_URL = "https://www.linkedin.com/in/caprianna-keeler/"
POST_LIMIT = 5


async def is_original_post(card) -> bool:
    """
    Return True only for original authored posts.
    Skip reposts/shares/reposts-with-commentary by detecting nested shared content.
    """

    # These nested structures commonly appear inside repost/share cards.
    repost_indicators = [
        ".feed-shared-update-v2__reshared-content",
        ".feed-shared-update-v2__shared-update",
        ".feed-shared-update-v2__commentary + div .update-components-actor",
        ".update-components-header__text-view + .feed-shared-update-v2__description-wrapper + .feed-shared-update-v2__reshared-content",
        ".feed-shared-update-v2__content .feed-shared-update-v2__content",
    ]

    for selector in repost_indicators:
        try:
            found = await card.locator(selector).count()
            if found > 0:
                return False
        except Exception:
            pass

    # Text-level fallback from the visible header
    try:
        card_text = (await card.inner_text()).lower()
        header_clues = [
            "reposted this",
            "reposted",
            "shared this",
            "shared a post",
        ]
        if any(clue in card_text for clue in header_clues):
            return False
    except Exception:
        pass

    return True


async def extract_post_text(card) -> str:
    """
    Try a few likely selectors for the user's own post text.
    """
    text_selectors = [
        ".feed-shared-update-v2__description",
        ".update-components-text",
        ".update-components-update-v2__commentary",
        ".feed-shared-inline-show-more-text",
        "span.break-words",
    ]

    for selector in text_selectors:
        try:
            locator = card.locator(selector).first
            if await locator.count() > 0:
                text = (await locator.inner_text()).strip()
                if text:
                    return text
        except Exception:
            pass

    try:
        return (await card.inner_text()).strip()
    except Exception:
        return ""


async def main():
    project_root = Path(__file__).resolve().parent.parent
    profile_dir = project_root / "playwright_linkedin_profile"

    activity_url = PROFILE_URL.rstrip("/") + "/recent-activity/all/"

    async with PersistentBrowserManager(
        user_data_dir=str(profile_dir),
        headless=False,
    ) as browser:
        try:
            await browser.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            print("Current URL before scrape:", browser.page.url)
            print("Current title before scrape:", await browser.page.title())
            print("\nIf LinkedIn shows any checkpoint/CAPTCHA, clear it manually in the browser.")

            await browser.goto(activity_url, wait_until="domcontentloaded")
            print("Activity URL:", browser.page.url)
            print("Activity page title:", await browser.page.title())

            await browser.page.wait_for_timeout(3000)

            # Try to load more activity cards by scrolling a bit
            for _ in range(5):
                await browser.page.mouse.wheel(0, 3000)
                await browser.page.wait_for_timeout(1500)

            card_selectors = [
                ".feed-shared-update-v2",
                '[data-urn*="activity:"]',
            ]

            cards = None
            for selector in card_selectors:
                loc = browser.page.locator(selector)
                count = await loc.count()
                if count > 0:
                    cards = loc
                    print(f"Using card selector: {selector} | found {count} cards")
                    break

            if cards is None:
                print("No activity cards found.")
                return

            kept_posts = []
            total_cards = await cards.count()

            for i in range(total_cards):
                card = cards.nth(i)

                try:
                    is_original = await is_original_post(card)
                    text = await extract_post_text(card)
                    preview = text[:160].replace("\n", " ")

                    print("\n" + "=" * 100)
                    print(f"CARD {i+1}")
                    print("=" * 100)
                    print("Preview:", preview if preview else "[No text found]")
                    print("Original post?:", is_original)

                    if not is_original:
                        print("[SKIPPED: detected repost/share card]")
                        continue

                    if not text:
                        print("[SKIPPED: no text]")
                        continue

                    kept_posts.append(text)
                    print("[KEPT]")

                    if len(kept_posts) >= POST_LIMIT:
                        break

                except Exception as e:
                    print(f"Error processing card {i+1}: {e}")

            print(f"\nTotal kept original posts: {len(kept_posts)}\n")

            for idx, text in enumerate(kept_posts, 1):
                print("=" * 100)
                print(f"POST {idx}")
                print("=" * 100)
                print(text)
                print()

        except RateLimitError as e:
            print(f"Rate-limit / CAPTCHA page detected: {e}")
        except Exception as e:
            print(f"Error scraping {PROFILE_URL}: {e}")


if __name__ == "__main__":
    asyncio.run(main())