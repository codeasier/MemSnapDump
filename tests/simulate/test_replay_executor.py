import unittest

from memsnapdump.base import TraceEntry
from memsnapdump.simulate.replay_executor import ReplayExecutor


class FakeAllocator:
    def __init__(self):
        self.calls = []

    def alloc_block(self, block):
        self.calls.append(("alloc_block", block))
        return True

    def active_block(self, event):
        self.calls.append(("active_block", event))
        return True

    def free_block(self, event):
        self.calls.append(("free_block", event))
        return True

    def alloc_or_map_segment(self, segment, merge=False):
        self.calls.append(("alloc_or_map_segment", segment, merge))
        return True

    def free_segment(self, event):
        self.calls.append(("free_segment", event))
        return True

    def unmap_segment(self, event):
        self.calls.append(("unmap_segment", event))
        return True


class FakeLogger:
    def __init__(self):
        self.messages = []

    def warning(self, msg, *args, **kwargs):
        self.messages.append(msg)


class TestReplayExecutor(unittest.TestCase):
    def setUp(self):
        self.allocator = FakeAllocator()
        self.logger = FakeLogger()
        self.executor = ReplayExecutor(self.allocator, self.logger)

    @staticmethod
    def make_event(
        action: str,
        addr: int = 0x1000,
        size: int = 0x100,
        stream: int = 0,
        idx: int = 1,
    ) -> TraceEntry:
        return TraceEntry(action=action, addr=addr, size=size, stream=stream, idx=idx)

    def test_execute_free_event_maps_to_alloc_block(self):
        event = self.make_event("free")

        result = self.executor.execute(event)

        self.assertTrue(result)
        call = self.allocator.calls[0]
        self.assertEqual("alloc_block", call[0])
        self.assertEqual(event.addr, call[1].address)

    def test_execute_segment_unmap_maps_to_alloc_or_map_segment_with_merge(self):
        event = self.make_event("segment_unmap", addr=0x2000, size=0x400)

        result = self.executor.execute(event)

        self.assertTrue(result)
        call = self.allocator.calls[0]
        self.assertEqual("alloc_or_map_segment", call[0])
        self.assertTrue(call[2])
        self.assertEqual(event.idx, call[1].free_or_unmap_event_idx)

    def test_execute_unknown_event_warns_and_skips(self):
        event = self.make_event("unknown_action")

        result = self.executor.execute(event)

        self.assertTrue(result)
        self.assertEqual([], self.allocator.calls)
        self.assertEqual(1, len(self.logger.messages))
        self.assertIn("Skip event", self.logger.messages[0])


if __name__ == "__main__":
    unittest.main(verbosity=2, module="test_replay_executor")
