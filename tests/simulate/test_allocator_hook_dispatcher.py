from memsnapdump.base import Block, DeviceSnapshot, Segment
from memsnapdump.simulate.allocator_hook_dispatcher import AllocatorHookDispatcher


class RecordingHooker:
    def __init__(self):
        self.calls = []

    def pre_replay_alloc_block(self, block, snapshot):
        self.calls.append(("pre_alloc", block, snapshot))

    def post_replay_alloc_block(self, block, snapshot):
        self.calls.append(("post_alloc", block, snapshot))

    def pre_replay_free_block(self, block, snapshot):
        self.calls.append(("pre_free", block, snapshot))

    def post_replay_free_block(self, block, snapshot):
        self.calls.append(("post_free", block, snapshot))

    def pre_replay_map_or_alloc_segment(self, segment, snapshot):
        self.calls.append(("pre_segment_alloc", segment, snapshot))

    def post_replay_map_or_alloc_segment(self, segment, snapshot):
        self.calls.append(("post_segment_alloc", segment, snapshot))

    def pre_replay_unmap_or_free_segment(self, segment, snapshot):
        self.calls.append(("pre_segment_free", segment, snapshot))

    def post_replay_unmap_or_free_segment(self, segment, snapshot):
        self.calls.append(("post_segment_free", segment, snapshot))


def test_dispatcher_register_unregister_and_dispatch_copy_behavior():
    dispatcher = AllocatorHookDispatcher()
    hooker = RecordingHooker()
    snapshot = DeviceSnapshot()
    block = Block(size=16, requested_size=16, address=0x1000)
    segment = Segment(address=0x1000, total_size=0x100, stream=0)

    hooker_id = dispatcher.register_hooker(hooker)
    assert hooker_id in dispatcher.hookers

    dispatcher.pre_replay_alloc_block(block, snapshot)
    dispatcher.post_replay_alloc_block(block, snapshot)
    dispatcher.pre_replay_free_block(block, snapshot)
    dispatcher.post_replay_free_block(block, snapshot, use_copy=True)
    dispatcher.pre_replay_map_or_alloc_segment(segment, snapshot)
    dispatcher.post_replay_map_or_alloc_segment(segment, snapshot)
    dispatcher.pre_replay_unmap_or_free_segment(segment, snapshot)
    dispatcher.post_replay_unmap_or_free_segment(segment, snapshot)

    names = [call[0] for call in hooker.calls]
    assert names == [
        "pre_alloc",
        "post_alloc",
        "pre_free",
        "post_free",
        "pre_segment_alloc",
        "post_segment_alloc",
        "pre_segment_free",
        "post_segment_free",
    ]
    assert hooker.calls[3][1] is not block
    assert hooker.calls[3][1].address == block.address

    dispatcher.unregister_hooker(hooker_id)
    assert hooker_id not in dispatcher.hookers


def test_dispatcher_unregister_missing_id_is_noop():
    dispatcher = AllocatorHookDispatcher()
    dispatcher.unregister_hooker(12345)
    assert dispatcher.hookers == {}
