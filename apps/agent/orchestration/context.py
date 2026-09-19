"""
orchestration.context — Context Isolation for Specialized Sub-Agents (V16)

Guarantees strict context scoping so sub-agents receive only the precise slice
of project context, memory, and dependency data necessary for their specific objective.
Prevents leaking unrelated project secrets, sensitive user preferences, or broad context.
"""

from __future__ import annotations

from typing import Any

from orchestration.types import AgentType


class ContextIsolator:
    """
    Filters and bounds global context packages per sub-agent based on agent capabilities.
    """

    @staticmethod
    def isolate(
        agent_type: AgentType,
        objective: str,
        global_context: dict[str, Any] | None = None,
        dependency_outputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Produce an isolated sub-context package tailored for a specific sub-agent.
        """
        g_ctx = global_context or {}
        deps = dependency_outputs or {}

        isolated: dict[str, Any] = {
            "objective": objective,
            "agent_type": agent_type.value,
            "dependency_outputs": deps,
        }

        # Project ID scope
        if "project_id" in g_ctx:
            isolated["project_id"] = g_ctx["project_id"]

        # Scope context specifically per agent type
        if agent_type == AgentType.RESEARCH_AGENT:
            # Only external research queries and upstream factual hints
            isolated["search_hints"] = g_ctx.get("search_hints", [])
            isolated["target_domains"] = g_ctx.get("target_domains", [])

        elif agent_type == AgentType.CODING_AGENT:
            # Code snippets, targeted file paths, language tags
            isolated["relevant_files"] = g_ctx.get("relevant_files", [])
            isolated["code_context"] = g_ctx.get("code_context", "")
            isolated["language"] = g_ctx.get("language", "python")

        elif agent_type == AgentType.DATA_AGENT:
            # Structured tables, CSV snippets, SQL dialect
            isolated["data_tables"] = g_ctx.get("data_tables", [])
            isolated["schema_info"] = g_ctx.get("schema_info", {})

        elif agent_type == AgentType.BROWSER_AGENT:
            # Target URL and automation instructions
            isolated["target_url"] = g_ctx.get("target_url", "")
            isolated["actions_list"] = g_ctx.get("actions_list", [])

        elif agent_type == AgentType.DOCUMENT_AGENT:
            # Document chunks and RAG references
            isolated["document_ids"] = g_ctx.get("document_ids", [])
            isolated["rag_chunks"] = g_ctx.get("rag_chunks", [])

        else:  # GENERAL_TASK_AGENT / Default
            isolated["task_params"] = g_ctx.get("task_params", {})

        return isolated
