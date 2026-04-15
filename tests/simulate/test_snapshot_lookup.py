import unittest

from memsnapdump.base import DeviceSnapshot, Segment, Block, BlockState
from memsnapdump.simulate.snapshot_lookup import (
    find_block,
    find_gap_for_alloc_block,
    find_overlapping_segment,
    find_segment,
    is_valid_sub_block,
)


class TestSnapshotLookup(unittest.TestCase):

    @staticmethod
    def make_snapshot(segments: list[Segment]) -> DeviceSnapshot:
        snapshot = DeviceSnapshot()
        snapshot.segments = sorted(segments, key=lambda seg: (seg.address, seg.stream))
        snapshot.trace_entries = []
        snapshot.total_allocated = sum(seg.allocated_size for seg in snapshot.segments)
        snapshot.total_reserved = sum(seg.total_size for seg in snapshot.segments)
        snapshot.total_activated = sum(seg.active_size for seg in snapshot.segments)
        snapshot.device = 0
        return snapshot

    @staticmethod
    def make_segment(
        address: int,
        total_size: int,
        stream: int = 0,
        blocks: list[Block] | None = None,
    ) -> Segment:
        segment = Segment(
            address=address,
            total_size=total_size,
            stream=stream,
            segment_type="large",
            allocated_size=0,
            active_size=0,
            blocks=[],
        )
        for block in blocks or []:
            block.segment_ptr = segment
            segment.blocks.append(block)
            segment.active_size += block.size
            if block.state == BlockState.ACTIVE_ALLOCATED:
                segment.allocated_size += block.size
        return segment

    @staticmethod
    def make_block(
        address: int, size: int, state: str = BlockState.ACTIVE_ALLOCATED
    ) -> Block:
        return Block(size=size, requested_size=size, address=address, state=state)

    def test_find_block_returns_idx_and_block(self):
        block_a = self.make_block(0x1000, 0x100)
        block_b = self.make_block(0x1400, 0x80)
        snapshot = self.make_snapshot(
            [self.make_segment(0x1000, 0x1000, blocks=[block_a, block_b])]
        )

        block_idx, found = find_block(snapshot.segments[0], 0x1400)
        miss_idx, missing = find_block(snapshot.segments[0], 0x1800)

        self.assertEqual(1, block_idx)
        self.assertIs(found, block_b)
        self.assertEqual(-1, miss_idx)
        self.assertIsNone(missing)

    def test_find_segment_returns_idx_and_exact_segment(self):
        snapshot = self.make_snapshot(
            [
                self.make_segment(0x1000, 0x300, stream=0),
                self.make_segment(0x1000, 0x400, stream=1),
                self.make_segment(0x2000, 0x200, stream=0),
            ]
        )

        result_idx, result_seg = find_overlapping_segment(snapshot, 0x1000)
        overlapping_seg0_idx, overlapping_seg0 = find_overlapping_segment(
            snapshot, 0x1000, stream=0
        )
        exact_seg1_idx, exact_seg1 = find_segment(snapshot, 0x1000, stream=1)
        missing_exact_idx, missing_exact_seg = find_segment(snapshot, 0x1100, stream=1)

        self.assertIn(result_idx, [0, 1])
        self.assertIsNotNone(result_seg)
        self.assertEqual(0, overlapping_seg0_idx)
        self.assertEqual(0x1000, overlapping_seg0.address)
        self.assertEqual(1, exact_seg1_idx)
        self.assertEqual(1, exact_seg1.stream)
        self.assertEqual(-1, missing_exact_idx)
        self.assertIsNone(missing_exact_seg)

    def test_find_overlapping_segment_scans_both_sides_when_overlapping_ranges_exist(
        self,
    ):
        snapshot = self.make_snapshot(
            [
                self.make_segment(0x1000, 0x1000, stream=5),
                self.make_segment(0x1800, 0x100, stream=1),
            ]
        )

        seg_idx, seg = find_overlapping_segment(snapshot, 0x1850, stream=1)

        self.assertEqual(1, seg_idx)
        self.assertIs(seg, snapshot.segments[1])

    def test_find_overlapping_segment_finds_left_side_overlap_when_mid_stream_mismatches(
        self,
    ):
        snapshot = self.make_snapshot(
            [
                self.make_segment(0x1000, 0x900, stream=1),
                self.make_segment(0x1400, 0x1000, stream=5),
            ]
        )

        seg_idx, seg = find_overlapping_segment(snapshot, 0x1850, stream=1)

        self.assertEqual(0, seg_idx)
        self.assertIs(seg, snapshot.segments[0])

    def test_find_overlapping_segment_returns_none_when_overlap_exists_but_stream_missing(
        self,
    ):
        snapshot = self.make_snapshot(
            [
                self.make_segment(0x1000, 0x1000, stream=5),
                self.make_segment(0x1800, 0x100, stream=1),
            ]
        )

        seg_idx, seg = find_overlapping_segment(snapshot, 0x1850, stream=9)

        self.assertEqual(-1, seg_idx)
        self.assertIsNone(seg)

    def test_is_valid_sub_block_checks_range_inclusion(self):
        block = self.make_block(0x1000, 0x200)

        self.assertTrue(is_valid_sub_block(block, 0x1000, 0x100))
        self.assertTrue(is_valid_sub_block(block, 0x1100, 0x100))
        self.assertFalse(is_valid_sub_block(block, 0x0F00, 0x100))
        self.assertFalse(is_valid_sub_block(block, 0x1100, 0x200))

    def test_find_gap_for_alloc_block_returns_insert_position_between_blocks(self):
        block_a = self.make_block(0x1000, 0x100)
        block_b = self.make_block(0x1400, 0x100)
        snapshot = self.make_snapshot(
            [self.make_segment(0x1000, 0x1000, blocks=[block_a, block_b])]
        )

        gap = find_gap_for_alloc_block(snapshot, 0x1200, 0x100, stream=0)

        self.assertIsNotNone(gap)
        segment, insert_idx = gap
        self.assertEqual(0x1000, segment.address)
        self.assertEqual(1, insert_idx)


if __name__ == "__main__":
    unittest.main(verbosity=2, module="test_snapshot_lookup")
