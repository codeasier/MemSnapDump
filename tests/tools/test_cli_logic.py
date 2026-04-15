import argparse
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from memsnapdump import cli as cli_mod
from memsnapdump.tools.slice_dump import dump as slice_dump_mod
from memsnapdump.tools.adaptors import snapshot2db as snapshot2db_mod

runner = CliRunner()


def test_slice_dump_get_args_accepts_explicit_argv(tmp_path: Path):
    snapshot_file = tmp_path / "snapshot.pkl"
    snapshot_file.write_bytes(b"data")

    args = slice_dump_mod.get_args([str(snapshot_file), "--slices", "2"])

    assert args.snapshot_file == str(snapshot_file)
    assert args.slices == 2


def test_snapshot2db_get_args_accepts_explicit_argv(tmp_path: Path):
    snapshot_file = tmp_path / "snapshot.pkl"
    snapshot_file.write_bytes(b"data")

    args = snapshot2db_mod.get_args([str(snapshot_file), "--device", "0"])

    assert args.snapshot_file == str(snapshot_file)
    assert args.device == 0


def test_root_cli_shows_version():
    result = runner.invoke(cli_mod.app, ["--version"])

    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_root_cli_split_help_shows_real_options():
    result = runner.invoke(cli_mod.app, ["split", "--help"])

    assert result.exit_code == 0
    assert "snapshot_file" in result.stdout
    assert "--device" in result.stdout
    assert "--slices" in result.stdout
    assert "--max-entries" in result.stdout
    assert "--dump-dir" in result.stdout
    assert "--dump-type" in result.stdout


def test_root_cli_dump2db_help_shows_real_options():
    result = runner.invoke(cli_mod.app, ["dump2db", "--help"])

    assert result.exit_code == 0
    assert "snapshot_file" in result.stdout
    assert "--device" in result.stdout
    assert "--dump-dir" in result.stdout
    assert "--log" in result.stdout


