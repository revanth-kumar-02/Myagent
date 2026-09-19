"""
orchestration.registry — Specialized Agent Profiles & Capabilities (V16)

Registers and validates specialized sub-agent definitions:
  - Research Agent
  - Coding Agent
  - Data Agent
  - Browser Agent
  - Document Agent
  - General Task Agent

Enforces capability constraints, allowed tools, permitted models, and permission boundaries.
"""

from __future__ import annotations

from orchestration.types import AgentProfile, AgentType


class AgentRegistry:
    """
    Central registry for specialized sub-agent profiles.
    """

    def __init__(self) -> None:
        self._profiles: dict[AgentType, AgentProfile] = {}
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        """Register Kora's standard specialized agent fleet."""
        # 1. Research Agent
        self.register_profile(
            AgentProfile(
                agent_type=AgentType.RESEARCH_AGENT,
                name="Research Specialist",
                description="Performs focused web research, source extraction, and factual verification via DuckDuckGo.",
                capabilities=["web_search", "evidence_extraction", "fact_checking", "summarization"],
                allowed_tools=["duckduckgo_search", "fetch_page", "extract_evidence"],
                allowed_models=["qwen-chat", "qwen-reason"],
                permission_limits=["normal"],
                max_concurrency=3,
                system_prompt="You are Kora's Research Agent. Gather accurate, non-hallucinatory information with clear citations.",
            )
        )

        # 2. Coding Agent
        self.register_profile(
            AgentProfile(
                agent_type=AgentType.CODING_AGENT,
                name="Coding Specialist",
                description="Writes, reviews, analyzes, refactors, and tests source code.",
                capabilities=["code_generation", "ast_analysis", "syntax_check", "git_operations", "debugging"],
                allowed_tools=["file_read", "file_write", "create_file", "run_terminal_command", "git_status", "git_diff"],
                allowed_models=["qwen-code", "qwen-reason"],
                permission_limits=["sensitive"],
                max_concurrency=2,
                system_prompt="You are Kora's Coding Agent. Produce clean, idiomatic, well-tested code following best practices.",
            )
        )

        # 3. Data Agent
        self.register_profile(
            AgentProfile(
                agent_type=AgentType.DATA_AGENT,
                name="Data Specialist",
                description="Processes structured data formats, CSVs, JSON datasets, and executes database queries.",
                capabilities=["data_analysis", "csv_parsing", "json_transformation", "sql_query"],
                allowed_tools=["read_file", "parse_csv", "query_database"],
                allowed_models=["qwen-code", "qwen-reason", "qwen-chat"],
                permission_limits=["normal"],
                max_concurrency=2,
                system_prompt="You are Kora's Data Agent. Analyze and transform structured data with statistical accuracy.",
            )
        )

        # 4. Browser Agent
        self.register_profile(
            AgentProfile(
                agent_type=AgentType.BROWSER_AGENT,
                name="Browser Automation Specialist",
                description="Interacts with web pages, performs multi-step form navigation and visual inspection via Playwright.",
                capabilities=["web_navigation", "form_filling", "screenshot_capture", "visual_inspection"],
                allowed_tools=["browser_navigate", "browser_click", "browser_type", "browser_screenshot"],
                allowed_models=["gemma-vision", "qwen-chat"],
                permission_limits=["sensitive"],
                max_concurrency=1,
                system_prompt="You are Kora's Browser Agent. Automate web workflows safely with precise DOM actions.",
            )
        )

        # 5. Document Agent
        self.register_profile(
            AgentProfile(
                agent_type=AgentType.DOCUMENT_AGENT,
                name="Document & RAG Specialist",
                description="Extracts and analyzes information from PDFs, Word docs, Markdown files, and the local RAG index.",
                capabilities=["pdf_extraction", "document_chunking", "rag_retrieval", "cross_referencing"],
                allowed_tools=["rag_retrieve", "read_file", "parse_pdf", "parse_docx"],
                allowed_models=["qwen-chat", "qwen-reason"],
                permission_limits=["normal"],
                max_concurrency=2,
                system_prompt="You are Kora's Document Agent. Retrieve and synthesize grounded answers from documents.",
            )
        )

        # 6. General Task Agent
        self.register_profile(
            AgentProfile(
                agent_type=AgentType.GENERAL_TASK_AGENT,
                name="General Task Specialist",
                description="Handles generic reasoning, step execution, formatting, and routine sub-tasks.",
                capabilities=["general_reasoning", "formatting", "calculation", "step_execution"],
                allowed_tools=["file_read", "system_info", "calculator"],
                allowed_models=["qwen-chat"],
                permission_limits=["normal"],
                max_concurrency=4,
                system_prompt="You are Kora's General Task Agent. Fulfill specific sub-task instructions directly.",
            )
        )

    def register_profile(self, profile: AgentProfile) -> None:
        """Register or override an agent profile."""
        self._profiles[profile.agent_type] = profile

    def get_profile(self, agent_type: AgentType | str) -> AgentProfile | None:
        """Get agent profile by type."""
        if isinstance(agent_type, str):
            try:
                agent_type = AgentType(agent_type)
            except ValueError:
                return None
        return self._profiles.get(agent_type)

    def list_profiles(self) -> list[AgentProfile]:
        """List all registered agent profiles."""
        return list(self._profiles.values())

    def validate_tool_allowed(self, agent_type: AgentType, tool_name: str) -> bool:
        """Check if a tool is permitted for a given agent type."""
        profile = self.get_profile(agent_type)
        if not profile:
            return False
        return tool_name in profile.allowed_tools

    def validate_model_allowed(self, agent_type: AgentType, model_id: str) -> bool:
        """Check if a model is permitted for a given agent type."""
        profile = self.get_profile(agent_type)
        if not profile:
            return False
        return model_id in profile.allowed_models
