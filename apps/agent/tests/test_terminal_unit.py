import os
import pytest
import asyncio
import tempfile
from core.tools.terminal import (
    CommandSafetyValidator, CommandRiskLevel, ProcessExecutor, TerminalTool
)
from core.filesystem.path_validator import PathValidator

def test_command_safety_validator():
    with tempfile.TemporaryDirectory() as tmp_dir:
        validator = PathValidator([tmp_dir])

        # SAFE
        assert CommandSafetyValidator.classify("pwd", tmp_dir, validator) == CommandRiskLevel.SAFE
        assert CommandSafetyValidator.classify("ls -la", tmp_dir, validator) == CommandRiskLevel.SAFE
        assert CommandSafetyValidator.classify("git status", tmp_dir, validator) == CommandRiskLevel.SAFE
        assert CommandSafetyValidator.classify("git diff", tmp_dir, validator) == CommandRiskLevel.SAFE
        assert CommandSafetyValidator.classify("pytest -v", tmp_dir, validator) == CommandRiskLevel.SAFE

        # REVIEW
        assert CommandSafetyValidator.classify("npm install lodash", tmp_dir, validator) == CommandRiskLevel.REVIEW
        assert CommandSafetyValidator.classify("pip install requests", tmp_dir, validator) == CommandRiskLevel.REVIEW
        assert CommandSafetyValidator.classify("git checkout main", tmp_dir, validator) == CommandRiskLevel.REVIEW

        # DANGEROUS
        assert CommandSafetyValidator.classify("rm temp.txt", tmp_dir, validator) == CommandRiskLevel.DANGEROUS
        assert CommandSafetyValidator.classify("chmod 644 file.txt", tmp_dir, validator) == CommandRiskLevel.DANGEROUS
        assert CommandSafetyValidator.classify("sudo systemctl restart nginx", tmp_dir, validator) == CommandRiskLevel.DANGEROUS

        # BLOCKED
        assert CommandSafetyValidator.classify("rm -rf /", tmp_dir, validator) == CommandRiskLevel.BLOCKED
        assert CommandSafetyValidator.classify("cat /etc/shadow", tmp_dir, validator) == CommandRiskLevel.BLOCKED
        assert CommandSafetyValidator.classify("printenv", tmp_dir, validator) == CommandRiskLevel.BLOCKED
        assert CommandSafetyValidator.classify("cat /root/secret.txt", tmp_dir, validator) == CommandRiskLevel.BLOCKED

@pytest.mark.asyncio
async def test_process_executor_sanitization_and_truncation():
    raw_secret = "Here is my token: gsk_123456789012345678901234567890 and sk-abcdef1234567890abcdef1234"
    clean = ProcessExecutor.sanitize_output(raw_secret)
    assert "gsk_••••" in clean
    assert "sk-••••" in clean
    assert "123456789012345678901234567890" not in clean

    long_output = b"A" * 100000
    truncated = ProcessExecutor.truncate_output(long_output, max_bytes=1000)
    assert "[... Output Truncated" in truncated
    assert len(truncated) < 5000
