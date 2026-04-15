import unittest

from memsnapdump.base import (
    Block,
    BlockState,
    DeviceSnapshot,
    Frame,
    Segment,
    TraceEntry,
)
from memsnapdump.simulate.snapshot_lookup import (
    find_block,
    find_overlapping_segment,
    find_segment,
    is_valid_sub_block,
)

# range lookup helpers are tested via returned (idx, object) tuples


class TestFrame(unittest.TestCase):

    def test_from_dict(self):
        frame_dict = {"filename": "test.py", "line": 42, "name": "test_func"}
        frame = Frame.from_dict(frame_dict)
        self.assertEqual(frame.filename, "test.py")
        self.assertEqual(frame.line, 42)
        self.assertEqual(frame.name, "test_func")
        self.assertEqual(frame._origin, frame_dict)

    def test_to_dict_with_origin(self):
        frame_dict = {"filename": "test.py", "line": 42, "name": "test_func"}
        frame = Frame.from_dict(frame_dict)
        result = frame.to_dict()
        self.assertEqual(result, frame_dict)

    def test_to_dict_without_origin(self):
        frame = Frame()
        frame.filename = "test.py"
        frame.line = 42
        frame.name = "test_func"
        result = frame.to_dict()
        self.assertEqual(result["filename"], "test.py")
        self.assertEqual(result["line"], 42)
        self.assertEqual(result["name"], "test_func")


class TestTraceEntry(unittest.TestCase):

    def test_from_dict(self):
        trace_dict = {
            "action": "alloc",
            "addr": 0x1000,
            "size": "1024",
            "stream": "0",
            "frames": [
                {"filename": "test.py", "line": 10, "name": "func_a"},
                {"filename": "test.py", "line": 20, "name": "func_b"},
            ],
        }
        trace = TraceEntry.from_dict(trace_dict)
        self.assertEqual(trace.action, "alloc")
        self.assertEqual(trace.addr, 0x1000)
        self.assertEqual(trace.size, 1024)
        self.assertEqual(trace.stream, 0)
        self.assertEqual(len(trace.frames), 2)
        self.assertEqual(trace.frames[0].filename, "test.py")
        self.assertEqual(trace.frames[1].name, "func_b")

    def test_from_dict_without_frames(self):
        trace_dict = {
            "action": "free_requested",
            "addr": 0x2000,
            "size": "2048",
            "stream": "1",
        }
        trace = TraceEntry.from_dict(trace_dict)
        self.assertEqual(trace.action, "free_requested")
        self.assertEqual(trace.addr, 0x2000)
        self.assertEqual(trace.size, 2048)
        self.assertEqual(len(trace.frames), 0)

    def test_get_callstack(self):
        trace_dict = {
            "action": "alloc",
            "addr": 0x1000,
            "size": "1024",
            "stream": "0",
            "frames": [
                {"filename": "test.py", "line": 10, "name": "func_a"},
                {"filename": "main.py", "line": 20, "name": "func_b"},
            ],
        }
        trace = TraceEntry.from_dict(trace_dict)
        callstack = trace.get_callstack()
        self.assertIn("main.py:20 func_b", callstack)
        self.assertIn("test.py:10 func_a", callstack)

    def test_get_callstack_empty_frames(self):
        trace = TraceEntry()
        trace.action = "alloc"
        callstack = trace.get_callstack()
        self.assertEqual(callstack, "")

    def test_to_dict(self):
        trace_dict = {
            "action": "alloc",
            "addr": 0x1000,
            "size": "1024",
            "stream": "0",
            "frames": [],
        }
        trace = TraceEntry.from_dict(trace_dict)
        result = trace.to_dict()
        self.assertEqual(result, trace_dict)


