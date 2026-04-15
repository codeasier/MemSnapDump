[English](README.md)

# MemSnapDump

MemSnapDump 是一个用于回放、切片和导出 `torch` / `torch_npu` 内存快照的工具集。

## 核心能力
- 回放 snapshot 历史事件，重建 allocator 状态变化
- 将大型 snapshot 文件切成更小的数据片段，便于局部分析
- 将 snapshot 数据导出到 SQLite，便于后续分析与工具集成

## 安装

```bash
pip install memsnapdump
```

用于开发：

```bash
python -m pip install -e .[dev]
```

## 快速开始

查看可用命令：

```bash
memsnapdump -h
memsnapdump --help
memsnapdump --version
memsnapdump split -h
memsnapdump dump2db -h
```

### 切分大型快照

```bash
memsnapdump split /data/snapshot.pickle --slices 4
```

### 导出快照到 SQLite

```bash
memsnapdump dump2db /data/snapshot.pickle -o /data/output
```

## 扩展与定制化开发

对于内存快照回放，Python API 的主要定位不是快速命令式使用，而是服务于扩展与定制化开发。你可以在回放过程中注册自定义 hook，在 allocator 状态重建时接入自己的统计、校验、导出或可观测性逻辑。

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
