import asyncio
from pathlib import Path

import pandas as pd

from linkedin_scraper import PersistentBrowserManager
from linkedin_scraper.core.exceptions import RateLimitError


EXCEL_PATH = r"C:\2025-2026 Berkeley\Spring\BAIR\1 - Cross Platform Project\Linkedin Scraping\openreview_verified_conference_authors_2021_2025_debug_final_with_twitter (2).xlsx"
OUTPUT_PATH = r"C:\2025-2026 Berkeley\Spring\BAIR\1 - Cross Platform Project\Linkedin Scraping\openreview_verified_conference_authors_2021_2025_debug_final_with_twitter (2).xlsx"

LINKEDIN_URL_COLUMN = "LinkedIn URL"
OUTPUT_COLUMN = "LinkedIn Text"

POST_LIMIT = 5

# inclusive row bounds, 0-indexed
START_ROW = 0
END_ROW = 1000


async def is_original_post(card) -> bool:
    """
    Return True only for original authored posts.
    Skip reposts/shares/reposts-with-commentary by detecting nested shared content.
    """
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


async def get_original_posts(browser, profile_url: str, post_limit: int = 5):
    """
    Scrape up to `post_limit` original posts from one LinkedIn profile.
    """
    activity_url = profile_url.rstrip("/") + "/recent-activity/all/"
    kept_posts = []

    try:
        await browser.goto(activity_url, wait_until="domcontentloaded")
        print("Activity URL:", browser.page.url)
        print("Activity page title:", await browser.page.title())

        await browser.page.wait_for_timeout(3000)

        # Scroll a few times to load more cards
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
            return []

        total_cards = await cards.count()

        for i in range(total_cards):
            card = cards.nth(i)

            try:
                is_original = await is_original_post(card)
                text = await extract_post_text(card)
                preview = text[:160].replace("\n", " ")

                print("\n" + "=" * 100)
                print(f"CARD {i + 1}")
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

                if len(kept_posts) >= post_limit:
                    break

            except Exception as e:
                print(f"Error processing card {i + 1}: {e}")

        return kept_posts

    except Exception as e:
        print(f"Error scraping profile {profile_url}: {e}")
        return []


async def main():
    excel_path = Path(EXCEL_PATH)
    output_path = Path(OUTPUT_PATH)

    df = pd.read_excel(excel_path)

    if LINKEDIN_URL_COLUMN not in df.columns:
        raise ValueError(f'Column "{LINKEDIN_URL_COLUMN}" not found in Excel file.')

    if OUTPUT_COLUMN not in df.columns:
        df[OUTPUT_COLUMN] = ""

    total_rows = len(df)

    start_row = START_ROW if START_ROW is not None else 0
    end_row = END_ROW if END_ROW is not None else total_rows - 1

    if start_row < 0 or end_row < 0:
        raise ValueError("START_ROW and END_ROW must be >= 0.")

    if start_row >= total_rows:
        raise ValueError(f"START_ROW {start_row} is out of range for file with {total_rows} rows.")

    if end_row >= total_rows:
        end_row = total_rows - 1

    if end_row < start_row:
        raise ValueError("END_ROW must be greater than or equal to START_ROW.")

    project_root = Path(__file__).resolve().parent.parent
    profile_dir = project_root / "playwright_linkedin_profile"

    async with PersistentBrowserManager(
        user_data_dir=str(profile_dir),
        headless=False,
    ) as browser:
        await browser.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        print("Current URL before scrape:", browser.page.url)
        print("Current title before scrape:", await browser.page.title())
        print("\nIf LinkedIn shows any checkpoint/CAPTCHA, clear it manually in the browser.")

        for idx in range(start_row, end_row + 1):
            raw_url = df.at[idx, LINKEDIN_URL_COLUMN]

            if pd.isna(raw_url):
                print(f"Row {idx}: blank LinkedIn URL, skipping")
                continue

            profile_url = str(raw_url).strip()
            if not profile_url:
                print(f"Row {idx}: blank LinkedIn URL, skipping")
                continue

            print("\n" + "#" * 120)
            print(f"ROW {idx}: scraping {profile_url}")
            print("#" * 120)

            try:
                posts = await get_original_posts(browser, profile_url, POST_LIMIT)

                separator = "\n\n" + ("-" * 100) + "\n\n"
                df.at[idx, OUTPUT_COLUMN] = separator.join(posts) if posts else ""

                print(f"Row {idx}: saved {len(posts)} original posts")

            except RateLimitError as e:
                print(f"Row {idx}: rate-limit / CAPTCHA page detected: {e}")
                df.at[idx, OUTPUT_COLUMN] = ""
            except Exception as e:
                print(f"Row {idx}: error scraping {profile_url}: {e}")
                df.at[idx, OUTPUT_COLUMN] = ""

            # Save progress after each row in case the run gets interrupted
            df.to_excel(output_path, index=False)
            print(f"Progress saved to: {output_path}")

    df.to_excel(output_path, index=False)
    print(f"\nDone. Final output saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())