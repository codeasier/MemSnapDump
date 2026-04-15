[中文文档](README.zh.md)

# MemSnapDump

MemSnapDump is a toolkit for replaying, slicing, and exporting memory snapshots collected from `torch` / `torch_npu`.

## What it does
- Replay snapshot event history to reconstruct allocator state changes
- Slice large snapshot files into smaller pieces for focused inspection
- Export snapshot data into SQLite for downstream analysis and tooling

## Installation

```bash
python -m pip install -e .[dev]
```

## Quick start

### Replay a snapshot in Python

```python
import pandas as pd
from memsnapdump.simulate import SimulateDeviceSnapshot

snapshot_dict = pd.read_pickle("tests/test_data/snapshot_expandable.pkl")
snapshot = SimulateDeviceSnapshot(snapshot_dict, 0)
snapshot.replay()
```

### Split a large snapshot

```bash
python -m memsnapdump.tools.split /data/snapshot.pickle --slices 4
```

### Export a snapshot to SQLite

```bash
python -m memsnapdump.tools.dump2db /data/snapshot.pickle -o /data/output
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
