import unittest

from memsnapdump.base import DeviceSnapshot, Segment, Block, BlockState, TraceEntry
from memsnapdump.simulate.allocator_context import AllocatorContext
from memsnapdump.simulate.simulated_caching_allocator import SimulatedCachingAllocator
from memsnapdump.simulate import snapshot_mutator
from tests.common import valid_segment, valid_snapshot


class TestSnapshotMutatorState(unittest.TestCase):

    @staticmethod
    def make_snapshot(
        segments: list[Segment], trace_entries: list[TraceEntry] | None = None
    ) -> DeviceSnapshot:
        snapshot = DeviceSnapshot()
        snapshot.segments = sorted(segments, key=lambda seg: (seg.address, seg.stream))
        snapshot.trace_entries = trace_entries or []
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

    @staticmethod
    def make_event(
        action: str, addr: int, size: int, stream: int = 0, idx: int = 0
    ) -> TraceEntry:
        return TraceEntry(action=action, addr=addr, size=size, stream=stream, idx=idx)

    def make_allocator(
        self, segments: list[Segment], trace_entries: list[TraceEntry] | None = None
    ) -> SimulatedCachingAllocator:
        snapshot = self.make_snapshot(segments, trace_entries)
        ctx = AllocatorContext(snapshot)
        return SimulatedCachingAllocator(ctx)

    def test_attach_and_detach_block_keep_totals_consistent(self):
        snapshot = self.make_snapshot([])
        segment = self.make_segment(0x1000, 0x1000)
        snapshot_mutator.insert_segment(snapshot, segment)
        block = self.make_block(0x1200, 0x100)

        snapshot_mutator.attach_block(snapshot, segment, block, 0)

        self.assertIs(block.segment_ptr, segment)
        self.assertEqual(0x100, segment.active_size)
        self.assertEqual(0x100, segment.allocated_size)
        self.assertEqual(0x100, snapshot.total_activated)
        self.assertEqual(0x100, snapshot.total_allocated)
        valid_snapshot(snapshot, self)

        self.assertTrue(snapshot_mutator.detach_block(snapshot, block))
        self.assertIsNone(block.segment_ptr)
        self.assertEqual([], segment.blocks)
        self.assertEqual(0, segment.active_size)
        self.assertEqual(0, segment.allocated_size)
        self.assertEqual(0, snapshot.total_activated)
        self.assertEqual(0, snapshot.total_allocated)
        valid_snapshot(snapshot, self)

    def test_insert_and_remove_segment_keep_reserved_consistent(self):
        snapshot = self.make_snapshot([])
        segment = self.make_segment(0x2000, 0x400)

        snapshot_mutator.insert_segment(snapshot, segment)

        self.assertEqual(1, len(snapshot.segments))
        self.assertEqual(0x400, snapshot.total_reserved)
        valid_snapshot(snapshot, self)

        snapshot_mutator.remove_segment(snapshot, segment)

        self.assertEqual([], snapshot.segments)
        self.assertEqual(0, snapshot.total_reserved)
        valid_snapshot(snapshot, self)

    def test_alloc_block_updates_segment_and_snapshot_totals(self):
        segment = self.make_segment(0x1000, 0x1000)
        allocator = self.make_allocator([segment])
        allocator.ctx.set_current_undo_event(
            self.make_event("free", 0x1200, 0x100, idx=7)
        )
        new_block = self.make_block(0x1200, 0x100)

        allocated = allocator.alloc_block(new_block)

        self.assertTrue(allocated)
        self.assertEqual(0x100, segment.active_size)
        self.assertEqual(0x100, segment.allocated_size)
        self.assertEqual(0x100, allocator.ctx.device_snapshot.total_activated)
        self.assertEqual(0x100, allocator.ctx.device_snapshot.total_allocated)
        self.assertEqual(7, new_block.free_event_idx)
        self.assertIs(new_block.segment_ptr, segment)
        valid_segment(segment, self)
        valid_snapshot(allocator.ctx.device_snapshot, self)

    def test_free_block_updates_segment_and_snapshot_totals(self):
        block = self.make_block(0x1200, 0x100)
        segment = self.make_segment(0x1000, 0x1000, blocks=[block])
        allocator = self.make_allocator([segment])
        event = self.make_event("alloc", 0x1200, 0x100, idx=8)

        freed = allocator.free_block(event)

        self.assertTrue(freed)
        self.assertEqual([], segment.blocks)
        self.assertEqual(0, segment.active_size)
        self.assertEqual(0, segment.allocated_size)
        self.assertEqual(0, allocator.ctx.device_snapshot.total_activated)
        self.assertEqual(0, allocator.ctx.device_snapshot.total_allocated)
        valid_snapshot(allocator.ctx.device_snapshot, self)

    def test_active_block_promotes_pending_free_block(self):
        block = self.make_block(0x1200, 0x100, state=BlockState.ACTIVE_PENDING_FREE)
        segment = self.make_segment(0x1000, 0x1000, blocks=[block])
        allocator = self.make_allocator([segment])
        event = self.make_event("free_requested", 0x1200, 0x100)

        activated = allocator.active_block(event)

        self.assertTrue(activated)
        self.assertEqual(BlockState.ACTIVE_ALLOCATED, block.state)
        self.assertEqual(0x100, segment.allocated_size)
        self.assertEqual(0x100, allocator.ctx.device_snapshot.total_allocated)
        valid_segment(segment, self)
        valid_snapshot(allocator.ctx.device_snapshot, self)

    def test_workspace_flag_tolerates_missing_block_on_free(self):
        segment = self.make_segment(0x1000, 0x1000)
        allocator = self.make_allocator([segment])
        allocator.ctx.workspace_flag = True
        event = self.make_event("alloc", 0x1200, 0x100)

        tolerated = allocator.free_block(event)

        self.assertTrue(tolerated)
        self.assertEqual(0, allocator.ctx.device_snapshot.total_allocated)
        self.assertEqual(0, allocator.ctx.device_snapshot.total_activated)
        valid_snapshot(allocator.ctx.device_snapshot, self)

    def test_alloc_or_map_segment_updates_reserved_for_non_merge(self):
        allocator = self.make_allocator([])
        allocator.ctx.set_current_undo_event(
            self.make_event("segment_free", 0x2000, 0x400, idx=5)
        )
        segment = self.make_segment(0x2000, 0x400)

        allocated = allocator.alloc_or_map_segment(segment, merge=False)

        self.assertTrue(allocated)
        self.assertEqual(1, len(allocator.ctx.device_snapshot.segments))
        self.assertEqual(0x400, allocator.ctx.device_snapshot.total_reserved)
        self.assertEqual(5, segment.free_or_unmap_event_idx)
        valid_snapshot(allocator.ctx.device_snapshot, self)

    def test_alloc_or_map_segment_merge_keeps_snapshot_invariants(self):
        left = self.make_segment(0x1000, 0x100)
        allocator = self.make_allocator([left])
        allocator.ctx.set_current_undo_event(
            self.make_event("segment_free", 0x1100, 0x80, idx=9)
        )
        new_segment = self.make_segment(0x1100, 0x80)

        allocated = allocator.alloc_or_map_segment(new_segment, merge=True)

        self.assertTrue(allocated)
        self.assertEqual(1, len(allocator.ctx.device_snapshot.segments))
        self.assertEqual(0x180, allocator.ctx.device_snapshot.total_reserved)
        valid_snapshot(allocator.ctx.device_snapshot, self)

    def test_unmap_segment_keeps_snapshot_invariants(self):
        segment = self.make_segment(0x1000, 0x200)
        allocator = self.make_allocator([segment])
        map_event = self.make_event("segment_map", 0x1000, 0x80, idx=10)

        unmapped = allocator.unmap_segment(map_event)

        self.assertTrue(unmapped)
        self.assertEqual(0x180, allocator.ctx.device_snapshot.total_reserved)
        valid_snapshot(allocator.ctx.device_snapshot, self)


if __name__ == "__main__":
    unittest.main(verbosity=2, module="test_snapshot_mutator_state")
