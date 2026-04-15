import json
from pathlib import Path

import pytest

from memsnapdump.base import DeviceSnapshot, TraceEntry
from memsnapdump.tools.slice_dump.hooker import SliceDumpHooker


def make_snapshot(entries_count: int):
    snapshot = DeviceSnapshot()
    snapshot.device = 0
    snapshot.segments = []
    snapshot.trace_entries = [TraceEntry(action="alloc", addr=i, size=1, stream=0, idx=i) for i in range(entries_count)]
    return snapshot


def test_slice_dump_hooker_rejects_invalid_directory(tmp_path: Path):
    with pytest.raises(ValueError):
        SliceDumpHooker(str(tmp_path / "missing"), num_of_slices=1)


def test_slice_dump_hooker_init_strategy_adjusts_num_slices_and_max_entries(tmp_path: Path):
    hooker = SliceDumpHooker(str(tmp_path), num_of_slices=2, max_entries=3)
    hooker.num_of_events = 10

    hooker._init_splitting_strategy()

    assert hooker.max_entries == 3
    assert hooker.num_of_slices == 4


def test_slice_dump_hooker_dump_json_writes_file(tmp_path: Path):
    hooker = SliceDumpHooker(str(tmp_path), num_of_slices=2, max_entries=2, dump_type="json")
    hooker.num_of_events = 4
    hooker.prev_segments = []
    hooker.events_buffer = [TraceEntry(action="alloc", addr=1, size=2, stream=0, idx=1)]

    hooker.dump(device=0)

    outputs = list(tmp_path.glob("*.json"))
    assert len(outputs) == 1
    payload = json.loads(outputs[0].read_text(encoding="utf-8"))
    assert "device_traces" in payload


def test_slice_dump_hooker_post_undo_event_resets_buffers_after_dump(tmp_path: Path):
    hooker = SliceDumpHooker(str(tmp_path), num_of_slices=1, max_entries=1)
    hooker.num_of_events = 1
    hooker.prev_segments = []
    snapshot = make_snapshot(0)
    event = TraceEntry(action="alloc", addr=1, size=2, stream=0, idx=1)

    hooker.post_undo_event(event, snapshot)

    assert hooker.events_buffer == []
    assert hooker.dump_count == 1
