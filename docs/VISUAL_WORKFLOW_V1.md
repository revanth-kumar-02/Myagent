# Kora Visual Workflow Automation Architecture (V20)

## 1. Overview & Purpose
The **Visual Workflow Automation Layer (V20)** extends Kora's computer vision and control capabilities into structured, multi-step, resilient desktop automations. It replaces brittle pixel-based automation macros with intelligent visual perception, dynamic element grounding, conditional branching, parameter interpolation, and closed-loop verification.

```
+-----------------------------------------------------------------------------------+
|                                 CORE WORKFLOW LOOP                                |
|                                                                                   |
|  Visual Workflow Step                                                             |
|         |                                                                         |
|         v                                                                         |
|  [Observe Screen] (ScreenCaptureEngine + VisualUnderstandingEngine)               |
|         |                                                                         |
|         v                                                                         |
|  [Condition Check] (VisualConditionEvaluator: Element/Text/Dialog Exists)         |
|         |                                                                         |
|         v                                                                         |
|  [Visual Grounding] (VisualGroundingEngine: Query -> Dynamic Coordinates)         |
|         |                                                                         |
|         v                                                                         |
|  [Safety & Permission Gate] (PermissionGate: High Impact Approval)                |
|         |                                                                         |
|         v                                                                         |
|  [Action Dispatch] (MouseControlTool / KeyboardControlTool / WindowManagerTool)    |
|         |                                                                         |
|         v                                                                         |
|  [Post-Action Observe] (Closed-Loop Screenshot Capture)                           |
|         |                                                                         |
|         v                                                                         |
|  [Visual Verification] (Success -> Next Step | Failure -> Retry / Branch / Halt)  |
+-----------------------------------------------------------------------------------+
```

---

## 2. Core Modules (`apps/agent/vision/workflows/`)

### 2.1 Domain Types (`types.py`)
- `VisualActionType`: Supported visual actions (`CLICK`, `DOUBLE_CLICK`, `RIGHT_CLICK`, `TYPE`, `KEY_PRESS`, `SCROLL`, `DRAG`, `SELECT`, `WAIT`, `WINDOW_SWITCH`).
- `ConditionType`: Pre-condition triggers (`ELEMENT_EXISTS`, `TEXT_APPEARS`, `DIALOG_APPEARS`, `SCREEN_STATE_MATCHES`, `PREVIOUS_ACTION_SUCCEEDED`).
- `VisualStepCondition` & `VisualStepVerification`: Declarative condition and verification criteria models.
- `VisualWorkflowStep`: Individual executable workflow step definition with retry thresholds, wait durations, and failure branching pointers (`on_failure_branch_to_step`).
- `VisualWorkflow`: Complete reusable workflow specification containing metadata, parameters, steps, and required permission scopes.
- `StepExecutionRecord` & `WorkflowExecutionResult`: Comprehensive execution traces containing timestamps, durations, pre/post screenshot paths, grounded coordinates, and verification statuses.

### 2.2 Visual Condition Evaluator (`conditions.py`)
- Evaluates screen analysis outputs against declarative step guards.
- Supports affirmative and negated checks (e.g. "Wait until loading indicator is NOT visible").

### 2.3 Visual Workflow Execution Engine (`engine.py`)
- **Dynamic Grounding Replay**: Rather than replaying stale static coordinates, each step grounds target queries in real-time to adapt to window moves and layout changes.
- **Variable Interpolation**: Resolves parameterized templates `{{param_name}}` while strictly rejecting forbidden secret variable names (`password`, `token`, `secret`, `api_key`).
- **Loop Prevention Guard**: Enforces `max_total_steps` limits to prevent infinite execution cycles.
- **Permission & Safety Enforcement**: Routes all computer control actions through `PermissionGate`.
- **Closed-Loop Verification & Recovery**: Verifies UI state post-action and triggers configured retry counts or fallback branches.

### 2.4 Workflow Recorder & Replayer (`recorder.py` & `replay.py`)
- **Sanitized Recording**: Records user/agent interactions while masking passwords and tokens (`[REDACTED_SECRET]`).
- **File Serialization**: Supports standard JSON export and loading.

---

## 3. Flutter Desktop UI Components (`apps/desktop/lib/features/vision/presentation/`)
1. `visual_workflow_view.dart`: Unified visual automation dashboard.
2. `workflow_step_builder_widget.dart`: Visual step editor supporting action configuration and re-ordering.
3. `workflow_runner_widget.dart`: Real-time execution monitor with progress bar, step statuses, and live log stream.

---

## 4. Safety & Operational Constraints
- **Zero Raw Credential Storage**: Passwords and private tokens are masked at record, execution, and log time.
- **Strict Cycle Limits**: Infinite loops from recursive branching are terminated when step counts exceed the threshold.
- **Non-Destructive Defaults**: High-impact actions require interactive user authorization through `PermissionGate`.