class TestBlock(unittest.TestCase):

    def test_from_dict(self):
        block_dict = {
            "size": 1024,
            "requested_size": 512,
            "address": 0x1000,
            "state": "active_allocated",
            "frames": [{"filename": "test.py", "line": 10, "name": "alloc_func"}],
        }
        block = Block.from_dict(block_dict)
        self.assertEqual(block.size, 1024)
        self.assertEqual(block.requested_size, 512)
        self.assertEqual(block.address, 0x1000)
        self.assertEqual(block.state, "active_allocated")
        self.assertEqual(len(block.frames), 1)

    def test_build_from_event(self):
        trace_dict = {
            "action": "alloc",
            "addr": 0x2000,
            "size": "2048",
            "stream": "0",
            "frames": [{"filename": "test.py", "line": 10, "name": "func"}],
        }
        event = TraceEntry.from_dict(trace_dict)
        block = Block.build_from_event(event)
        self.assertEqual(block.size, 2048)
        self.assertEqual(block.requested_size, 2048)
        self.assertEqual(block.address, 0x2000)
        self.assertEqual(len(block.frames), 1)

    def test_valid_sub_block(self):
        block = Block(size=1024, address=0x1000)
        self.assertTrue(is_valid_sub_block(block, 0x1000, 512))
        self.assertTrue(is_valid_sub_block(block, 0x1200, 512))
        self.assertTrue(is_valid_sub_block(block, 0x1000, 1024))
        self.assertFalse(is_valid_sub_block(block, 0x900, 512))
        self.assertFalse(is_valid_sub_block(block, 0x1400, 512))
        self.assertFalse(is_valid_sub_block(block, 0x1000, 2048))

    def test_to_dict(self):
        block = Block(
            size=1024,
            requested_size=512,
            address=0x1000,
            state=BlockState.ACTIVE_ALLOCATED,
            frames=[
                Frame.from_dict({"filename": "test.py", "line": 10, "name": "func"})
            ],
        )
        result = block.to_dict()
        self.assertEqual(result["size"], 1024)
        self.assertEqual(result["requested_size"], 512)
        self.assertEqual(result["address"], 0x1000)
        self.assertEqual(result["state"], BlockState.ACTIVE_ALLOCATED)


