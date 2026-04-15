[中文文档](README.zh.md)

# MemSnapDump

MemSnapDump is a toolkit for replaying, slicing, and exporting memory snapshots collected from `torch` / `torch_npu`.

## What it does
- Replay snapshot event history to reconstruct allocator state changes
- Slice large snapshot files into smaller pieces for focused inspection
- Export snapshot data into SQLite for downstream analysis and tooling

## Installation

```bash
pip install memsnapdump
```

For development:

```bash
python -m pip install -e .[dev]
```

## Quick start

Check the available commands:

```bash
memsnapdump -h
memsnapdump --help
memsnapdump --version
memsnapdump split -h
memsnapdump dump2db -h
```

### Split a large snapshot

```bash
memsnapdump split /data/snapshot.pickle --slices 4
```

### Export a snapshot to SQLite

```bash
memsnapdump dump2db /data/snapshot.pickle -o /data/output
```

## Extension and customization

For memory snapshot replay, the Python API is intended primarily for extension and custom development rather than quick CLI-style usage. You can register custom hooks into the replay process to add your own statistics, validation, export, or observability logic while allocator state is reconstructed.

```python
from pathlib import Path

from memsnapdump.simulate import SimulateDeviceSnapshot, SimulateHooker
from memsnapdump.util.file_util import load_pickle_to_dict


class EventCounterHooker(SimulateHooker):
    def __init__(self):
        self.count = 0

    def pre_undo_event(self, wait4undo_event, current_snapshot) -> bool:
        self.count += 1
        return True

    def post_undo_event(self, already_undo_event, current_snapshot) -> bool:
        return True


snapshot_dict = load_pickle_to_dict(Path("tests/test_data/snapshot_expandable.pkl"))
snapshot = SimulateDeviceSnapshot(snapshot_dict, 0)

hooker = EventCounterHooker()
snapshot.register_hooker(hooker)
snapshot.replay()

print(f"replayed events: {hooker.count}")
```

## Documentation
- [Getting started](docs/en/getting-started.md)
- [Replay guide](docs/en/user-guide/replay.md)
- [Split guide](docs/en/user-guide/split.md)
- [Dump-to-database guide](docs/en/user-guide/dump2db.md)
- [SQLite schema reference](docs/en/reference/snapshot-db-schema.md)
- [Development guide](docs/en/development/development-guide.md)

## Development checks

```bash
ruff check .
black --check .
pytest --cov=memsnapdump --cov-fail-under=85
```

## Related links
- [PyTorch: Understanding CUDA Memory Usage](https://docs.pytorch.org/docs/stable/torch_cuda_memory.html)
- [memory_viz](https://pytorch.org/memory_viz)

Contributions are welcome via issues and pull requests.
