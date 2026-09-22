# Kora Tool System & Computer Control (V8) — Architecture & Guide

## 1. Overview

Kora V8 introduces a modular, cross-platform, security-first **Tool Execution & Computer Control Layer**. It enables the agent to safely observe, interact with, and manipulate the operating system, file system, browser, and developer environment across **Linux**, **Windows**, and **macOS**.

```
Agent Decision (V7)
       │
       ▼
   ToolRouter
       │
       ▼
PermissionGate (4 Tiers + Interactive Approval)
       │
       ▼
  ToolRegistry (22 Core Tools)
       │
       ▼
BasePlatformAdapter (Linux / Windows / macOS)
       │
       ▼
OS / Filesystem / GUI / Network
       │
       ▼
ToolAuditLogger (Secret Masking + Metrics) & Verifier
```

---

## 2. Core Tool Registry

All tools inherit from [`BaseTool`](file:///home/rev/My_Personal_Space/Projects/Unfinished/Myagent/apps/agent/tools/base.py) and are registered in [`ToolRegistry`](file:///home/rev/My_Personal_Space/Projects/Unfinished/Myagent/apps/agent/tools/registry.py).

| Category | Tool ID | Description | Default Permission |
|---|---|---|---|
| **SYSTEM** | `app_launcher` | Launch installed system applications | `EXTERNAL_ACTION` |
| | `file_manager` | Reveal/open paths in the system file manager | `EXTERNAL_ACTION` |
| | `clipboard` | Read and write desktop clipboard buffers | `LOW_RISK_WRITE` |
| | `notification` | Dispatch native desktop notifications | `EXTERNAL_ACTION` |
| | `system_info` | Inspect OS, CPU count, memory, architecture | `READ` |
| **FILES** | `file_read` | Read text content with line limits | `READ` |
| | `file_write` | Write or append file content safely | `LOW_RISK_WRITE` |
| | `file_create` | Create new empty files | `LOW_RISK_WRITE` |
| | `file_move` | Move files between paths | `LOW_RISK_WRITE` |
| | `file_rename` | Rename files or directories | `LOW_RISK_WRITE` |
| | `file_delete` | Permanently delete file from disk | `HIGH_IMPACT_ACTION` |
| | `directory_ops` | List, create, or remove directories | `LOW_RISK_WRITE` |
| **COMPUTER** | `window_manager`| List, focus, minimize, or close GUI windows | `EXTERNAL_ACTION` |
| | `mouse_control` | Move cursor, click, drag, scroll | `EXTERNAL_ACTION` |
| | `keyboard_control`| Type text, keypresses, shortcuts | `EXTERNAL_ACTION` |
| | `screen_capture`| Take fullscreen or region screenshots | `READ` |
| **WEB** | `browser_control`| Launch, close, or configure browser session | `EXTERNAL_ACTION` |
| | `page_navigation`| Navigate to URL, back, forward, refresh | `EXTERNAL_ACTION` |
| | `page_interaction`| Click, type, select CSS elements | `EXTERNAL_ACTION` |
| | `download_manager`| Download files from remote URLs | `LOW_RISK_WRITE` |
| **DEVELOPMENT** | `terminal_exec` | Execute shell commands in isolated subprocess | `HIGH_IMPACT_ACTION` |
| | `git_operations`| Run git status, diff, log, commit, branch | `LOW_RISK_WRITE` |
| | `database_ops` | Execute safe SQL queries | `HIGH_IMPACT_ACTION` |

---

## 3. Platform Abstraction Layer

Operating-system-specific commands and native API calls are isolated inside `apps/agent/tools/platforms/`:

- **[`LinuxAdapter`](file:///home/rev/My_Personal_Space/Projects/Unfinished/Myagent/apps/agent/tools/platforms/linux.py)**: Utilizes `xclip`/`wl-copy`, `notify-send`, `wmctrl`/`xdotool`, and `scrot`/`gnome-screenshot`.
- **[`WindowsAdapter`](file:///home/rev/My_Personal_Space/Projects/Unfinished/Myagent/apps/agent/tools/platforms/windows.py)**: Utilizes `powershell`, Windows clipboard, Windows notifications, and PowerShell commands.
- **[`MacOSAdapter`](file:///home/rev/My_Personal_Space/Projects/Unfinished/Myagent/apps/agent/tools/platforms/macos.py)**: Utilizes `pbcopy`/`pbpaste`, `osascript` (AppleScript notifications & window management), and `screencapture`.
- **[`get_platform_adapter()`](file:///home/rev/My_Personal_Space/Projects/Unfinished/Myagent/apps/agent/tools/platforms/factory.py)**: Automatic runtime factory returning the correct platform adapter.

---

## 4. 4-Tier Permission System

1. **`READ`**: Inspecting state, querying logs, reading files, reading clipboard, screen capture. Auto-allowed by policy.
2. **`LOW_RISK_WRITE`**: Modifying non-critical files, git diffs/status, writing clipboard. Auto-allowed under standard session.
3. **`EXTERNAL_ACTION`**: Browser navigation, clicking GUI elements, launching apps, desktop notifications.
4. **`HIGH_IMPACT_ACTION`**: File deletion, terminal execution, database mutations, system config alteration. Requires interactive user approval over WebSocket or explicit session grant.

---

## 5. Audit Logging & Secret Masking

The [`ToolAuditLogger`](file:///home/rev/My_Personal_Space/Projects/Unfinished/Myagent/apps/agent/tools/audit.py) records every tool call with:
- `tool_id` and execution action
- Permission level
- Start time, completion time, and duration in milliseconds
- Status (`SUCCESS`, `ERROR`, `DENIED`, `TIMEOUT`)
- **Sanitized payload & metadata**: All passwords, API keys, bearer tokens, and credentials matching `is_sensitive_content()` or sensitive keys (`password|secret|api_key|token|auth`) are automatically redacted into `****** [REDACTED SECRET]`.
