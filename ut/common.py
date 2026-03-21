import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

import unittest
from typing import List
from base import Segment, BlockState


def valid_segment(segment: Segment, test_util: unittest.TestCase):
    test_util.assertGreaterEqual(segment.active_size, segment.allocated_size)
    test_util.assertGreaterEqual(segment.total_size, segment.active_size)
    addr_offset = segment.address
    allocated = 0
    activated = 0
    for block in segment.blocks:
        test_util.assertGreater(block.size, 0)
        if block.state != BlockState.INACTIVE:
            activated += block.size
            if block.state == BlockState.ACTIVE_ALLOCATED:
                allocated += block.size
        test_util.assertEqual(block.address, addr_offset)
        test_util.assertEqual(block.segment_ptr, segment)
        addr_offset += block.size
    test_util.assertEqual(segment.address + segment.total_size, addr_offset)
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
