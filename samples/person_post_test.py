import asyncio

from linkedin_scraper import BrowserManager, PersonPostsScraper


async def main():
    async with BrowserManager(headless=False) as browser:
        await browser.load_session(r"C:\2025-2026 Berkeley\Spring\BAIR\1 - Cross Platform Project\Linkedin Scraping\linkedin_scraper\\linkedin_session.json")

        scraper = PersonPostsScraper(browser.page)

        posts = await scraper.scrape(
            "https://www.linkedin.com/in/jade-mon/",
            limit=5,
        )

        print(f"Found {len(posts)} posts\n")

        for i, post in enumerate(posts, 1):
            print(f"Post {i}")
            print(f"URL: {post.linkedin_url}")
            print(f"Date: {post.posted_date}")
            print(f"Reactions: {post.reactions_count}")
            print(f"Comments: {post.comments_count}")
            print(f"Reposts: {post.reposts_count}")
            print(f"Text: {post.text}")
            print("-" * 80)


if __name__ == "__main__":
    asyncio.run(main())