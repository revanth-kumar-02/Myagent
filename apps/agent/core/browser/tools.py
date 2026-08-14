import os
import logging
import pathlib
import uuid
import asyncio
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
from pydantic import BaseModel, Field
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from core.browser.session_manager import browser_session_manager, BrowserSession
from core.browser.prompt_protection import wrap_untrusted_content, sanitize_sensitive_data
from core.filesystem.permission_manager import permission_manager, PermissionLevel
from api.websocket import ws_manager

logger = logging.getLogger(__name__)

STORAGE_DIR = pathlib.Path(__file__).parent.parent.parent / "storage"
SCREENSHOT_DIR = STORAGE_DIR / "screenshots"
DOWNLOAD_DIR = STORAGE_DIR / "downloads"

SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ─── Pydantic Input Schemas ────────────────────────────────────────────────

class BrowserOpenInput(BaseModel):
    url: str = Field(description="URL to open, must begin with http:// or https://")
    task_id: Optional[str] = Field(default=None, description="Task ID for session isolation")

class BrowserNavigateInput(BaseModel):
    page_id: str = Field(description="Page ID from browser_open")
    url: str = Field(description="Target URL to navigate to")

class BrowserBackInput(BaseModel):
    page_id: str = Field(description="Page ID from browser_open")

class BrowserExtractInput(BaseModel):
    page_id: str = Field(description="Page ID from browser_open")
    max_text_chars: int = Field(default=15000, description="Max text characters to extract")

class BrowserClickInput(BaseModel):
    page_id: str = Field(description="Page ID from browser_open")
    element_ref: str = Field(description="Element reference, e.g. text:Submit, button:Search, css:#btn, or role:button[name='Submit']")

class BrowserTypeInput(BaseModel):
    page_id: str = Field(description="Page ID from browser_open")
    element_ref: str = Field(description="Target input element reference")
    text: str = Field(description="Text to type into input field")
    clear_first: bool = Field(default=True, description="Whether to clear existing value first")

class BrowserScrollInput(BaseModel):
    page_id: str = Field(description="Page ID from browser_open")
    direction: str = Field(default="down", description="Scroll direction: up | down | top | bottom")
    amount: int = Field(default=500, description="Scroll amount in pixels for up/down")

class BrowserScreenshotInput(BaseModel):
    page_id: str = Field(description="Page ID from browser_open")
    full_page: bool = Field(default=False, description="Whether to capture full scrollable page")

class BrowserDownloadInput(BaseModel):
    page_id: str = Field(description="Page ID from browser_open")
    url: Optional[str] = Field(default=None, description="Direct download URL if available")
    trigger_element_ref: Optional[str] = Field(default=None, description="Element reference to click for download")

class BrowserCloseInput(BaseModel):
    page_id: Optional[str] = Field(default=None, description="Page ID to close")
    session_id: Optional[str] = Field(default=None, description="Session ID to close")

# ─── URL Validation Helper ───────────────────────────────────────────────

ALLOWED_SCHEMES = {"http", "https"}

def validate_url_scheme(url: str) -> None:
    try:
        parsed = urlparse(url)
        if not parsed.scheme or parsed.scheme.lower() not in ALLOWED_SCHEMES:
            raise ValueError(f"Unsupported URL scheme '{parsed.scheme}'. Only http and https are permitted.")
    except Exception as e:
        if "Unsupported URL scheme" in str(e):
            raise e
        raise ValueError(f"Malformed or invalid URL '{url}': {e}")

# ─── Browser ToolSet Implementation ──────────────────────────────────────

