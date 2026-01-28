import unittest
from typing import List
from base import Segment, BlockState


# 校验单个segment是否合法
def valid_segment(segment: Segment, test_util: unittest.TestCase):
    # allocated <= active <= total
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
        addr_offset += block.size
    test_util.assertEqual(segment.address + segment.total_size, addr_offset)
    test_util.assertEqual(allocated, segment.allocated_size)
    test_util.assertEqual(activated, segment.active_size)


# 校验snapshot中的segments是否合法
def valid_segments(segments: List[Segment], test_util: unittest.TestCase):
    pre_seg_start = -1
    pre_seg_end = 0
    for seg in segments:
        # 校验seg是否地址异常
        seg_start = seg.address
        seg_end = seg.address + seg.total_size
        test_util.assertTrue(pre_seg_start < pre_seg_end <= seg_start < seg_end)
        # 校验seg数值是否正确
        valid_segment(seg, test_util)
        pre_seg_start = seg_start
        pre_seg_end = seg_end
