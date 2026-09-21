# Kora LLM Gateway & Model Integration Specification (V1)

## Architecture Overview

Kora implements a capability-routed LLM Gateway that strictly isolates all model identifiers and API credentials to the backend configuration and Model Registry.

```
Flutter Desktop Client
       │
       ▼ (HTTP / WebSocket)
FastAPI Backend (apps/agent/api)
       │
       ▼
Agent Core (DecisionEngine / Planner / Session)
       │
       ▼
Model Router (core/model_router.py)
       │
       ▼
Model Registry (models/registry.yaml)
       │
       ▼
LLM Gateway (models/providers/huggingface.py)
       │
       ▼
Hugging Face Inference API / Hosted Models
```

---

## Model Registry Roles & Configurations

Model IDs exist **only** in `apps/agent/models/registry.yaml`. Agent components and frontend clients never reference concrete model IDs directly; they route exclusively by capability tags (`chat`, `reason`, `code`, `vision`, `audio`, `embedding`).

| Capability Tag | Model Name | Hugging Face Model ID | Context Window |
|---|---|---|---|
| `chat` | `qwen-chat` | `Qwen/Qwen3-4B-Instruct-2507` | 32,768 tokens |
| `reason` | `qwen-reason` | `Qwen/Qwen3-30B-A3B-Instruct-2507` | 32,768 tokens |
| `code` | `qwen-code` | `Qwen/Qwen3-Coder-30B-A3B-Instruct` | 32,768 tokens |
| `vision` | `gemma-vision` | `google/gemma-4-E4B-it` | 131,072 tokens |
| `audio` | `gemma-audio` | `google/gemma-4-E4B-it` | 32,768 tokens |
| `embedding` | `embed-model` | `BAAI/bge-m3` | 8,192 tokens (dim: 1024) |
| *(internal)* | `reranker-model` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | 512 tokens |

---

## LLM Gateway Capabilities

The `HuggingFaceProvider` (`apps/agent/models/providers/huggingface.py`) delivers:

1. **OpenAI-Compatible Chat Completion**:
   - Primary endpoint: `/models/{model_id}/v1/chat/completions`
   - Non-streaming completion returning `GenerationResult` (full text, prompt tokens, completion tokens, latency).

2. **Server-Sent Events (SSE) Streaming**:
   - `chat_stream(model_id, messages)` parses live SSE stream chunks (`data: {"choices": [{"delta": {"content": "..."}}]}`) and yields individual token deltas in real time.
   - Handles `data: [DONE]` stream termination cleanly.

3. **Feature Extraction (Embeddings)**:
   - Endpoint: `/pipeline/feature-extraction/{model_id}` with mean pooling for multi-dimensional embeddings.

4. **Resilience & Backoff Retries**:
   - Automatic retry with exponential backoff on HTTP 429 (Rate Limits) and HTTP 503 (Model Loading).
   - Configurable request timeout (default: 60s) with `LLMTimeoutError`.

5. **Structured Error Hierarchy**:
   - `LLMError`: Base exception
   - `LLMAuthError`: 401 / 403 Authentication failures
   - `LLMRateLimitError`: 429 Quota / Rate limit exceedance
   - `LLMModelUnavailableError`: 503 Model loading / unavailable
   - `LLMTimeoutError`: Request timeout

6. **Token Safety & Security**:
   - API tokens are read from environment variable `KORA_HUGGINGFACE_API_TOKEN`.
   - Never exposed over REST or WebSocket payloads to the Flutter frontend.
   - Never logged in logs, stack traces, or exception messages.

---

## Selective Context Retrieval Pipeline

Retrieval is context-aware and governed by `IntentAnalyzer`:
- Standard conversation: No RAG / Web research invoked.
- Project / Code queries: Triggers RAG retrieval from vector store.
- External / Current queries: Triggers DuckDuckGo web research.
- User profile / preferences: Triggers Memory retrieval.
- Results are assembled into a bounded `AgentContextPackage` before passing to `ActionType.MODEL_GENERATE`.
