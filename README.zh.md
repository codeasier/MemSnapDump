[English](README.md)

# MemSnapDump

MemSnapDump 是一个用于回放、切片和导出 `torch` / `torch_npu` 内存快照的工具集。

## 核心能力
- 回放 snapshot 历史事件，重建 allocator 状态变化
- 将大型 snapshot 文件切成更小的数据片段，便于局部分析
- 将 snapshot 数据导出到 SQLite，便于后续分析与工具集成

## 安装

```bash
python -m pip install -e .[dev]
```

## 快速开始

### 在 Python 中回放快照

```python
import pandas as pd
from memsnapdump.simulate import SimulateDeviceSnapshot

snapshot_dict = pd.read_pickle("tests/test_data/snapshot_expandable.pkl")
snapshot = SimulateDeviceSnapshot(snapshot_dict, 0)
snapshot.replay()
```

### 切分大型快照

```bash
python -m memsnapdump.tools.split /data/snapshot.pickle --slices 4
```

### 导出快照到 SQLite

```bash
python -m memsnapdump.tools.dump2db /data/snapshot.pickle -o /data/output
```

## 文档导航
- [快速开始](docs/zh/getting-started.md)
- [快照回放说明](docs/zh/user-guide/replay.md)
- [快照切片说明](docs/zh/user-guide/split.md)
- [快照转数据库说明](docs/zh/user-guide/dump2db.md)
- [SQLite Schema 参考](docs/zh/reference/snapshot-db-schema.md)
- [开发指南](docs/zh/development/development-guide.md)

## 开发检查

```bash
ruff check .
black --check .
pytest --cov=memsnapdump --cov-fail-under=85
```

## 相关链接
- [PyTorch: Understanding CUDA Memory Usage](https://docs.pytorch.org/docs/stable/torch_cuda_memory.html)
- [memory_viz](https://pytorch.org/memory_viz)

欢迎通过 issue 和 PR 参与改进。
