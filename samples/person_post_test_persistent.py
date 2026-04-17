import asyncio
from pathlib import Path

from linkedin_scraper import PersistentBrowserManager, PersonPostsScraper
from linkedin_scraper.core.exceptions import RateLimitError


PROFILE_URL = "https://www.linkedin.com/in/jade-mon/"


async def main():
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
        # input("Press Enter to continue...")

        scraper = PersonPostsScraper(browser.page)

        try:
            posts = await scraper.scrape(PROFILE_URL, limit=5)
        except RateLimitError as e:
            print(f"\nRate-limit / CAPTCHA page detected: {e}")
            print("Please clear it manually in the open browser window.")
            # input("After clearing the challenge and confirming the Activity page is visible, press Enter...")

            activity_url = PROFILE_URL.rstrip("/") + "/recent-activity/all/"
            await browser.goto(activity_url, wait_until="domcontentloaded")
            print("Current URL after manual clear:", browser.page.url)
            print("Current title after manual clear:", await browser.page.title())

            posts = await scraper._scrape_posts(limit=5, profile_name=None)

        print(f"\nFound {len(posts)} posts\n")

        for i, post in enumerate(posts, 1):
            print(f"Post {i}")
            print(f"URL: {post.linkedin_url}")
            print(f"Date: {post.posted_date}")
            print(f"Reactions: {post.reactions_count}")
            print(f"Comments: {post.comments_count}")
            print(f"Reposts: {post.reposts_count}")
            print(f"Text: {(post.text or '')[:500]}")
            print("-" * 80)


if __name__ == "__main__":
    asyncio.run(main())