import unittest

from memsnapdump.base import Block, BlockState, DeviceSnapshot, Segment
from memsnapdump.simulate import snapshot_mutator
from tests.common import valid_segments

CHECKER = unittest.TestCase()


def make_snapshot(segments=None):
    snapshot = DeviceSnapshot()
    snapshot.segments = list(segments or [])
    snapshot.trace_entries = []
    snapshot.total_allocated = sum(seg.allocated_size for seg in snapshot.segments)
    snapshot.total_activated = sum(seg.active_size for seg in snapshot.segments)
    snapshot.total_reserved = sum(seg.total_size for seg in snapshot.segments)
    snapshot.device = 0
    return snapshot


def make_segment(address=0x1000, total_size=0x1000):
    return Segment(
        address=address,
        total_size=total_size,
        stream=0,
        segment_type="large",
        allocated_size=0,
        active_size=0,
        blocks=[],
    )


def make_block(address=0x1000, size=0x100, state=BlockState.ACTIVE_ALLOCATED):
    return Block(size=size, requested_size=size, address=address, state=state)


def test_detach_block_returns_false_when_block_has_no_segment():
    snapshot = make_snapshot()
    block = make_block()

    assert snapshot_mutator.detach_block(snapshot, block) is False
    valid_segments(snapshot.segments, CHECKER)


def test_promote_pending_free_block_returns_false_without_segment():
    snapshot = make_snapshot()
    block = make_block(state=BlockState.ACTIVE_PENDING_FREE)

    assert snapshot_mutator.promote_pending_free_block(snapshot, block) is False
    valid_segments(snapshot.segments, CHECKER)


def test_merge_mapped_segment_merges_left_and_right_adjacent_segments_when_present():
    left = make_segment(0x1000, 0x100)
    right = make_segment(0x1300, 0x100)
    new_segment = make_segment(0x1100, 0x200)
    right_block = make_block(0x1300, 0x80)
    right_block.segment_ptr = right
    right.blocks.append(right_block)
    right.active_size = right_block.size
    right.allocated_size = right_block.size
    snapshot = make_snapshot([left, right])

    assert snapshot_mutator.merge_mapped_segment(snapshot, new_segment, 0, 1) is True
    assert len(snapshot.segments) == 1
    merged = snapshot.segments[0]
    assert merged.total_size == 0x400
    assert right_block.segment_ptr is merged
    valid_segments(snapshot.segments, CHECKER)


def test_merge_mapped_segment_merges_right_adjacent_segment_without_left_neighbor():
    right = make_segment(0x1300, 0x100)
    new_segment = make_segment(0x1100, 0x200)
    right_block = make_block(0x1300, 0x80)
    right_block.segment_ptr = right
    right.blocks.append(right_block)
    right.active_size = right_block.size
    right.allocated_size = right_block.size
    snapshot = make_snapshot([right])

    assert snapshot_mutator.merge_mapped_segment(snapshot, new_segment, -1, 0) is True
    assert len(snapshot.segments) == 1
    merged = snapshot.segments[0]
    assert merged.address == 0x1100
    assert merged.total_size == 0x300
    assert right_block.segment_ptr is merged
    valid_segments(snapshot.segments, CHECKER)


def test_merge_mapped_segment_returns_false_when_no_adjacent_segments_exist():
    snapshot = make_snapshot()
    new_segment = make_segment(0x1100, 0x200)

    assert snapshot_mutator.merge_mapped_segment(snapshot, new_segment, -1, -1) is False
    assert snapshot.segments == []
    valid_segments(snapshot.segments, CHECKER)


def test_split_or_shrink_segment_uses_middle_split_branch():
    segment = make_segment(0x1000, 0x1000)
    left_block = make_block(0x1000, 0x100)
    right_block = make_block(0x1800, 0x100)
    left_block.segment_ptr = segment
    right_block.segment_ptr = segment
    segment.blocks = [left_block, right_block]
    segment.active_size = left_block.size + right_block.size
    segment.allocated_size = left_block.size + right_block.size
    snapshot = make_snapshot([segment])

    assert snapshot_mutator.split_or_shrink_segment(snapshot, 0, 0x1400, 0x100) is True
    assert len(snapshot.segments) == 2
    valid_segments(snapshot.segments, CHECKER)


def test_increase_and_decrease_reserved_update_snapshot_totals():
    snapshot = make_snapshot()

    snapshot_mutator.increase_reserved(snapshot, 64)
    snapshot_mutator.decrease_reserved(snapshot, 24)

    assert snapshot.total_reserved == 40
