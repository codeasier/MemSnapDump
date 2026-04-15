import unittest
from typing import List
from memsnapdump.base import DeviceSnapshot, Segment, BlockState


def valid_segment(segment: Segment, test_util: unittest.TestCase):
    test_util.assertGreaterEqual(segment.active_size, segment.allocated_size)
    test_util.assertGreaterEqual(segment.total_size, segment.active_size)
    allocated = 0
    activated = 0
    for block in segment.blocks:
        test_util.assertGreater(block.size, 0)
        if block.state != BlockState.INACTIVE:
            activated += block.size
            if block.state == BlockState.ACTIVE_ALLOCATED:
                allocated += block.size
        test_util.assertEqual(block.segment_ptr, segment)
    test_util.assertEqual(allocated, segment.allocated_size)
    test_util.assertEqual(activated, segment.active_size)


def valid_segments(segments: List[Segment], test_util: unittest.TestCase):
    pre_seg_start = -1
    pre_seg_end = 0
    for seg in segments:
        seg_start = seg.address
        seg_end = seg.address + seg.total_size
        test_util.assertTrue(pre_seg_start < pre_seg_end <= seg_start < seg_end)
        valid_segment(seg, test_util)
        pre_seg_start = seg_start
        pre_seg_end = seg_end


def valid_snapshot(snapshot: DeviceSnapshot, test_util: unittest.TestCase):
    valid_segments(snapshot.segments, test_util)
    test_util.assertEqual(
        sum(seg.total_size for seg in snapshot.segments), snapshot.total_reserved
    )
    test_util.assertEqual(
        sum(seg.allocated_size for seg in snapshot.segments), snapshot.total_allocated
    )
    test_util.assertEqual(
        sum(seg.active_size for seg in snapshot.segments), snapshot.total_activated
    )
