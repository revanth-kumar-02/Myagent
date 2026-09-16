import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class TriggerEvaluator:
    @staticmethod
    def evaluate_condition(condition_expr: str, context: Dict[str, Any]) -> bool:
        """Evaluates boolean condition expressions safely against execution context."""
        if not condition_expr:
            return True
        
        expr_lower = condition_expr.lower().strip()
        
        task_status = str(context.get("task_status", "")).lower()
        task_result = str(context.get("task_result", "")).lower()
        step_result = str(context.get("step_result", "")).lower()

        has_failure = "fail" in task_status or "error" in task_status or "fail" in task_result or "fail" in step_result or "error" in task_result or "error" in step_result

        if "fail" in expr_lower or "error" in expr_lower:
            return has_failure
        if "pass" in expr_lower or "success" in expr_lower:
            return not has_failure and ("completed" in task_status or "success" in task_result or "pass" in step_result or "pass" in task_result or "passed" in task_result)
        if "git_dirty" in expr_lower:
            return bool(context.get("git_dirty", False))

        return True

    @staticmethod
    def check_file_change(path: str, last_checked_mtime: Optional[float] = None) -> tuple[bool, float]:
        """Checks if files under path have changed since last_checked_mtime."""
        if not os.path.exists(path):
            return False, last_checked_mtime or 0.0

        current_max_mtime = 0.0
        try:
            p = Path(path)
            if p.is_file():
                current_max_mtime = p.stat().st_mtime
            elif p.is_dir():
                for root, dirs, files in os.walk(path):
                    if any(ignored in root for ignored in [".git", "node_modules", ".venv", "__pycache__"]):
                        continue
                    for f in files:
                        fp = os.path.join(root, f)
                        try:
                            mtime = os.stat(fp).st_mtime
                            if mtime > current_max_mtime:
                                current_max_mtime = mtime
                        except Exception:
                            continue
        except Exception as e:
            logger.warning(f"Error checking file mtime for {path}: {e}")

        if last_checked_mtime is None:
            return False, current_max_mtime

        has_changed = current_max_mtime > last_checked_mtime
        return has_changed, current_max_mtime

trigger_evaluator = TriggerEvaluator()
