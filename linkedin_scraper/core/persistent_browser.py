from pathlib import Path
from typing import Optional

from playwright.async_api import BrowserContext, Page, Playwright, async_playwright


class PersistentBrowserManager:
    """
    Chromium persistent-profile browser manager.

    Use this instead of storage_state/session.json when LinkedIn is tripping
    CAPTCHA or checkpoint flows. It reuses a real Chromium user-data directory.
    """

    def __init__(
        self,
        user_data_dir: str = "playwright_linkedin_profile",
        headless: bool = False,
        viewport_width: int = 1400,
        viewport_height: int = 1000,
        channel: Optional[str] = None,
    ):
        self.user_data_dir = str(Path(user_data_dir).resolve())
        self.headless = headless
        self.viewport = {"width": viewport_width, "height": viewport_height}
        self.channel = channel

        self.playwright: Optional[Playwright] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def __aenter__(self):
        self.playwright = await async_playwright().start()

        launch_kwargs = {
            "user_data_dir": self.user_data_dir,
            "headless": self.headless,
            "viewport": self.viewport,
        }
        if self.channel:
            launch_kwargs["channel"] = self.channel

        self.context = await self.playwright.chromium.launch_persistent_context(
            **launch_kwargs
        )

        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.context is not None:
            await self.context.close()
        if self.playwright is not None:
            await self.playwright.stop()

    async def goto(self, url: str, wait_until: str = "domcontentloaded"):
        if self.page is None:
            raise RuntimeError("Browser not initialized.")
        return await self.page.goto(url, wait_until=wait_until)