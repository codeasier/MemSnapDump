[中文](../zh/getting-started.md)

# Getting Started

This guide covers the shortest path to using MemSnapDump effectively.

## Prerequisites
- Python 3.10+
- A snapshot produced by `torch` or `torch_npu`
- Historical memory events enabled during collection if you want replay, slicing, or DB export

## Install

```bash
python -m pip install -e .[dev]
```

## Collecting a usable snapshot
Replay-based features require historical memory events to be recorded before dumping the snapshot.

```python
# torch_npu
# import torch_npu
torch_npu.npu.memory._record_memory_history()

# NVIDIA CUDA
# import torch
torch.cuda.memory._record_memory_history()
```

## Main workflows
### 1. Replay a snapshot
Use replay when you want to traverse historical events and observe allocator state transitions.

See: [Replay guide](user-guide/replay.md)

### 2. Slice a large snapshot
Use slicing when a snapshot is too large to inspect conveniently in `memory_viz`.

See: [Split guide](user-guide/split.md)

### 3. Export to SQLite
Use SQLite export when you want structured querying, offline analysis, or custom visualization pipelines.

See: [Dump-to-database guide](user-guide/dump2db.md)

## Development and validation

```bash
ruff check .
black --check .
pytest --cov=memsnapdump --cov-fail-under=85
```

See also: [Development guide](development/development-guide.md)
