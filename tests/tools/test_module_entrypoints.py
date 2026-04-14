import importlib
import runpy


def test_split_module_import_exposes_slice_dump():
    split_module = importlib.import_module("memsnapdump.tools.split")

    assert callable(split_module.slice_dump)


def test_dump2db_module_import_exposes_main():
    dump2db_module = importlib.import_module("memsnapdump.tools.dump2db")

    assert callable(dump2db_module.main)


def test_split_module_main_path_invokes_slice_dump(monkeypatch):
    called = {"value": False}

    def fake_slice_dump():
        called["value"] = True

    monkeypatch.setattr("memsnapdump.tools.slice_dump.slice_dump", fake_slice_dump)

    runpy.run_module("memsnapdump.tools.split", run_name="__main__")

    assert called["value"] is True


def test_dump2db_module_main_path_invokes_main(monkeypatch):
    called = {"value": False}

    def fake_main():
        called["value"] = True

    monkeypatch.setattr("memsnapdump.tools.adaptors.snapshot2db.main", fake_main)

    runpy.run_module("memsnapdump.tools.dump2db", run_name="__main__")

    assert called["value"] is True
