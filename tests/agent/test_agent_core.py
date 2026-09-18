"""
tests.agent.test_agent_core — Agent core loop unit tests (scaffold)
"""

import pytest


class TestContextManager:
    def test_enforces_token_budget(self) -> None:
        pytest.skip("Implement in feature phase")

    def test_history_truncated_oldest_first(self) -> None:
        pytest.skip("Implement in feature phase")


class TestPlanner:
    def test_simple_query_produces_single_step(self) -> None:
        pytest.skip("Implement in feature phase")

    def test_multi_step_plan_ordered(self) -> None:
        pytest.skip("Implement in feature phase")


class TestVerifier:
    def test_pass_on_successful_result(self) -> None:
        pytest.skip("Implement in feature phase")

    def test_retry_on_failed_result(self) -> None:
        pytest.skip("Implement in feature phase")

    def test_escalate_after_max_retries(self) -> None:
        pytest.skip("Implement in feature phase")


class TestModelRouter:
    def test_routes_chat_capability(self) -> None:
        pytest.skip("Implement in feature phase")

    def test_raises_on_unknown_capability(self) -> None:
        pytest.skip("Implement in feature phase")

    def test_model_id_not_in_agent_code(self) -> None:
        """Ensure model IDs only exist in registry.yaml, not in Python source."""
        import subprocess, pathlib
        result = subprocess.run(
            ["grep", "-r", "Qwen/", str(pathlib.Path(__file__).parent.parent.parent / "apps/agent")],
            capture_output=True, text=True,
        )
        hits = [line for line in result.stdout.splitlines() if "registry.yaml" not in line]
        assert not hits, f"Model IDs found outside registry.yaml: {hits}"
