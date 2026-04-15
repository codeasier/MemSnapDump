from memsnapdump.base import Block, TraceEntry
from memsnapdump.tools.adaptors.database.defs import BlockFieldDefs, EventFieldDefs
from memsnapdump.tools.adaptors.database.entity2record import (
    block2record,
    event2record,
    get_timestamp_by_event_idx,
    make_default_id_counter,
)


def test_make_default_id_counter_counts_down_from_start():
    next_id = make_default_id_counter(-3)

    assert next_id() == -3
    assert next_id() == -4


def test_get_timestamp_by_event_idx_handles_none():
    assert get_timestamp_by_event_idx(None) == -1
    assert get_timestamp_by_event_idx(7) == 70


def test_event2record_uses_generated_default_id_when_missing():
    event = TraceEntry(action="alloc", addr=0x1000, size=16, stream=0, idx=None)

    record = event2record(event, allocated=1, active=2, reserved=3)

    assert record[EventFieldDefs.ID] < 0
    assert record[EventFieldDefs.ALLOCATED] == 1
    assert record[EventFieldDefs.ACTIVE] == 2
    assert record[EventFieldDefs.RESERVED] == 3


def test_block2record_uses_generated_default_id_when_missing():
    block = Block(size=16, requested_size=8, address=0x1000, state="active_allocated")

    record = block2record(block)

    assert record[BlockFieldDefs.ID] < 0
    assert record[BlockFieldDefs.ALLOC_EVENT_ID] == -1
    assert record[BlockFieldDefs.FREE_EVENT_ID] == -1
