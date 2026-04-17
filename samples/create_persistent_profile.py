import asyncio
from pathlib import Path

from linkedin_scraper import PersistentBrowserManager


async def main():
    project_root = Path(__file__).resolve().parent.parent
    profile_dir = project_root / "playwright_linkedin_profile"

    print(f"Using persistent profile dir: {profile_dir}")

    async with PersistentBrowserManager(
        user_data_dir=str(profile_dir),
        headless=False,
    ) as browser:
        await browser.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")

        print("\nA Chromium window is open.")
        print("1. Log into LinkedIn if needed")
        print("2. Solve any CAPTCHA/checkpoint if shown")
        print("3. Make sure the feed or your profile is fully visible")
        input("\nPress Enter here after LinkedIn is fully open and usable...")

        print("\nPersistent profile is now saved on disk.")
        print("You can reuse it in future runs without session.json.")


if __name__ == "__main__":
    asyncio.run(main())