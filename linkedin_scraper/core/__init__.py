"""Core browser and auth utilities."""

from .browser import BrowserManager
from .persistent_browser import PersistentBrowserManager
from .auth import (
    login_with_credentials,
    login_with_cookie,
    is_logged_in,
    wait_for_manual_login,
    load_credentials_from_env,
)
from .exceptions import (
    LinkedInScraperException,
    AuthenticationError,
    RateLimitError,
    ElementNotFoundError,
    ProfileNotFoundError,
    NetworkError,
    ScrapingError,
)
from .utils import (
    detect_rate_limit,
    scroll_to_bottom,
    scroll_to_half,
    click_see_more_buttons,
    handle_modal_close,
    extract_text_safe,
    retry_async,
)

__all__ = [
    "BrowserManager",
    "PersistentBrowserManager",
    "login_with_credentials",
    "login_with_cookie",
    "is_logged_in",
    "wait_for_manual_login",
    "load_credentials_from_env",
    "LinkedInScraperException",
    "AuthenticationError",
    "RateLimitError",
    "ElementNotFoundError",
    "ProfileNotFoundError",
    "NetworkError",
    "ScrapingError",
    "detect_rate_limit",
    "scroll_to_bottom",
    "scroll_to_half",
    "click_see_more_buttons",
    "handle_modal_close",
    "extract_text_safe",
    "retry_async",
]