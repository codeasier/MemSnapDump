from memsnapdump.base import TraceEntry
from memsnapdump.simulate import SimulateDeviceSnapshot


class Hooker:
    def __init__(self, pre=True, post=True):
        self.pre = pre
        self.post = post
        self.calls = []

    def pre_undo_event(self, event, snapshot):
        self.calls.append(("pre", event.idx))
        return self.pre

    def post_undo_event(self, event, snapshot):
        self.calls.append(("post", event.idx))
        return self.post


class AllocatorHooker:
    pass


def make_snapshot_dict(action="alloc", with_segment=False):
    payload = {
        "segments": [],
        "device_traces": [[{"action": action, "addr": 1, "size": 1, "stream": 0, "frames": []}]],
    }
    if with_segment:
        payload["segments"] = [{
            "address": 1,
            "total_size": 16,
            "stream": 0,
            "segment_type": "small",
            "allocated_size": 0,
            "active_size": 0,
            "device": 0,
            "is_expandable": False,
            "frames": [],
            "blocks": [],
        }]
    return payload


def test_simulate_device_snapshot_raises_on_empty_snapshot():
    try:
        SimulateDeviceSnapshot({}, 0)
        assert False, "expected runtime error"
    except RuntimeError:
        assert True


def test_simulate_device_snapshot_sets_workspace_flag_from_first_event():
    snapshot = SimulateDeviceSnapshot(make_snapshot_dict("workspace_snapshot"), 0)

    assert snapshot.simulated_allocator_context.workspace_flag is True


def test_simulate_register_unregister_hookers_and_allocator_hookers():
    snapshot = SimulateDeviceSnapshot(make_snapshot_dict(), 0)
    hooker = Hooker()
    allocator_hooker = AllocatorHooker()

    hook_id = snapshot.register_hooker(hooker)
    alloc_id = snapshot.register_allocator_hooker(allocator_hooker)
    snapshot.unregister_hooker(hook_id)
    snapshot.unregister_allocator_hooker(alloc_id)

    assert hook_id not in snapshot.hookers
    assert alloc_id not in snapshot.simulated_allocator.dispatcher.hookers


def test_simulate_replay_stops_when_pre_hook_returns_false():
    snapshot = SimulateDeviceSnapshot(make_snapshot_dict(), 0)
    hooker = Hooker(pre=False)
    snapshot.register_hooker(hooker)

    assert snapshot.replay() is False
    assert hooker.calls == [("pre", 0)]


def test_simulate_replay_stops_when_post_hook_returns_false():
    snapshot = SimulateDeviceSnapshot(make_snapshot_dict("free", with_segment=True), 0)
    hooker = Hooker(post=False)
    snapshot.register_hooker(hooker)

    assert snapshot.replay() is False
    assert hooker.calls == [("pre", 0), ("post", 0)]
