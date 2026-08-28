from __future__ import annotations

import hashlib
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from test_agent.planner import TestPlan


@dataclass
class ValidationResult:
    valid: bool
    sha256: str
    errors: list[str]
    lint_passed: bool
    parse_passed: bool
    test_passed: bool | None


class SandboxValidator:
    """Validates generated test patches in a locked-down sandbox."""

    def validate(
        self,
        code: str,
        framework: str = "pytest",
        language: str = "python",
    ) -> ValidationResult:
        sha256 = hashlib.sha256(code.encode()).hexdigest()
        errors: list[str] = []

        parse_passed = self._validate_parse(code, language)
        if not parse_passed:
            errors.append("Code failed to parse")

        lint_passed = self._validate_lint(code, language)
        if not lint_passed:
            errors.append("Code failed linting")

        test_passed = None
        if parse_passed and lint_passed:
            test_passed = self._run_test(code, framework, language)
            if test_passed is False:
                errors.append("Test execution failed in sandbox")

        return ValidationResult(
            valid=parse_passed and lint_passed and (test_passed is not False),
            sha256=sha256,
            errors=errors,
            lint_passed=lint_passed,
            parse_passed=parse_passed,
            test_passed=test_passed,
        )

    def _validate_parse(self, code: str, language: str) -> bool:
        if language == "python":
            try:
                import ast
                tree = ast.parse(code)
                forbidden_modules = {"os", "sys", "subprocess", "socket", "urllib", "requests", "httpx", "shutil", "importlib", "ctypes"}
                forbidden_funcs = {"eval", "exec", "__import__", "compile", "open"}

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name.split('.')[0] in forbidden_modules:
                                return False
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and node.module.split('.')[0] in forbidden_modules:
                            return False
                    elif isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id in forbidden_funcs:
                            return False
                return True
            except SyntaxError:
                return False
        return True

    def _validate_lint(self, code: str, language: str) -> bool:
        if language != "python":
            return True
        import sys
        try:
            with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
                f.write(code)
                f.flush()
                result = subprocess.run(
                    [sys.executable, "-m", "py_compile", f.name],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return result.returncode == 0
        except Exception:
            return False
        finally:
            try:
                Path(f.name).unlink(missing_ok=True)
            except Exception:
                pass

    def _run_test(self, code: str, framework: str, language: str) -> bool | None:
        if framework != "pytest" or language != "python":
            return None

        import os
        import sys
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                test_file = Path(tmpdir) / "test_sandbox.py"
                test_file.write_text(code, encoding="utf-8")

                use_docker = os.environ.get("SANDBOX_USE_DOCKER", "false").lower() == "true"
                if use_docker:
                    docker_cmd = [
                        "docker", "run", "--rm",
                        "--network", "none",
                        "--read-only",
                        "--cap-drop=ALL",
                        "--memory=512m",
                        "--cpus=1.0",
                        "-v", f"{tmpdir}:/workspace:ro",
                        "-w", "/workspace",
                        "python:3.12-slim",
                        "python", "-m", "pytest", "test_sandbox.py", "--tb=short", "-q"
                    ]
                    result = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=20)
                    return result.returncode == 0

                safe_env = dict(os.environ)
                safe_env.update({
                    "HOME": tmpdir,
                    "TMPDIR": tmpdir,
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONUNBUFFERED": "1",
                    "NO_NETWORK": "1",
                })

                user_arg = "nobody" if hasattr(os, "geteuid") and os.geteuid() == 0 else None

                cmd = [
                    sys.executable, "-m", "pytest", str(test_file), "--tb=short", "-q",
                    "-p", "no:cacheprovider",
                    "--basetemp", str(Path(tmpdir) / "pytest"),
                ]



                kwargs = {
                    "capture_output": True,
                    "text": True,
                    "timeout": 15,
                    "env": safe_env,
                    "cwd": tmpdir,
                }
                if user_arg:
                    kwargs["user"] = user_arg

                result = subprocess.run(cmd, **kwargs)
                return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
        except Exception:
            return False
