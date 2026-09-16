import os
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from core.tools.registry import tool_registry

logger = logging.getLogger(__name__)

class ValidationResult(BaseModel):
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

class PlanValidator:
    """
    Strict Plan Validator for Cocoa Agent.
    Verifies tools, parameters, dependency IDs, cycle freedom, workspace boundaries, timeouts, and retry limits.
    """

    def __init__(self, authorized_roots: Optional[List[str]] = None):
        self.authorized_roots = authorized_roots or [os.getcwd()]

    def set_authorized_roots(self, roots: List[str]):
        self.authorized_roots = [os.path.abspath(r) for r in roots]

    def validate_plan(self, plan: Any, project_id: Optional[str] = None) -> ValidationResult:
        errors = []
        warnings = []

        if not hasattr(plan, "steps") or not plan.steps:
            return ValidationResult(valid=False, errors=["Plan contains no steps."])

        step_ids = {s.id for s in plan.steps}

        # 1. Step ID & Dependency Checks
        for step in plan.steps:
            # Tool validity
            tool_name = getattr(step, "tool", None)
            if tool_name:
                available_tools = tool_registry.list_tools()
                valid_tools = set(available_tools)
                # Also accept generic browser/scheduler aliases if supported by registry
                if tool_name not in valid_tools and tool_name not in ("browser", "web_search", "scheduler"):
                    errors.append(f"Step '{step.id}' specifies invalid tool '{tool_name}'.")

            # Dependency ID validity & self-dependency
            deps = getattr(step, "dependencies", []) or []
            for dep_id in deps:
                if dep_id not in step_ids:
                    errors.append(f"Step '{step.id}' references non-existent dependency ID '{dep_id}'.")
                if dep_id == step.id:
                    errors.append(f"Step '{step.id}' cannot depend on itself.")

            # Timeout check
            timeout = getattr(step, "timeout", 60.0)
            if timeout is not None:
                if timeout <= 0:
                    errors.append(f"Step '{step.id}' has invalid timeout {timeout}s (must be > 0).")
                elif timeout > 600:
                    errors.append(f"Step '{step.id}' timeout {timeout}s exceeds maximum limit of 600s.")

            # Retry policy check
            retry_policy = getattr(step, "retry_policy", {}) or {}
            max_retries = retry_policy.get("max_retries", 2)
            if max_retries < 0 or max_retries > 5:
                errors.append(f"Step '{step.id}' max_retries {max_retries} outside allowed range [0, 5].")

            # Arguments & Workspace boundary check
            args = getattr(step, "arguments", {}) or {}
            for path_key in ("path", "root_path", "working_directory", "source_path", "destination_path"):
                path_val = args.get(path_key)
                if path_val and isinstance(path_val, str) and "/" in path_val:
                    norm_path = os.path.abspath(path_val)
                    if self.authorized_roots:
                        is_safe = any(norm_path.startswith(root) for root in self.authorized_roots)
                        if not is_safe:
                            errors.append(f"Step '{step.id}' path '{path_val}' escapes authorized workspace boundaries {self.authorized_roots}.")

        # 2. Circular Dependency Detection (Kahn's Algorithm)
        in_degree = {s.id: 0 for s in plan.steps}
        graph = {s.id: [] for s in plan.steps}

        for step in plan.steps:
            deps = getattr(step, "dependencies", []) or []
            for dep in deps:
                if dep in graph:
                    graph[dep].append(step.id)
                    in_degree[step.id] += 1

        queue = [step_id for step_id, count in in_degree.items() if count == 0]
        visited_count = 0

        while queue:
            node = queue.pop(0)
            visited_count += 1
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited_count < len(plan.steps):
            errors.append("Circular dependency detected in execution plan graph.")

        if errors:
            logger.warning(f"Plan validation failed with {len(errors)} error(s): {errors}")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        return ValidationResult(valid=True, errors=[], warnings=warnings)

plan_validator = PlanValidator()
