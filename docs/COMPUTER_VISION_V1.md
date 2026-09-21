# Kora Computer Vision & Screen Intelligence Architecture (V19)

## 1. Overview & Purpose
The **Computer Vision & Screen Intelligence Layer (V19)** provides Kora with real-time visual perception, screen understanding, and coordinate-grounded computer control. It bridges visual observation directly to agent reasoning and actions while strictly enforcing safety policies, permission gates, and privacy protections.

```
+-----------------------------------------------------------------------------------+
|                                 CORE FLOW                                         |
|                                                                                   |
|  Screen / Display                                                                 |
|         |                                                                         |
|         v                                                                         |
|  [ScreenCaptureEngine] (Full / Monitor / Window / Region, Ephemeral)              |
|         |                                                                         |
|         v                                                                         |
|  [VisualUnderstandingEngine] (Gemma Vision via ModelRouter, No Hardcoded IDs)      |
|         |                                                                         |
|         v                                                                         |
|  [UIElementDetector] (Structured Elements, Types, BBoxes, Center Coords)          |
|         |                                                                         |
|         v                                                                         |
|  [VisualGroundingEngine] ("click Settings" -> (x, y) coordinates)                 |
|         |                                                                         |
|         v                                                                         |
|  [PermissionGate] (HIGH_IMPACT_ACTION validation & Session Grants)                |
|         |                                                                         |
|         v                                                                         |
|  [Computer Tools] (MouseControlTool / KeyboardControlTool)                        |
|         |                                                                         |
|         v                                                                         |
|  [Closed-Loop Verification] (Post-Action Capture, State Verification, Retry)      |
+-----------------------------------------------------------------------------------+
```

---

## 2. Core Modules (`apps/agent/vision/`)

### 2.1 Domain Types (`types.py`)
- `BoundingBox`: Bounding box with integer pixel bounds `(x, y, w, h)`, normalized bounds `[0.0, 1.0]`, and automatic `center` coordinate calculation `(cx, cy)`.
- `UIElementType`: Classification enum (`BUTTON`, `INPUT_FIELD`, `TEXT`, `MENU`, `LINK`, `DIALOG`, `ICON`, `CHECKBOX`, `TABLE`, `WINDOW`, `CUSTOM`).
- `UIElement`: Structured element with element ID, type, label, bounding box, confidence score, clickable flag, and custom attributes.
- `CaptureTarget`: Scope enum (`FULL_SCREEN`, `MONITOR`, `WINDOW`, `REGION`).
- `CaptureOptions` & `ScreenCaptureResult`: Config and result representations for screen capture.
- `VisualAnalysisResult`: Rich multi-modal analysis payload containing summary, description, detected elements, text tokens, active window, and error dialogs.
- `VisualGroundingTarget`: Result of mapping natural language intent into screen elements and click coordinates.
- `VisualActionResult`: Result of visual action execution and post-action verification.

### 2.2 Screen Capture Engine (`capture.py`)
- **Multi-Scope Capture**: Supports full screen, specific monitor index, focused window ID, or bounded sub-regions.
- **Platform Abstraction**: Dispatches to OS adapters (`LinuxAdapter`, `WindowsAdapter`, `MacOSAdapter`).
- **Ephemeral Lifecycle**: Temporary screenshots are tracked in an isolated directory with auto-cleanup and explicit cleanup APIs to minimize disk usage and protect privacy.

### 2.3 UI Element Detector (`detector.py`)
- **Structured Parsing**: Converts raw model output dictionaries and visual heuristics into type-safe `UIElement` structures.
- **Query & Filtering**: Provides filter utilities by element type, exact/substring label matching, and clickable capability.

### 2.4 Visual Understanding Engine (`analyzer.py`)
- **Dynamic Model Resolution**: Uses `ModelRouter.select("vision")` to communicate with the registered `gemma-vision` model (`google/gemma-3-12b-it`). Zero hardcoded model IDs exist in Python code.
- **Visual Question Answering & Error Recognition**: Supports VQA over screenshot state and modal/dialog extraction.
- **Secret & Password Sanitization**: Masks potential credentials, tokens (`ghp_...`, `sk-...`), or password patterns from text outputs before returning or logging.

### 2.5 Visual Grounding Engine (`grounding.py`)
- **Intent to Coordinates**: Maps queries like "click the Settings button" or "type in Search field" to the highest scoring UI element based on token extraction, role matching, label similarity, and confidence weighting.
- **Center Click Calculation**: Computes exact pixel center points `(cx, cy)` rather than hardcoded absolute screen positions.

### 2.6 Visual Control Coordinator (`controller.py`)
- **Closed-Loop Action Execution**: Coordinates pre-action screenshot -> visual analysis -> coordinate grounding -> permission check -> mouse/keyboard execution -> post-action screenshot -> verification.
- **Safety Gate Integration**: Evaluates `PermissionGate` before executing any high-impact mouse or keyboard actions.

### 2.7 Visual Context Builder (`context.py`)
- **Bounded Prompt Context**: Formats compact text summaries of active windows and detected UI elements for inclusion in Agent Reasoning prompts.

---

## 3. Flutter Desktop UI Components (`apps/desktop/lib/features/vision/`)
1. `screen_intelligence_view.dart`: Main vision dashboard integrating preview canvas, detected element lists, and action history.
2. `screen_preview_widget.dart`: Live screen preview with active grounding target indicators.
3. `detected_elements_widget.dart`: Filterable list of UI elements with color-coded type badges, confidence meters, and action buttons.
4. `visual_action_history_widget.dart`: Real-time execution log showing action type, target label, coordinates, and closed-loop verification status.

---

## 4. Privacy & Safety Commitments
- **No Continuous Capture**: Screen capture is strictly triggered on explicit demand or agent workflow steps.
- **Permission Enforcement**: Computer control actions require `HIGH_IMPACT_ACTION` approval via `PermissionGate`.
- **Ephemeral Storage**: Screenshots are discarded after analysis or verification.
- **Secret Masking**: Sensitive tokens and passwords visible on screen are masked (`[REDACTED_SECRET]`) before logging or analysis storage.