class TestSegment(unittest.TestCase):

    def test_from_dict(self):
        segment_dict = {
            "address": 0x10000,
            "total_size": 4096,
            "stream": 0,
            "segment_type": "large",
            "allocated_size": 2048,
            "active_size": 3072,
            "device": 0,
            "is_expandable": False,
            "frames": [],
            "blocks": [
                {
                    "size": 2048,
                    "requested_size": 1024,
                    "address": 0x10000,
                    "state": "active_allocated",
                    "frames": [],
                },
                {
                    "size": 2048,
                    "requested_size": 2048,
                    "address": 0x10800,
                    "state": "inactive",
                    "frames": [],
                },
            ],
        }
        segment = Segment.from_dict(segment_dict)
        self.assertEqual(segment.address, 0x10000)
        self.assertEqual(segment.total_size, 4096)
        self.assertEqual(segment.allocated_size, 2048)
        self.assertEqual(segment.active_size, 3072)
        self.assertEqual(len(segment.blocks), 2)
        self.assertEqual(segment.blocks[0].segment_ptr, segment)
        self.assertEqual(segment.blocks[1].segment_ptr, segment)

    def test_from_dict_with_expandable(self):
        segment_dict = {
            "address": 0x10000,
            "total_size": 4096,
            "stream": 0,
            "segment_type": "large",
            "allocated_size": 0,
            "active_size": 0,
            "device": 0,
            "is_expandable": True,
            "frames": [],
            "blocks": [],
        }
        segment = Segment.from_dict(segment_dict)
        self.assertTrue(segment.is_expandable)

    def test_build_from_event(self):
        trace_dict = {
            "action": "segment_alloc",
            "addr": 0x20000,
            "size": "8192",
            "stream": "1",
            "frames": [],
        }
        event = TraceEntry.from_dict(trace_dict)
        segment = Segment.build_from_event(event, True)
        self.assertEqual(segment.address, 0x20000)
        self.assertEqual(segment.total_size, 8192)
        self.assertEqual(segment.stream, 1)
        self.assertEqual(len(segment.blocks), 1)
        self.assertEqual(segment.blocks[0].state, BlockState.INACTIVE)
        self.assertEqual(segment.blocks[0].segment_ptr, segment)

    def test_build_from_event_expandable(self):
        trace_dict = {
            "action": "segment_map",
            "addr": 0x30000,
            "size": "16384",
            "stream": "0",
            "frames": [],
        }
        event = TraceEntry.from_dict(trace_dict)
        segment = Segment.build_from_event(event)
        self.assertTrue(segment.is_expandable)

    def test_find_block_returns_idx_and_object(self):
        segment = Segment(address=0x10000, total_size=8192)
        segment.blocks = [
            Block(size=2048, address=0x10000),
            Block(size=2048, address=0x10800),
            Block(size=4096, address=0x11000),
        ]
        block_idx, block = find_block(segment, 0x10000)
        self.assertEqual(block_idx, 0)
        self.assertIs(block, segment.blocks[0])
        block_idx, block = find_block(segment, 0x10800)
        self.assertEqual(block_idx, 1)
        self.assertIs(block, segment.blocks[1])
        block_idx, block = find_block(segment, 0x11000)
        self.assertEqual(block_idx, 2)
        self.assertIs(block, segment.blocks[2])
        block_idx, block = find_block(segment, 0x10500)
        self.assertEqual(block_idx, 0)
        self.assertIs(block, segment.blocks[0])
        block_idx, block = find_block(segment, 0x11500)
        self.assertEqual(block_idx, 2)
        self.assertIs(block, segment.blocks[2])
        block_idx, block = find_block(segment, 0x9000)
        self.assertEqual(block_idx, -1)
        self.assertIsNone(block)
        block_idx, block = find_block(segment, 0x13000)
        self.assertEqual(block_idx, -1)
        self.assertIsNone(block)

    def test_to_dict(self):
        segment = Segment(
            address=0x10000,
            total_size=4096,
            stream=0,
            segment_type="large",
            allocated_size=2048,
            active_size=2048,
            device=0,
            is_expandable=False,
        )
        result = segment.to_dict()
        self.assertEqual(result["address"], 0x10000)
        self.assertEqual(result["total_size"], 4096)
        self.assertEqual(result["segment_type"], "large")


