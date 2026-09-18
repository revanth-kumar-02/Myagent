# Kora WebSocket Protocol — Message Specification

All client ↔ server communication uses a single persistent WebSocket connection.
Every frame is a UTF-8 JSON object conforming to the envelope below.

---

## Message Envelope

```json
{
  "id":         "<uuid-v4>",
  "type":       "<MessageType>",
  "session_id": "<uuid-v4>",
  "project_id": "<uuid-v4 | null>",
  "payload":    { },
  "ts":         1234567890123
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | UUID | ✅ | Unique per message |
| `type` | string enum | ✅ | See types below |
| `session_id` | UUID | ✅ | Conversation session |
| `project_id` | UUID or null | ✅ | Active project; null = global |
| `payload` | object | ✅ | Type-specific (may be `{}`) |
| `ts` | int (ms epoch) | ✅ | Sender wall-clock time |

---

## Message Types

### Chat

| Type | Direction | Description |
|---|---|---|
| `CHAT_REQUEST` | Client → Server | User message; initiates an agent turn |
| `CHAT_CHUNK` | Server → Client | Streaming token(s) from model |
| `CHAT_DONE` | Server → Client | Final response with sources and metadata |

#### `CHAT_REQUEST` payload
```json
{
  "message":     "string",
  "attachments": ["file_path_or_url"]
}
```

#### `CHAT_CHUNK` payload
```json
{
  "delta": "string"
}
```

#### `CHAT_DONE` payload
```json
{
  "full_text":    "string",
  "sources":      [{ "file_path": "string", "chunk_id": "uuid", "start_line": 0, "end_line": 0 }],
  "web_sources":  [{ "url": "string", "title": "string", "snippet": "string" }],
  "model_used":   "string",
  "input_tokens": 0,
  "output_tokens": 0,
  "latency_ms":   0
}
```

---

### Agent Planning

| Type | Direction | Description |
|---|---|---|
| `PLAN_UPDATE` | Server → Client | Planner step status changed |

#### `PLAN_UPDATE` payload
```json
{
  "step_index":  0,
  "step_label":  "string",
  "status":      "pending | running | done | failed"
}
```

---

### Tool Execution

| Type | Direction | Description |
|---|---|---|
| `TOOL_CALL_NOTIFY` | Server → Client | Tool about to execute |
| `TOOL_RESULT_NOTIFY` | Server → Client | Tool result (success or error) |
| `PERMISSION_REQUEST` | Server → Client | Tool needs user approval |
| `PERMISSION_RESPONSE` | Client → Server | User grants or denies approval |

#### `TOOL_CALL_NOTIFY` payload
```json
{
  "call_id":   "uuid",
  "tool_name": "string",
  "params":    { }
}
```

#### `TOOL_RESULT_NOTIFY` payload
```json
{
  "call_id":  "uuid",
  "tool_name": "string",
  "success":  true,
  "result":   { },
  "error":    "string | null"
}
```

#### `PERMISSION_REQUEST` payload
```json
{
  "request_id": "uuid",
  "tool_name":  "string",
  "action":     "string",
  "scope":      "string",
  "description": "human-readable reason"
}
```

#### `PERMISSION_RESPONSE` payload
```json
{
  "request_id": "uuid",
  "granted":    true
}
```

---

### Indexing

| Type | Direction | Description |
|---|---|---|
| `INDEX_REQUEST` | Client → Server | Start or refresh project index |
| `INDEX_PROGRESS` | Server → Client | Per-file progress update |
| `INDEX_DONE` | Server → Client | Indexing complete |
| `INDEX_ERROR` | Server → Client | Indexing failed |

#### `INDEX_REQUEST` payload
```json
{
  "project_id": "uuid",
  "root_path":  "string",
  "incremental": true
}
```

#### `INDEX_PROGRESS` payload
```json
{
  "file_path":    "string",
  "event":        "added | changed | deleted | skipped",
  "done":         42,
  "total":        100
}
```

#### `INDEX_DONE` payload
```json
{
  "project_id": "uuid",
  "files_added": 0,
  "files_changed": 0,
  "files_deleted": 0,
  "chunks_total": 0,
  "duration_ms": 0
}
```

---

### System

| Type | Direction | Description |
|---|---|---|
| `HEARTBEAT` | Both | Keep-alive ping/pong (payload: `{}`) |
| `ERROR` | Server → Client | Structured error |

#### `ERROR` payload
```json
{
  "code":    "string",
  "message": "string",
  "detail":  { }
}
```

---

## Error Codes

| Code | Meaning |
|---|---|
| `SESSION_NOT_FOUND` | Unknown session_id |
| `PROJECT_NOT_FOUND` | Unknown project_id |
| `INDEX_IN_PROGRESS` | Indexing already running for project |
| `PERMISSION_DENIED` | Tool call blocked by permission gate |
| `MODEL_UNAVAILABLE` | Requested capability has no available model |
| `RATE_LIMITED` | Provider rate limit hit |
| `INTERNAL_ERROR` | Unhandled server error |
