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


def test_pyproject_registers_memsnapdump_console_script():
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")

    assert "[project.scripts]" in content
    assert 'memsnapdump = "memsnapdump.cli:main"' in content


def test_pyproject_declares_typer_dependency():
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")

    assert '"typer>=' in content or '"typer"' in content


def test_root_cli_module_help_runs():
    result = _run_module_help("memsnapdump.cli")
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()
    assert "split" in result.stdout
    assert "dump2db" in result.stdout


def test_root_cli_module_short_help_runs():
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        SRC_DIR if not env.get("PYTHONPATH") else f"{SRC_DIR}:{env['PYTHONPATH']}"
    )
    result = subprocess.run(
        [sys.executable, "-m", "memsnapdump.cli", "-h"],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_root_cli_module_version_runs():
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        SRC_DIR if not env.get("PYTHONPATH") else f"{SRC_DIR}:{env['PYTHONPATH']}"
    )
    result = subprocess.run(
        [sys.executable, "-m", "memsnapdump.cli", "--version"],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "0.1.0" in result.stdout


def test_root_cli_module_split_help_runs():
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        SRC_DIR if not env.get("PYTHONPATH") else f"{SRC_DIR}:{env['PYTHONPATH']}"
    )
    result = subprocess.run(
        [sys.executable, "-m", "memsnapdump.cli", "split", "--help"],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "snapshot_file" in result.stdout
    assert "--device" in result.stdout
    assert "--slices" in result.stdout
    assert "--max-entries" in result.stdout
    assert "--dump-dir" in result.stdout
    assert "--dump-type" in result.stdout


def test_root_cli_module_split_short_help_runs():
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        SRC_DIR if not env.get("PYTHONPATH") else f"{SRC_DIR}:{env['PYTHONPATH']}"
    )
    result = subprocess.run(
        [sys.executable, "-m", "memsnapdump.cli", "split", "-h"],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "snapshot_file" in result.stdout
    assert "--device" in result.stdout


def test_root_cli_module_dump2db_help_shows_real_options():
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        SRC_DIR if not env.get("PYTHONPATH") else f"{SRC_DIR}:{env['PYTHONPATH']}"
    )
    result = subprocess.run(
        [sys.executable, "-m", "memsnapdump.cli", "dump2db", "--help"],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "snapshot_file" in result.stdout
    assert "--device" in result.stdout
    assert "--dump-dir" in result.stdout
    assert "--log" in result.stdout


def test_root_cli_module_dump2db_short_help_runs():
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        SRC_DIR if not env.get("PYTHONPATH") else f"{SRC_DIR}:{env['PYTHONPATH']}"
    )
    result = subprocess.run(
        [sys.executable, "-m", "memsnapdump.cli", "dump2db", "-h"],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "snapshot_file" in result.stdout
    assert "--log" in result.stdout


def test_split_module_help_runs():
    result = _run_module_help("memsnapdump.tools.split")
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_dump2db_module_help_runs():
    result = _run_module_help("memsnapdump.tools.dump2db")
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()
