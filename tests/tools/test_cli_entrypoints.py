import os
import subprocess
import sys
from pathlib import Path

SRC_DIR = str(Path(__file__).resolve().parents[2] / "src")


def _run_module_help(module_name: str):
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        SRC_DIR if not env.get("PYTHONPATH") else f"{SRC_DIR}:{env['PYTHONPATH']}"
    )
    return subprocess.run(
        [sys.executable, "-m", module_name, "--help"],
        capture_output=True,
        text=True,
        env=env,
    )


def test_split_module_help_runs():
    result = _run_module_help("memsnapdump.tools.split")
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_dump2db_module_help_runs():
    result = _run_module_help("memsnapdump.tools.dump2db")
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()
