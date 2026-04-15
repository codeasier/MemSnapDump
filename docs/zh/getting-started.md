[English](../en/getting-started.md)

# 快速开始

本指南提供使用 MemSnapDump 的最短路径。

## 前置条件
- Python 3.10+
- 由 `torch` 或 `torch_npu` 采集得到的 snapshot 文件
- 如果要使用回放、切片或数据库导出功能，需要在采集时启用历史内存事件记录

## 安装

```bash
python -m pip install -e .[dev]
```

## 如何采集可用的 snapshot
基于回放的功能要求在 dump snapshot 之前先启用历史事件记录。

```python
# torch_npu
# import torch_npu
torch_npu.npu.memory._record_memory_history()

# NVIDIA CUDA
# import torch
torch.cuda.memory._record_memory_history()
```

## 主要使用流程
### 1. 回放快照
当你需要遍历历史事件并观察 allocator 状态变化时，使用回放功能。

参见：[快照回放说明](user-guide/replay.md)

### 2. 切分大型快照
当 snapshot 过大，不方便直接在 `memory_viz` 中查看时，使用切片功能。

参见：[快照切片说明](user-guide/split.md)

### 3. 导出到 SQLite
当你需要结构化查询、离线分析或自定义可视化时，使用数据库导出功能。

参见：[快照转数据库说明](user-guide/dump2db.md)

## 开发与校验

```bash
ruff check .
black --check .
pytest --cov=memsnapdump --cov-fail-under=85
```

另见：[开发指南](development/development-guide.md)
