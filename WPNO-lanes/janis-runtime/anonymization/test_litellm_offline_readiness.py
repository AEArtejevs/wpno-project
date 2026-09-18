from pathlib import Path
import os
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
LITELLM = ROOT / "docker" / "litellm"


def test_compose_mounts_every_runtime_source_read_only():
    compose = (LITELLM / "docker-compose.yml").read_text()
    required = (
        "./config.yaml:/app/config.yaml:ro",
        "./custom_callback.py:/app/custom_callback.py:ro",
        "../../anonymization/payload_scan.py:/app/payload_scan.py:ro",
        "../../anonymization/iban_validation.py:/app/iban_validation.py:ro",
        "../../anonymization/party_names.json:/app/party_names.json:ro",
        "./tool_registry_gate.py:/app/tool_registry_gate.py:ro",
        "../../mcp/mcp.registry.json:/app/mcp.registry.json:ro",
    )
    for mount in required:
        assert mount in compose


def test_dockerfile_uses_digest_pinned_base():
    source = (LITELLM / "Dockerfile").read_text()
    first = source.splitlines()[0]
    assert first.startswith("FROM ")
    assert "@sha256:" in first
    assert len(first.rsplit("@sha256:", 1)[1]) == 64


def test_compose_renders_offline_with_placeholder_external_values(tmp_path):
    project = tmp_path / "project"
    shutil.copytree(LITELLM, project / "docker" / "litellm", symlinks=True)
    shutil.copytree(ROOT / "anonymization", project / "anonymization",
                    ignore=shutil.ignore_patterns("__pycache__", "ledger_data"))
    (project / "mcp").mkdir()
    shutil.copy2(ROOT / "mcp" / "mcp.registry.json",
                 project / "mcp" / "mcp.registry.json")
    env_file = project / "docker" / "litellm" / ".env"
    env_file.write_text(
        "ANTHROPIC_API_KEY=placeholder\nLIBRA_API_KEY=placeholder\n"
        "REDIS_HOST=redis\nLITELLM_MASTER_KEY=placeholder\n"
        "DATABASE_URL=postgresql://placeholder.invalid/db\n"
        "GATEWAY_LOG_DB_PASSWORD=placeholder\n"
    )
    result = subprocess.run(
        ["docker", "compose", "-f", str(env_file.parent / "docker-compose.yml"),
         "config", "--no-interpolate"],
        cwd=env_file.parent, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "wpno-litellm-custom:latest" in result.stdout


def test_callback_import_and_fail_closed_paths_with_runtime_stubs(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    for name in ("custom_callback.py", "tool_registry_gate.py"):
        shutil.copy2(LITELLM / name, runtime / name)
    for name in ("payload_scan.py", "iban_validation.py", "party_names.json"):
        shutil.copy2(ROOT / "anonymization" / name, runtime / name)
    shutil.copy2(ROOT / "mcp" / "mcp.registry.json", runtime / "mcp.registry.json")
    (runtime / "litellm" / "integrations").mkdir(parents=True)
    (runtime / "litellm" / "__init__.py").write_text("")
    (runtime / "litellm" / "integrations" / "__init__.py").write_text("")
    (runtime / "litellm" / "integrations" / "custom_logger.py").write_text(
        "class CustomLogger:\n    pass\n")
    (runtime / "fastapi.py").write_text(
        "class HTTPException(Exception):\n"
        "    def __init__(self, status_code, detail):\n"
        "        self.status_code = status_code\n        self.detail = detail\n")
    (runtime / "psycopg2.py").write_text("def connect(*args, **kwargs):\n    raise RuntimeError\n")
    probe = runtime / "probe.py"
    probe.write_text(
        "import asyncio\nfrom custom_callback import proxy_handler_instance\n"
        "from fastapi import HTTPException\n"
        "async def main():\n"
        "    clean = {'messages': [{'role': 'user', 'content': 'clean prose'}]}\n"
        "    assert await proxy_handler_instance.async_pre_call_hook({}, None, clean, None) == clean\n"
        "    for data, code in (({'messages':[{'content':'IBAN DE89370400440532013000'}]},451),"
        " ({'tools':[{'name':'not_registered'}]},403)):\n"
        "        try: await proxy_handler_instance.async_pre_call_hook({}, None, data, None)\n"
        "        except HTTPException as exc: assert exc.status_code == code\n"
        "        else: raise AssertionError('fail-open')\n"
        "asyncio.run(main())\n")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(runtime)
    env["WPNO_LEDGER_DIR"] = str(tmp_path / "ledger")
    result = subprocess.run(
        [sys.executable, "-B", str(probe)], cwd=runtime, env=env,
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