def test_root_cli_dispatches_split(monkeypatch):
    captured = {}

    def fake_run_slice_dump(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(cli_mod, "run_slice_dump", fake_run_slice_dump)

    result = runner.invoke(cli_mod.app, ["split", "snapshot.pkl", "--slices", "2"])

    assert result.exit_code == 0
    assert captured["snapshot_file"] == "snapshot.pkl"
    assert captured["slices"] == 2


def test_root_cli_dispatches_dump2db(monkeypatch):
    captured = {}

    def fake_run_dump_to_db(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(cli_mod, "run_dump_to_db", fake_run_dump_to_db)

    result = runner.invoke(cli_mod.app, ["dump2db", "snapshot.pkl", "--device", "0"])

    assert result.exit_code == 0
    assert captured["snapshot_file"] == "snapshot.pkl"
    assert captured["device"] == 0


def test_slice_dump_get_args_uses_snapshot_parent_as_default_dump_dir(
    monkeypatch, tmp_path: Path
):
    snapshot_file = tmp_path / "snapshot.pkl"
    snapshot_file.write_bytes(b"data")
    monkeypatch.setattr(
        "sys.argv",
        ["slice_dump", str(snapshot_file)],
    )

    args = slice_dump_mod.get_args()

    assert args.snapshot_file == str(snapshot_file)
    assert Path(args.dump_dir) == tmp_path
    assert args.device == 0
    assert args.slices == 4
    assert args.dump_type == "pkl"


def test_slice_dump_get_args_rejects_missing_snapshot(monkeypatch, tmp_path: Path):
    missing = tmp_path / "missing.pkl"
    monkeypatch.setattr("sys.argv", ["slice_dump", str(missing)])

    with pytest.raises(argparse.ArgumentError):
        slice_dump_mod.get_args()


def test_run_slice_dump_returns_early_when_trace_data_missing(
    monkeypatch, tmp_path: Path
):
    snapshot_file = tmp_path / "snapshot.pkl"
    snapshot_file.write_bytes(b"data")
    monkeypatch.setattr(
        slice_dump_mod, "load_pickle_to_dict", lambda path: {"segments": []}
    )

    constructed = {"value": False}

    class FakeSnapshot:
        def __init__(self, *_args, **_kwargs):
            constructed["value"] = True

    monkeypatch.setattr(slice_dump_mod, "SimulateDeviceSnapshot", FakeSnapshot)

    slice_dump_mod.run_slice_dump(
        snapshot_file=str(snapshot_file),
        device=0,
        slices=4,
        max_entries=15000,
        dump_dir=str(tmp_path),
        dump_type="pkl",
    )

    assert constructed["value"] is False


def test_run_slice_dump_happy_path_constructs_snapshot_and_replays(
    monkeypatch, tmp_path: Path
):
    snapshot_file = tmp_path / "snapshot.pkl"
    snapshot_file.write_bytes(b"data")
    payload = {"segments": [1, 2], "device_traces": [[{"idx": 1}]]}
    monkeypatch.setattr(slice_dump_mod, "load_pickle_to_dict", lambda path: payload)

    state = {"hooker_args": None, "registered": None, "replayed": False}

    class FakeHooker:
        def __init__(self, dump_dir, num_of_slices, max_entries, dump_type):
            state["hooker_args"] = (dump_dir, num_of_slices, max_entries, dump_type)

    class FakeSnapshot:
        def __init__(self, df, device):
            assert df is payload
            assert device == 0
            self.hooker = None

        def register_hooker(self, hooker):
            state["registered"] = hooker

        def replay(self):
            state["replayed"] = True
            return True

    monkeypatch.setattr(slice_dump_mod, "SliceDumpHooker", FakeHooker)
    monkeypatch.setattr(slice_dump_mod, "SimulateDeviceSnapshot", FakeSnapshot)

    slice_dump_mod.run_slice_dump(
        snapshot_file=str(snapshot_file),
        device=0,
        slices=2,
        max_entries=10,
        dump_dir=str(tmp_path),
        dump_type="json",
    )

    assert state["hooker_args"] == (str(tmp_path), 2, 10, "json")
    assert state["registered"] is not None
    assert state["replayed"] is True


def test_snapshot2db_get_args_uses_snapshot_parent_as_default_dump_dir(
    monkeypatch, tmp_path: Path
):
    snapshot_file = tmp_path / "snapshot.pkl"
    snapshot_file.write_bytes(b"data")
    monkeypatch.setattr("sys.argv", ["dump2db", str(snapshot_file)])

    args = snapshot2db_mod.get_args()

    assert args.snapshot_file == str(snapshot_file)
    assert Path(args.dump_dir) == tmp_path
    assert args.device is None


def test_run_dump_to_db_returns_success_when_dump_succeeds(
    monkeypatch, tmp_path: Path
):
    snapshot_file = tmp_path / "snapshot.pkl"
    snapshot_file.write_bytes(b"data")
    monkeypatch.setattr(snapshot2db_mod, "dump", lambda *a, **k: True)

    result = snapshot2db_mod.run_dump_to_db(
        snapshot_file=str(snapshot_file),
        dump_dir=str(tmp_path),
        device=0,
        log_file="",
    )

    assert result is True


def test_run_dump_to_db_returns_failed_when_dump_fails(
    monkeypatch, tmp_path: Path
):
    snapshot_file = tmp_path / "snapshot.pkl"
    snapshot_file.write_bytes(b"data")
    monkeypatch.setattr(snapshot2db_mod, "dump", lambda *a, **k: False)

    result = snapshot2db_mod.run_dump_to_db(
        snapshot_file=str(snapshot_file),
        dump_dir=str(tmp_path),
        device=0,
        log_file="",
    )

    assert result is False


def test_snapshot2db_main_exits_success_when_dump_succeeds(monkeypatch, tmp_path: Path):
    args = SimpleNamespace(
        snapshot_file=str(tmp_path / "snapshot.pkl"),
        dump_dir=str(tmp_path),
        log="",
        device=0,
    )
    monkeypatch.setattr(snapshot2db_mod, "get_args", lambda argv=None: args)
    monkeypatch.setattr(snapshot2db_mod, "run_dump_to_db", lambda **kwargs: True)

    with pytest.raises(SystemExit) as exc:
        snapshot2db_mod.main()

    assert exc.value.code == snapshot2db_mod.ExistCode.SUCCESS


def test_snapshot2db_main_exits_failed_when_dump_fails(monkeypatch, tmp_path: Path):
    args = SimpleNamespace(
        snapshot_file=str(tmp_path / "snapshot.pkl"),
        dump_dir=str(tmp_path),
        log="",
        device=0,
    )
    monkeypatch.setattr(snapshot2db_mod, "get_args", lambda argv=None: args)
    monkeypatch.setattr(snapshot2db_mod, "run_dump_to_db", lambda **kwargs: False)

    with pytest.raises(SystemExit) as exc:
        snapshot2db_mod.main()

    assert exc.value.code == snapshot2db_mod.ExistCode.FAILED


def test_snapshot2db_main_exits_failed_on_argument_error(monkeypatch):
    parser = argparse.ArgumentParser()
    action = parser.add_argument("snapshot_file")

    def raise_error(argv=None):
        raise argparse.ArgumentError(action, "bad args")

    monkeypatch.setattr(snapshot2db_mod, "get_args", raise_error)

    with pytest.raises(SystemExit) as exc:
        snapshot2db_mod.main()

    assert exc.value.code == snapshot2db_mod.ExistCode.FAILED
