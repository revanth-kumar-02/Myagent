"""
tests.agent.test_research — Web research tests (scaffold)
"""

import pytest


class TestResearchRouter:
    def test_uses_tavily_when_key_set(self) -> None:
        pytest.skip("Implement in feature phase")

    def test_falls_back_to_duckduckgo_on_tavily_error(self) -> None:
        pytest.skip("Implement in feature phase")

    def test_results_never_written_to_rag_db(self) -> None:
        """Research results must not appear in chunks table."""
        pytest.skip("Implement in feature phase")

    def test_result_schema_consistent_across_providers(self) -> None:
        pytest.skip("Implement in feature phase")