class BrowserToolSet:
    def __init__(self):
        self.session_manager = browser_session_manager

    # 1. BROWSER OPEN
    async def open(self, input_data: BrowserOpenInput) -> Dict[str, Any]:
        try:
            validate_url_scheme(input_data.url)
            
            # Permission check
            has_perm = await permission_manager.check_permission(
                tool_name="browser_open",
                path=input_data.url,
                operation="open_page",
                permission_level=PermissionLevel.BROWSER_READ,
                task_id=input_data.task_id
            )
            if not has_perm:
                return {"success": False, "error": {"code": "PERMISSION_DENIED", "message": "Browser open permission denied"}}

            session = await self.session_manager.get_or_create_session(task_id=input_data.task_id)
            page_id, page = await self.session_manager.create_page(session)

            await ws_manager.broadcast({
                "event": "browser.session_started",
                "data": {"session_id": session.session_id, "page_id": page_id, "task_id": input_data.task_id}
            })
            await ws_manager.broadcast({
                "event": "browser.navigation_started",
                "data": {"page_id": page_id, "url": input_data.url}
            })

            # Navigate to page with timeout
            response = await page.goto(input_data.url, timeout=30000, wait_until="domcontentloaded")
            session.record_domain(input_data.url)
            title = await page.title()

            await ws_manager.broadcast({
                "event": "browser.navigation_completed",
                "data": {"page_id": page_id, "url": page.url, "title": title, "status": response.status if response else 200}
            })

            return {
                "success": True,
                "result": {
                    "page_id": page_id,
                    "session_id": session.session_id,
                    "url": page.url,
                    "title": title,
                    "status": response.status if response else 200
                }
            }
        except PlaywrightTimeoutError:
            await ws_manager.broadcast({"event": "browser.failed", "data": {"error": "Page navigation timed out"}})
            return {"success": False, "error": {"code": "TIMEOUT", "message": f"Navigation to '{input_data.url}' timed out"}}
        except Exception as e:
            logger.error(f"browser_open failed: {e}")
            await ws_manager.broadcast({"event": "browser.failed", "data": {"error": str(e)}})
            return {"success": False, "error": {"code": "OPEN_FAILED", "message": str(e)}}

    # 2. BROWSER NAVIGATE
    async def navigate(self, input_data: BrowserNavigateInput) -> Dict[str, Any]:
        page = self.session_manager.get_page(input_data.page_id)
        if not page or page.is_closed():
            return {"success": False, "error": {"code": "INVALID_PAGE", "message": f"Page ID '{input_data.page_id}' not found or closed"}}

        try:
            validate_url_scheme(input_data.url)
            session = self.session_manager.get_session_by_page(input_data.page_id)

            await ws_manager.broadcast({
                "event": "browser.navigation_started",
                "data": {"page_id": input_data.page_id, "url": input_data.url}
            })

            response = await page.goto(input_data.url, timeout=30000, wait_until="domcontentloaded")
            if session:
                session.record_domain(input_data.url)
            title = await page.title()

            await ws_manager.broadcast({
                "event": "browser.navigation_completed",
                "data": {"page_id": input_data.page_id, "url": page.url, "title": title, "status": response.status if response else 200}
            })

            return {
                "success": True,
                "result": {
                    "page_id": input_data.page_id,
                    "url": page.url,
                    "title": title,
                    "status": response.status if response else 200
                }
            }
        except Exception as e:
            return {"success": False, "error": {"code": "NAVIGATE_FAILED", "message": str(e)}}

    # 3. BROWSER BACK
    async def back(self, input_data: BrowserBackInput) -> Dict[str, Any]:
        page = self.session_manager.get_page(input_data.page_id)
        if not page or page.is_closed():
            return {"success": False, "error": {"code": "INVALID_PAGE", "message": f"Page ID '{input_data.page_id}' not found"}}

        try:
            response = await page.go_back(timeout=15000, wait_until="domcontentloaded")
            title = await page.title()
            return {
                "success": True,
                "result": {
                    "page_id": input_data.page_id,
                    "url": page.url,
                    "title": title,
                    "status": response.status if response else 200
                }
            }
        except Exception as e:
            return {"success": False, "error": {"code": "BACK_FAILED", "message": str(e)}}

    # 4. BROWSER EXTRACT
    async def extract(self, input_data: BrowserExtractInput) -> Dict[str, Any]:
        page = self.session_manager.get_page(input_data.page_id)
        if not page or page.is_closed():
            return {"success": False, "error": {"code": "INVALID_PAGE", "message": f"Page ID '{input_data.page_id}' not found"}}

        try:
            title = await page.title()
            url = page.url

            # Extract structured semantic info via JavaScript in page evaluation
            extracted_info = await page.evaluate("""
                () => {
                    const headings = Array.from(document.querySelectorAll('h1, h2, h3'))
                        .map(h => ({ tag: h.tagName.toLowerCase(), text: h.innerText.trim() }))
                        .filter(h => h.text.length > 0)
                        .slice(0, 15);

                    const links = Array.from(document.querySelectorAll('a[href]'))
                        .map(a => ({ text: a.innerText.trim(), href: a.href }))
                        .filter(a => a.text.length > 0 && a.href.startsWith('http'))
                        .slice(0, 20);

                    const buttons = Array.from(document.querySelectorAll('button, input[type="button"], input[type="submit"]'))
                        .map(b => b.innerText?.trim() || b.value?.trim() || 'Button')
                        .filter(t => t.length > 0)
                        .slice(0, 15);

                    const inputs = Array.from(document.querySelectorAll('input:not([type="hidden"]), textarea, select'))
                        .map(i => ({
                            name: i.name || i.id || i.placeholder || 'input',
                            type: i.type || i.tagName.toLowerCase(),
                            value: (i.type === 'password') ? '******' : (i.value || '')
                        }))
                        .slice(0, 10);

                    // Main visible body text
                    const bodyText = document.body ? document.body.innerText : '';
                    return { headings, links, buttons, inputs, bodyText };
                }
            """)

            untrusted_text = wrap_untrusted_content(extracted_info["bodyText"], max_chars=input_data.max_text_chars)

            await ws_manager.broadcast({
                "event": "browser.extraction_completed",
                "data": {"page_id": input_data.page_id, "url": url, "title": title, "headings_count": len(extracted_info["headings"])}
            })

            return {
                "success": True,
                "result": {
                    "page_id": input_data.page_id,
                    "url": url,
                    "title": title,
                    "text": untrusted_text,
                    "headings": extracted_info["headings"],
                    "links": extracted_info["links"],
                    "buttons": extracted_info["buttons"],
                    "inputs": extracted_info["inputs"]
                }
            }
        except Exception as e:
            return {"success": False, "error": {"code": "EXTRACT_FAILED", "message": str(e)}}

    # 5. BROWSER CLICK
    async def click(self, input_data: BrowserClickInput) -> Dict[str, Any]:
        page = self.session_manager.get_page(input_data.page_id)
        if not page or page.is_closed():
            return {"success": False, "error": {"code": "INVALID_PAGE", "message": f"Page ID '{input_data.page_id}' not found"}}

        try:
            # Determine permission requirement
            ref_lower = input_data.element_ref.lower()
            is_external_action = any(k in ref_lower for k in ["submit", "buy", "purchase", "delete", "remove", "pay", "send"])
            perm_level = PermissionLevel.BROWSER_EXTERNAL_ACTION if is_external_action else PermissionLevel.BROWSER_INTERACT

            has_perm = await permission_manager.check_permission(
                tool_name="browser_click",
                path=page.url,
                operation=f"click:{input_data.element_ref}",
                permission_level=perm_level
            )
            if not has_perm:
                return {"success": False, "error": {"code": "PERMISSION_DENIED", "message": f"Permission denied for click action on '{input_data.element_ref}'"}}

            await ws_manager.broadcast({
                "event": "browser.click_started",
                "data": {"page_id": input_data.page_id, "element_ref": input_data.element_ref}
            })

            # Resolve element selector from stable element_ref
            selector = self._resolve_selector(input_data.element_ref)
            
            # Verify existence & interactability
            element = await page.wait_for_selector(selector, state="visible", timeout=10000)
            if not element:
                return {"success": False, "error": {"code": "ELEMENT_NOT_FOUND", "message": f"Element '{input_data.element_ref}' not found or not visible"}}

            await element.click(timeout=10000)
            await page.wait_for_load_state("domcontentloaded", timeout=5000)
            
            new_title = await page.title()
            new_url = page.url

            await ws_manager.broadcast({
                "event": "browser.click_completed",
                "data": {"page_id": input_data.page_id, "url": new_url, "title": new_title}
            })

            return {
                "success": True,
                "result": {
                    "page_id": input_data.page_id,
                    "url": new_url,
                    "title": new_title,
                    "clicked_element": input_data.element_ref
                }
            }
        except PlaywrightTimeoutError:
            return {"success": False, "error": {"code": "ELEMENT_TIMEOUT", "message": f"Element '{input_data.element_ref}' was not interactable within timeout"}}
        except Exception as e:
            return {"success": False, "error": {"code": "CLICK_FAILED", "message": str(e)}}

    # 6. BROWSER TYPE
    async def type(self, input_data: BrowserTypeInput) -> Dict[str, Any]:
        page = self.session_manager.get_page(input_data.page_id)
        if not page or page.is_closed():
            return {"success": False, "error": {"code": "INVALID_PAGE", "message": f"Page ID '{input_data.page_id}' not found"}}

        try:
            has_perm = await permission_manager.check_permission(
                tool_name="browser_type",
                path=page.url,
                operation=f"type:{input_data.element_ref}",
                permission_level=PermissionLevel.BROWSER_INTERACT
            )
            if not has_perm:
                return {"success": False, "error": {"code": "PERMISSION_DENIED", "message": "Permission denied for type action"}}

            # Redact password/sensitive text from broadcasts and logs
            is_password = "password" in input_data.element_ref.lower() or "secret" in input_data.element_ref.lower()
            safe_text = "******" if is_password else input_data.text[:20]

            await ws_manager.broadcast({
                "event": "browser.type_started",
                "data": {"page_id": input_data.page_id, "element_ref": input_data.element_ref, "text_summary": safe_text}
            })

            selector = self._resolve_selector(input_data.element_ref)
            element = await page.wait_for_selector(selector, state="visible", timeout=10000)
            if not element:
                return {"success": False, "error": {"code": "ELEMENT_NOT_FOUND", "message": f"Input element '{input_data.element_ref}' not found"}}

            if input_data.clear_first:
                await element.fill("")
            await element.type(input_data.text, delay=20)

            await ws_manager.broadcast({
                "event": "browser.type_completed",
                "data": {"page_id": input_data.page_id, "element_ref": input_data.element_ref}
            })

            return {
                "success": True,
                "result": {
                    "page_id": input_data.page_id,
                    "element_ref": input_data.element_ref,
                    "typed": safe_text
                }
            }
        except Exception as e:
            return {"success": False, "error": {"code": "TYPE_FAILED", "message": str(e)}}

    # 7. BROWSER SCROLL
    async def scroll(self, input_data: BrowserScrollInput) -> Dict[str, Any]:
        page = self.session_manager.get_page(input_data.page_id)
        if not page or page.is_closed():
            return {"success": False, "error": {"code": "INVALID_PAGE", "message": f"Page ID '{input_data.page_id}' not found"}}

        try:
            dir_lower = input_data.direction.lower()
            if dir_lower == "down":
                await page.evaluate(f"window.scrollBy(0, {input_data.amount})")
            elif dir_lower == "up":
                await page.evaluate(f"window.scrollBy(0, -{input_data.amount})")
            elif dir_lower == "top":
                await page.evaluate("window.scrollTo(0, 0)")
            elif dir_lower == "bottom":
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

            scroll_position = await page.evaluate("() => ({ x: window.scrollX, y: window.scrollY, totalHeight: document.body.scrollHeight })")

            return {
                "success": True,
                "result": {
                    "page_id": input_data.page_id,
                    "direction": input_data.direction,
                    "position": scroll_position
                }
            }
        except Exception as e:
            return {"success": False, "error": {"code": "SCROLL_FAILED", "message": str(e)}}

    # 8. BROWSER SCREENSHOT
    async def screenshot(self, input_data: BrowserScreenshotInput) -> Dict[str, Any]:
        page = self.session_manager.get_page(input_data.page_id)
        if not page or page.is_closed():
            return {"success": False, "error": {"code": "INVALID_PAGE", "message": f"Page ID '{input_data.page_id}' not found"}}

        try:
            filename = f"screenshot_{uuid.uuid4().hex[:8]}.png"
            file_path = SCREENSHOT_DIR / filename
            await page.screenshot(path=str(file_path), full_page=input_data.full_page)

            return {
                "success": True,
                "result": {
                    "page_id": input_data.page_id,
                    "file_name": filename,
                    "file_path": str(file_path),
                    "url": page.url,
                    "title": await page.title()
                }
            }
        except Exception as e:
            return {"success": False, "error": {"code": "SCREENSHOT_FAILED", "message": str(e)}}

    # 9. BROWSER DOWNLOAD
    async def download(self, input_data: BrowserDownloadInput) -> Dict[str, Any]:
        page = self.session_manager.get_page(input_data.page_id)
        if not page or page.is_closed():
            return {"success": False, "error": {"code": "INVALID_PAGE", "message": f"Page ID '{input_data.page_id}' not found"}}

        try:
            # Download requires explicit BROWSER_DOWNLOAD permission check
            has_perm = await permission_manager.check_permission(
                tool_name="browser_download",
                path=input_data.url or page.url,
                operation="download_file",
                permission_level=PermissionLevel.BROWSER_DOWNLOAD
            )
            if not has_perm:
                return {"success": False, "error": {"code": "PERMISSION_DENIED", "message": "Browser download permission denied"}}

            await ws_manager.broadcast({
                "event": "browser.download_started",
                "data": {"page_id": input_data.page_id, "url": input_data.url}
            })

            file_path = None
            suggested_filename = f"download_{uuid.uuid4().hex[:8]}"

            if input_data.trigger_element_ref:
                selector = self._resolve_selector(input_data.trigger_element_ref)
                async with page.expect_download(timeout=30000) as download_info:
                    await page.click(selector)
                download = await download_info.value
                suggested_filename = download.suggested_filename
                file_path = DOWNLOAD_DIR / suggested_filename
                await download.save_as(str(file_path))
            elif input_data.url:
                validate_url_scheme(input_data.url)
                async with page.expect_download(timeout=30000) as download_info:
                    await page.goto(input_data.url)
                download = await download_info.value
                suggested_filename = download.suggested_filename
                file_path = DOWNLOAD_DIR / suggested_filename
                await download.save_as(str(file_path))
            else:
                return {"success": False, "error": {"code": "INVALID_INPUT", "message": "Either url or trigger_element_ref must be provided"}}

            # Verification
            if not file_path.exists() or file_path.stat().st_size == 0:
                raise ValueError(f"Downloaded file verification failed for '{suggested_filename}'")

            file_size = file_path.stat().st_size

            await ws_manager.broadcast({
                "event": "browser.download_completed",
                "data": {"page_id": input_data.page_id, "filename": suggested_filename, "size": file_size}
            })

            return {
                "success": True,
                "result": {
                    "filename": suggested_filename,
                    "local_path": str(file_path),
                    "size_bytes": file_size,
                    "mime_type": "application/octet-stream"
                }
            }
        except Exception as e:
            return {"success": False, "error": {"code": "DOWNLOAD_FAILED", "message": str(e)}}

    # 10. BROWSER CLOSE
    async def close(self, input_data: BrowserCloseInput) -> Dict[str, Any]:
        try:
            if input_data.page_id:
                session = self.session_manager.get_session_by_page(input_data.page_id)
                page = self.session_manager.get_page(input_data.page_id)
                if page and not page.is_closed():
                    await page.close()
                if session and input_data.page_id in session.pages:
                    session.pages.pop(input_data.page_id)
                await ws_manager.broadcast({
                    "event": "browser.session_closed",
                    "data": {"page_id": input_data.page_id}
                })
                return {"success": True, "result": {"closed_page_id": input_data.page_id}}

            if input_data.session_id:
                await self.session_manager.close_session(input_data.session_id)
                await ws_manager.broadcast({
                    "event": "browser.session_closed",
                    "data": {"session_id": input_data.session_id}
                })
                return {"success": True, "result": {"closed_session_id": input_data.session_id}}

            return {"success": False, "error": {"code": "INVALID_INPUT", "message": "Specify page_id or session_id"}}
        except Exception as e:
            return {"success": False, "error": {"code": "CLOSE_FAILED", "message": str(e)}}

    # Helper: resolve selector references safely
    def _resolve_selector(self, ref: str) -> str:
        if ref.startswith("css:"):
            return ref[4:].strip()
        elif ref.startswith("text:"):
            txt = ref[5:].strip()
            return f"text={txt}"
        elif ref.startswith("button:"):
            btn_txt = ref[7:].strip()
            return f"button:has-text('{btn_txt}'), input[type='button'][value='{btn_txt}'], input[type='submit'][value='{btn_txt}']"
        elif ref.startswith("role:"):
            return ref[5:].strip()
        else:
            # Fallback text or css search
            return f"text={ref}"

# Global instance
global_browser_toolset = BrowserToolSet()