class TestDeviceSnapshot(unittest.TestCase):

    def test_from_dict(self):
        snapshot_dict = {
            "segments": [
                {
                    "address": 0x10000,
                    "total_size": 4096,
                    "stream": 0,
                    "segment_type": "large",
                    "allocated_size": 2048,
                    "active_size": 2048,
                    "device": 0,
                    "is_expandable": False,
                    "frames": [],
                    "blocks": [
                        {
                            "size": 2048,
                            "requested_size": 1024,
                            "address": 0x10000,
                            "state": "active_allocated",
                            "frames": [],
                        },
                        {
                            "size": 2048,
                            "requested_size": 2048,
                            "address": 0x10800,
                            "state": "inactive",
                            "frames": [],
                        },
                    ],
                }
            ],
            "device_traces": [
                [
                    {
                        "action": "alloc",
                        "addr": 0x10000,
                        "size": "1024",
                        "stream": "0",
                        "frames": [],
                    },
                    {
                        "action": "free_requested",
                        "addr": 0x10000,
                        "size": "1024",
                        "stream": "0",
                        "frames": [],
                    },
                ]
            ],
        }
        snapshot = DeviceSnapshot.from_dict(snapshot_dict, 0)
        self.assertEqual(len(snapshot.segments), 1)
        self.assertEqual(len(snapshot.trace_entries), 2)
        self.assertEqual(snapshot.total_reserved, 4096)
        self.assertEqual(snapshot.total_allocated, 2048)
        self.assertEqual(snapshot.total_activated, 2048)
        self.assertEqual(snapshot.trace_entries[0].idx, 0)
        self.assertEqual(snapshot.trace_entries[1].idx, 1)

    def test_find_overlapping_segment_returns_idx_and_matches_containing_segment(self):
        snapshot = DeviceSnapshot()
        snapshot.segments = [
            Segment(address=0x10000, total_size=0x2000),
            Segment(address=0x20000, total_size=0x5000),
            Segment(address=0x30000, total_size=0x1000),
        ]
        seg_idx, seg = find_overlapping_segment(snapshot, 0x10000)
        self.assertEqual(seg_idx, 0)
        self.assertIs(seg, snapshot.segments[0])
        seg_idx, seg = find_overlapping_segment(snapshot, 0x12000)
        self.assertEqual(seg_idx, -1)
        self.assertIsNone(seg)
        seg_idx, seg = find_overlapping_segment(snapshot, 0x20000)
        self.assertEqual(seg_idx, 1)
        self.assertIs(seg, snapshot.segments[1])
        seg_idx, seg = find_overlapping_segment(snapshot, 0x25000)
        self.assertEqual(seg_idx, -1)
        self.assertIsNone(seg)
        seg_idx, seg = find_overlapping_segment(snapshot, 0x30000)
        self.assertEqual(seg_idx, 2)
        self.assertIs(seg, snapshot.segments[2])
        seg_idx, seg = find_overlapping_segment(snapshot, 0x9000)
        self.assertEqual(seg_idx, -1)
        self.assertIsNone(seg)
        seg_idx, seg = find_overlapping_segment(snapshot, 0x40000)
        self.assertEqual(seg_idx, -1)
        self.assertIsNone(seg)

    def test_find_overlapping_segment_returns_idx_and_matches_stream_filtered_segment(
        self,
    ):
        snapshot = DeviceSnapshot()
        snapshot.segments = [
            Segment(address=0x10000, total_size=0x2000, stream=0),
            Segment(address=0x10000, total_size=0x3000, stream=1),
            Segment(address=0x20000, total_size=0x5000, stream=0),
            Segment(address=0x30000, total_size=0x1000, stream=1),
        ]
        result_idx, result_seg = find_overlapping_segment(snapshot, 0x10000)
        self.assertIn(result_idx, [0, 1])
        self.assertIsNotNone(result_seg)
        seg_idx, seg = find_overlapping_segment(snapshot, 0x10000, stream=0)
        self.assertEqual(seg_idx, 0)
        self.assertIs(seg, snapshot.segments[0])
        seg_idx, seg = find_overlapping_segment(snapshot, 0x10000, stream=1)
        self.assertEqual(seg_idx, 1)
        self.assertIs(seg, snapshot.segments[1])
        seg_idx, seg = find_overlapping_segment(snapshot, 0x10000, stream=2)
        self.assertEqual(seg_idx, -1)
        self.assertIsNone(seg)
        seg_idx, seg = find_overlapping_segment(snapshot, 0x20000, stream=0)
        self.assertEqual(seg_idx, 2)
        self.assertIs(seg, snapshot.segments[2])
        seg_idx, seg = find_overlapping_segment(snapshot, 0x20000, stream=1)
        self.assertEqual(seg_idx, -1)
        self.assertIsNone(seg)
        seg_idx, seg = find_overlapping_segment(snapshot, 0x11000, stream=1)
        self.assertEqual(seg_idx, 1)
        self.assertIs(seg, snapshot.segments[1])
        exact_idx, exact_seg = find_segment(snapshot, 0x30000, stream=1)
        self.assertEqual(exact_idx, 3)
        self.assertIs(exact_seg, snapshot.segments[3])

    def test_to_dict(self):
        snapshot_dict = {"segments": [], "device_traces": [[]]}
        snapshot = DeviceSnapshot.from_dict(snapshot_dict, 0)
        result = snapshot.to_dict()
        self.assertIn("segments", result)
        self.assertIn("device_traces", result)


if __name__ == "__main__":
    import unittest

    unittest.main(verbosity=2, module="test_entities")
