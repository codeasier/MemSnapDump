import unittest

from memsnapdump.base import DeviceSnapshot, Segment, Block, BlockState
from memsnapdump.simulate.range_ops import (
    find_block_by_addr,
    find_gap_for_alloc_block,
    insert_segment_sorted,
    merge_segments,
    shrink_segment,
    split_segment_at,
)


class TestRangeOps(unittest.TestCase):

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
    def make_segment(address: int, total_size: int, stream: int = 0, blocks: list[Block] | None = None) -> Segment:
        segment = Segment(
            address=address,
            total_size=total_size,
            stream=stream,
            segment_type='large',
            allocated_size=0,
            active_size=0,
            blocks=[]
        )
        for block in blocks or []:
            block.segment_ptr = segment
            segment.blocks.append(block)
            segment.active_size += block.size
            if block.state == BlockState.ACTIVE_ALLOCATED:
                segment.allocated_size += block.size
        return segment

    @staticmethod
    def make_block(address: int, size: int, state: str = BlockState.ACTIVE_ALLOCATED) -> Block:
        return Block(
            size=size,
            requested_size=size,
            address=address,
            state=state
        )


    def test_find_block_by_addr_returns_exact_block(self):
        block_a = self.make_block(0x1000, 0x100)
        block_b = self.make_block(0x1400, 0x80)
        snapshot = self.make_snapshot([
            self.make_segment(0x1000, 0x1000, blocks=[block_a, block_b])
        ])

        found = find_block_by_addr(snapshot, 0, 0x1400)

        self.assertIs(found, block_b)
        self.assertIsNone(find_block_by_addr(snapshot, 0, 0x1800))

    def test_find_gap_for_alloc_block_returns_insert_position_between_blocks(self):
        block_a = self.make_block(0x1000, 0x100)
        block_b = self.make_block(0x1400, 0x100)
        snapshot = self.make_snapshot([
            self.make_segment(0x1000, 0x1000, blocks=[block_a, block_b])
        ])

        gap = find_gap_for_alloc_block(snapshot, 0x1200, 0x100, stream=0)

        self.assertIsNotNone(gap)
        segment, insert_idx = gap
        self.assertEqual(0x1000, segment.address)
        self.assertEqual(1, insert_idx)

    def test_insert_segment_sorted_orders_by_address_then_stream(self):
        segment_a = self.make_segment(0x3000, 0x200, stream=1)
        segment_b = self.make_segment(0x1000, 0x200, stream=0)
        segment_c = self.make_segment(0x3000, 0x200, stream=0)
        snapshot = self.make_snapshot([segment_a, segment_b])

        insert_segment_sorted(snapshot, segment_c)

        ordered = [(seg.address, seg.stream) for seg in snapshot.segments]
        self.assertEqual([(0x1000, 0), (0x3000, 0), (0x3000, 1)], ordered)

    def test_merge_segments_combines_sizes_and_rebinds_blocks(self):
        left_block = self.make_block(0x1000, 0x80)
        right_block = self.make_block(0x1200, 0x80)
        left = self.make_segment(0x1000, 0x100, blocks=[left_block])
        right = self.make_segment(0x1100, 0x200, blocks=[right_block])
        snapshot = self.make_snapshot([left, right])

        merged = merge_segments(snapshot, 0, 1)

        self.assertTrue(merged)
        self.assertEqual(1, len(snapshot.segments))
        merged_segment = snapshot.segments[0]
        self.assertEqual(0x1000, merged_segment.address)
        self.assertEqual(0x300, merged_segment.total_size)
        self.assertEqual([left_block, right_block], merged_segment.blocks)
        self.assertIs(left_block.segment_ptr, merged_segment)
        self.assertIs(right_block.segment_ptr, merged_segment)

    def test_split_segment_at_drops_only_blocks_overlapping_cut_range(self):
        left_block = self.make_block(0x1000, 0x100)
        middle_left_block = self.make_block(0x1300, 0x100)
        overlap_block = self.make_block(0x1500, 0x200)
        right_block = self.make_block(0x1800, 0x100)
        snapshot = self.make_snapshot([
            self.make_segment(0x1000, 0x1000, blocks=[left_block, middle_left_block, overlap_block, right_block])
        ])

        split = split_segment_at(snapshot, 0, 0x1400, 0x200)

        self.assertTrue(split)
        segments = snapshot.segments
        self.assertEqual(2, len(segments))
        self.assertEqual((0x1000, 0x400), (segments[0].address, segments[0].total_size))
        self.assertEqual((0x1600, 0xA00), (segments[1].address, segments[1].total_size))
        self.assertEqual([left_block, middle_left_block], segments[0].blocks)
        self.assertEqual([right_block], segments[1].blocks)
        self.assertIs(left_block.segment_ptr, segments[0])
        self.assertIs(middle_left_block.segment_ptr, segments[0])
        self.assertIs(right_block.segment_ptr, segments[1])

    def test_shrink_segment_left_recomputes_sizes_and_remaining_blocks(self):
        remain_alloc = self.make_block(0x1300, 0x100, state=BlockState.ACTIVE_ALLOCATED)
        remain_pending = self.make_block(0x1500, 0x80, state=BlockState.ACTIVE_PENDING_FREE)
        snapshot = self.make_snapshot([
            self.make_segment(0x1000, 0x1000, blocks=[remain_alloc, remain_pending])
        ])

        shrunk = shrink_segment(snapshot, 0, 0x1000, 0x200, 'left')

        self.assertTrue(shrunk)
        segment = snapshot.segments[0]
        self.assertEqual(0x1200, segment.address)
        self.assertEqual(0xE00, segment.total_size)
        self.assertEqual([remain_alloc, remain_pending], segment.blocks)
        self.assertEqual(remain_alloc.size, segment.allocated_size)
        self.assertEqual(remain_alloc.size + remain_pending.size, segment.active_size)


if __name__ == "__main__":
    unittest.main(verbosity=2, module="test_range_ops")
