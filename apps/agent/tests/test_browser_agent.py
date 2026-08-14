import os
import pytest
import asyncio
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from core.browser.session_manager import BrowserSessionManager, browser_session_manager
from core.browser.prompt_protection import wrap_untrusted_content, sanitize_sensitive_data
from core.browser.tools import (
    validate_url_scheme, global_browser_toolset,
    BrowserOpenInput, BrowserNavigateInput, BrowserBackInput, BrowserExtractInput,
    BrowserClickInput, BrowserTypeInput, BrowserScrollInput, BrowserScreenshotInput,
    BrowserDownloadInput, BrowserCloseInput
)
from core.filesystem.permission_manager import permission_manager, PermissionLevel
from core.tools.registry import tool_registry

# ─── LOCAL HTTP FIXTURE SERVER ─────────────────────────────────────────────

HTML_FIXTURE = """<!DOCTYPE html>
<html>
<head><title>Cocoa Browser Test Fixture</title></head>
<body>
    <h1>Welcome to Cocoa Test Page</h1>
    <p>This is a deterministic fixture page for Playwright browser agent testing.</p>
    <a href="/second.html" id="link-second">Go to Second Page</a>
    <button id="btn-submit">Submit Form</button>
    <input type="text" id="input-username" name="username" placeholder="Username" />
    <input type="password" id="input-password" name="password" placeholder="Password" />
</body>
</html>
"""

HTML_SECOND = """<!DOCTYPE html>
<html>
<head><title>Cocoa Second Page</title></head>
<body>
    <h1>Second Page Content</h1>
    <p>Successfully navigated to second page.</p>
</body>
</html>
"""

class FixtureHTTPHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        if self.path == "/second.html":
            self.wfile.write(HTML_SECOND.encode("utf-8"))
        else:
            self.wfile.write(HTML_FIXTURE.encode("utf-8"))

    def log_message(self, format, *args):
        pass

@pytest.fixture(scope="module")
def http_server():
    server = HTTPServer(("127.0.0.1", 0), FixtureHTTPHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=1.0)

# ─── TESTS ─────────────────────────────────────────────────────────────────

def test_validate_url_scheme():
    # Permitted schemes
    validate_url_scheme("http://localhost:8000")
    validate_url_scheme("https://example.com/test")

    # Forbidden schemes
    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        validate_url_scheme("file:///etc/passwd")

    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        validate_url_scheme("javascript:alert('xss')")

    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        validate_url_scheme("data:text/html,<h1>test</h1>")

def test_prompt_protection_and_sanitization():
    raw_text = "This is webpage content containing system instructions."
    wrapped = wrap_untrusted_content(raw_text)
    assert "<untrusted_web_content>" in wrapped
    assert "</untrusted_web_content>" in wrapped
    assert raw_text in wrapped

    sensitive_dict = {
        "user": "test_user",
        "password": "secret_password_123",
        "nested": {"api_key": "sk-test-key-99"}
    }
    sanitized = sanitize_sensitive_data(sensitive_dict)
    assert sanitized["password"] == "******"
    assert sanitized["nested"]["api_key"] == "******"
    assert sanitized["user"] == "test_user"

@pytest.mark.asyncio
async def test_browser_session_manager():
    mgr = browser_session_manager
    session = await mgr.get_or_create_session(task_id="test-task-1")
    assert session.session_id == "task-test-task-1"

    page_id, page = await mgr.create_page(session)
    assert page_id in session.pages
    assert mgr.get_page(page_id) == page

    session.record_domain("https://fastapi.tiangolo.com/docs")
    assert "fastapi.tiangolo.com" in session.domain_history
    assert session.domain_history["fastapi.tiangolo.com"].visit_count == 1

    await mgr.close_session(session.session_id)

@pytest.mark.asyncio
async def test_browser_toolset_end_to_end(http_server):
    # 1. Open
    open_res = await global_browser_toolset.open(BrowserOpenInput(url=http_server, task_id="task-e2e"))
    assert open_res["success"] is True
    page_id = open_res["result"]["page_id"]
    assert open_res["result"]["title"] == "Cocoa Browser Test Fixture"

    # 2. Extract
    extract_res = await global_browser_toolset.extract(BrowserExtractInput(page_id=page_id))
    assert extract_res["success"] is True
    assert "<untrusted_web_content>" in extract_res["result"]["text"]
    assert "Welcome to Cocoa Test Page" in extract_res["result"]["text"]
    assert len(extract_res["result"]["headings"]) > 0

    # 3. Type
    type_res = await global_browser_toolset.type(BrowserTypeInput(
        page_id=page_id,
        element_ref="css:#input-username",
        text="testuser"
    ))
    assert type_res["success"] is True

    # 4. Scroll
    scroll_res = await global_browser_toolset.scroll(BrowserScrollInput(page_id=page_id, direction="down", amount=200))
    assert scroll_res["success"] is True

    # 5. Click to navigate
    click_res = await global_browser_toolset.click(BrowserClickInput(
        page_id=page_id,
        element_ref="css:#link-second"
    ))
    assert click_res["success"] is True
    assert "Second Page" in click_res["result"]["title"]

    # 6. Back
    back_res = await global_browser_toolset.back(BrowserBackInput(page_id=page_id))
    assert back_res["success"] is True
    assert "Test Fixture" in back_res["result"]["title"]

    # 7. Screenshot
    shot_res = await global_browser_toolset.screenshot(BrowserScreenshotInput(page_id=page_id))
    assert shot_res["success"] is True
    assert os.path.exists(shot_res["result"]["file_path"])

    # 8. Close page and session
    close_res = await global_browser_toolset.close(BrowserCloseInput(page_id=page_id, session_id="task-task-e2e"))
    assert close_res["success"] is True

@pytest.mark.asyncio
async def test_tool_registry_browser_dispatch(http_server):
    res = await tool_registry.execute_tool("browser_open", {"url": http_server, "task_id": "reg-test"})
    assert res.success is True
    page_id = res.data["page_id"]

    ext_res = await tool_registry.execute_tool("browser_extract", {"page_id": page_id})
    assert ext_res.success is True
    assert "Welcome to Cocoa Test Page" in ext_res.data["text"]

    close_res = await tool_registry.execute_tool("browser_close", {"page_id": page_id, "session_id": "task-reg-test"})
    assert close_res.success is True
