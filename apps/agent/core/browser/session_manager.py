import logging
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)

class DomainRecord:
    def __init__(self, domain: str):
        self.domain = domain
        self.first_visited = datetime.now(timezone.utc).isoformat()
        self.last_visited = datetime.now(timezone.utc).isoformat()
        self.visit_count = 1

    def touch(self):
        self.last_visited = datetime.now(timezone.utc).isoformat()
        self.visit_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "first_visited": self.first_visited,
            "last_visited": self.last_visited,
            "visit_count": self.visit_count
        }

class BrowserSession:
    def __init__(self, session_id: str, context: BrowserContext, task_id: Optional[str] = None):
        self.session_id = session_id
        self.context = context
        self.task_id = task_id
        self.pages: Dict[str, Page] = {}
        self.active_page_id: Optional[str] = None
        self.domain_history: Dict[str, DomainRecord] = {}
        self.created_at = datetime.now(timezone.utc).isoformat()

    def record_domain(self, url: str):
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if not domain:
                return
            if domain in self.domain_history:
                self.domain_history[domain].touch()
            else:
                self.domain_history[domain] = DomainRecord(domain)
        except Exception as e:
            logger.warning(f"Could not parse domain from URL '{url}': {e}")

    async def close(self):
        try:
            for page in list(self.pages.values()):
                try:
                    if not page.is_closed():
                        await page.close()
                except Exception:
                    pass
            self.pages.clear()
            try:
                await self.context.close()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Error closing browser session {self.session_id}: {e}")

class BrowserSessionManager:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self.sessions: Dict[str, BrowserSession] = {}
        self.page_to_session: Dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def _ensure_browser(self):
        async with self._lock:
            current_loop = asyncio.get_running_loop()
            if hasattr(self, "_loop") and self._loop != current_loop:
                logger.info("Event loop changed, resetting Playwright instance.")
                self._browser = None
                self._playwright = None
            self._loop = current_loop

            if self._playwright is None:
                self._playwright = await async_playwright().start()
            if self._browser is None or not self._browser.is_connected():
                self._browser = await self._playwright.chromium.launch(
                    headless=self.headless,
                    args=["--no-sandbox", "--disable-setuid-sandbox"]
                )

    async def get_or_create_session(self, task_id: Optional[str] = None, session_id: Optional[str] = None) -> BrowserSession:
        await self._ensure_browser()
        
        sid = session_id or (f"task-{task_id}" if task_id else f"session-{uuid.uuid4().hex[:8]}")
        if sid in self.sessions:
            return self.sessions[sid]

        assert self._browser is not None
        # Create an isolated browser context
        context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 CocoaAgent/1.0"
        )
        
        session = BrowserSession(session_id=sid, context=context, task_id=task_id)
        self.sessions[sid] = session
        logger.info(f"Created isolated browser session: {sid}")
        return session

    async def create_page(self, session: BrowserSession) -> tuple[str, Page]:
        page = await session.context.new_page()
        page_id = f"page-{uuid.uuid4().hex[:8]}"
        session.pages[page_id] = page
        session.active_page_id = page_id
        self.page_to_session[page_id] = session.session_id
        return page_id, page

    def get_page(self, page_id: str) -> Optional[Page]:
        sid = self.page_to_session.get(page_id)
        if sid and sid in self.sessions:
            return self.sessions[sid].pages.get(page_id)
        return None

    def get_session_by_page(self, page_id: str) -> Optional[BrowserSession]:
        sid = self.page_to_session.get(page_id)
        if sid:
            return self.sessions.get(sid)
        return None

    async def close_session(self, session_id: str):
        session = self.sessions.pop(session_id, None)
        if session:
            # clean up page map
            for page_id in list(session.pages.keys()):
                self.page_to_session.pop(page_id, None)
            await session.close()
            logger.info(f"Closed browser session: {session_id}")

    async def close_all(self):
        for sid in list(self.sessions.keys()):
            await self.close_session(sid)
        if self._browser:
            try:
                if self._browser.is_connected():
                    await self._browser.close()
            except Exception as e:
                logger.warning(f"Error closing browser in close_all: {e}")
            self._browser = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.warning(f"Error stopping playwright in close_all: {e}")
            self._playwright = None
        logger.info("BrowserSessionManager shut down completely.")

# Global instance
browser_session_manager = BrowserSessionManager()
