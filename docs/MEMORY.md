# Kora Long-Term Memory & Knowledge System

Kora features an autonomous, self-maintaining memory and knowledge subsystem.

---

## 1. Core Architecture

```
User Turn / Workspace Event
           │
           ▼
Candidate Detection & Extraction
(Filters trivial chatter, detects preferences, facts, corrections)
           │
           ▼
Validation & Secret Protection
(Enforces length bounds, strips secrets / private keys)
           │
           ▼
Semantic Embedding & Conflict Resolution
(1024-dim embedding, checks contradictions and supersedes stale entries)
           │
           ▼
Dual Persistence (PostgreSQL + In-Memory Cache)
(Stored in agent_memory with vector index for fast similarity lookups)
           │
           ▼
Context Injection
(Injected into agent prompt when relevant to query)
```

---

## 2. Memory Types & Lifecycle

### Memory Types
- `user_preference`: Coding styles, preferred libraries, communication tone.
- `user_profile_context`: Developer background, hardware environment, timezone.
- `project_context`: Repository architectural patterns, team conventions.
- `task_context`: Long-running multi-step task states.
- `agent_learning`: Learned bug fixes, test corrections, operational insights.
- `decision`: Explicit decisions agreed upon with the user.
- `workflow_pattern`: Preferred git flows, testing workflows, deployment procedures.

### Lifecycle Statuses
- `active`: Available for semantic retrieval and prompt augmentation.
- `archived`: Manually or automatically archived.
- `expired`: Time-to-live expiration reached.
- `superseded`: Replaced by newer contradictory memory record.

---

## 3. Desktop UI Integration

The Flutter desktop app provides a transparent **Memory & Knowledge** screen:
- Automatic presentation of learned memories categorized by type.
- User controls to **Forget** (permanent deletion) or **Correct / Edit** memory contents.
- Real-time statistics on total, active, and superseded memories.
