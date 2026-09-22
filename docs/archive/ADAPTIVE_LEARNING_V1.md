# Kora — V12: Self-Reflection & Adaptive Learning

## 1. Purpose & Overview
The **Self-Reflection & Adaptive Learning (V12)** layer enables Kora to analyze completed and failed task executions, extract factual, non-sensitive, reusable operational insights, validate them against actual execution evidence, persist them in Long-Term Memory (`MemoryType.AGENT_LEARNING`) and the Knowledge Graph, and adapt future task planning without modifying system source code or bypassing security rules.

---

## 2. Core Architecture & Lifecycle

```
               +-----------------------------+
               |     Task Execution Trace    |
               |  (Steps, Tools, Latency)    |
               +-----------------------------+
                              |
                              v
               +-----------------------------+
               |      ExecutionAnalyzer      |
               +-----------------------------+
                              |
                              v
               +-----------------------------+
               |      ReflectionEngine       |
               | (What worked/failed, root)  |
               +-----------------------------+
                              |
                              v
               +-----------------------------+
               |      LearningValidator      |
               | (Secret Masking, Duplicate  |
               |  Detection, Contradictions) |
               +-----------------------------+
                              |
                              v
               +-----------------------------+
               |   AdaptiveLearningManager   |
               +-----------------------------+
                   /          |           \
                  v           v            v
          +------------+ +------------+ +------------+
          | Long-Term  | | Knowledge  | |   Task     |
          |  Memory    | |   Graph    | |  Planner   |
          | (AGENT_    | | (TASK->    | |  Adaptive  |
          |  LEARNING) | |  TECH/     | |  Guidance  |
          |            | |  CONCEPT)  | |            |
          +------------+ +------------+ +------------+
```

---

## 3. Learning Categories (`LearningCategory`)
1. **`SUCCESSFUL_WORKFLOW`**: Proven sequence of actions and tools for achieving a recurring goal.
2. **`FAILED_WORKFLOW`**: Identified anti-pattern, failure mode, or invalid approach to avoid.
3. **`TOOL_SELECTION_PATTERN`**: Contextual recommendation on which tool is best suited for specific arguments/environments.
4. **`RECOVERY_STRATEGY`**: Recovery actions to apply when a step or tool encounters a specific error.
5. **`PLANNING_IMPROVEMENT`**: Guidance on simplifying over-engineered plans or resolving bottlenecks.
6. **`EXECUTION_CONSTRAINT`**: Environmental or platform limitation (e.g. rate limits, OS restrictions).

---

## 4. Safety & Grounding Boundaries
- **Zero Automatic System Mutation**: Learnings guide future planning via contextual recommendations; they **never** alter source code or system configurations autonomously.
- **Permission & Security Invariance**: Learning records **cannot** bypass permission gates, elevate privilege levels, or alter security policies.
- **Secret & Credential Masking**: Regex-based scanners sanitize API keys, bearer tokens, private keys, and passwords (`[REDACTED_SECRET]`).
- **Strict Evidence Grounding**: Speculative, ungrounded recommendations without verifiable execution evidence are automatically rejected during validation.

---

## 5. User Feedback Loop (`FeedbackType`)
Users can explicitly evaluate learned patterns:
- **`USEFUL`**: Increases confidence score (+0.1) and marks status as `REINFORCED`.
- **`NOT_USEFUL`**: Decreases confidence score (-0.25); if confidence drops below 0.4, status becomes `INVALIDATED`.
- **`CORRECTION`**: Updates recommendation text with user instructions and marks status as `REINFORCED`.
- **`PREFERRED_APPROACH`**: Overrides existing strategies with maximum priority (`importance = 1.0`, `confidence = 1.0`).
