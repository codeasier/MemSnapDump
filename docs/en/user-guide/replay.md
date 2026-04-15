[中文](../../zh/user-guide/replay.md)

# Replay Guide

Replay is the core mechanism behind MemSnapDump. It walks backward through recorded memory events and reconstructs allocator state changes over time.

## When to use replay
Use replay when you need to:
- inspect allocator state evolution
- attach hooks before and after a single event is undone
- build tools such as slicing and SQLite export on top of replay

## Requirements
The snapshot must contain historical memory events in `device_traces`.

## Core API
The main implementation lives in `src/memsnapdump/simulate/simulate.py`.

Typical usage:

```python
import pandas as pd
from memsnapdump.simulate import SimulateDeviceSnapshot

snapshot_dict = pd.read_pickle("tests/test_data/snapshot_expandable.pkl")
snapshot = SimulateDeviceSnapshot(snapshot_dict, 0)
snapshot.replay()
```

## Hook model
Replay supports two hook layers:
- `SimulateHooker`: hooks around per-event undo
- `AllocatorHooker`: hooks around allocator block / segment operations

This lets you inspect state without reimplementing replay internals.

## Example: custom event hook

```python
from memsnapdump.base import TraceEntry, DeviceSnapshot
from memsnapdump.simulate import SimulateDeviceSnapshot, SimulateHooker


class ExamplePrintHooker(SimulateHooker):
    def pre_undo_event(self, wait4undo_event: TraceEntry, current_snapshot: DeviceSnapshot) -> bool:
        print(wait4undo_event.to_dict())
        return True

    def post_undo_event(self, already_undo_event: TraceEntry, current_snapshot: DeviceSnapshot) -> bool:
        print(already_undo_event.to_dict())
        return True
```

Register the hook and start replay:

```python
snapshot.register_hooker(ExamplePrintHooker())
snapshot.replay()
```

## Notes
- Replay processes events in reverse order.
- Features such as slicing and DB export are built on top of the same replay foundation.
- If a snapshot has no historical events, replay-based functionality cannot proceed.
