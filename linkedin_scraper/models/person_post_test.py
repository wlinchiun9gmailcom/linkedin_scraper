import asyncio
from pathlib import Path

import pandas as pd

from linkedin_scraper import BrowserManager, PersonPostsScraper


EXCEL_PATH = r"C:\2025-2026 Berkeley\Spring\BAIR\1 - Cross Platform Project\Linkedin Scraping\openreview_verified_conference_authors_2021_2025_debug_final_with_twitter (2).xlsx"
OUTPUT_PATH = r"C:\2025-2026 Berkeley\Spring\BAIR\1 - Cross Platform Project\Linkedin Scraping\openreview_verified_conference_authors_2021_2025_debug_final_with_twitter (2).xlsx"
LINKEDIN_URL_COLUMN = "LinkedIn URL "
OUTPUT_COLUMN = "Linkedin Posts"
POST_LIMIT = 5

START_ROW = 0
END_ROW = 1000


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

    async with BrowserManager(headless=False) as browser:
        await browser.load_session("session.json")

        scraper = PersonPostsScraper(browser.page)

        for idx in range(start_row, end_row + 1):
            raw_url = df.at[idx, LINKEDIN_URL_COLUMN]

            if pd.isna(raw_url):
                print(f"Row {idx}: blank LinkedIn URL, skipping")
                continue

            url = str(raw_url).strip()
            if not url:
                print(f"Row {idx}: blank LinkedIn URL, skipping")
                continue

            print(f"Row {idx}: scraping {url}")

            try:
                posts = await scraper.scrape(url, limit=POST_LIMIT)

                post_texts = []
                for post_num, post in enumerate(posts, 1):
                    text = (post.text or "").strip()
                    if text:
                        post_texts.append(f"Post {post_num}:\n{text}")

                separator = "\n\n" + ("-" * 80) + "\n\n"
                df.at[idx, OUTPUT_COLUMN] = separator.join(post_texts) if post_texts else ""

                print(f"Row {idx}: found {len(posts)} posts")

            except Exception as e:
                print(f"Row {idx}: error scraping {url}: {e}")
                df.at[idx, OUTPUT_COLUMN] = ""

    df.to_excel(output_path, index=False)
    print(f"\nDone. Saved output to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())