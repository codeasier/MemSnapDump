[English](../../en/user-guide/replay.md)

# 快照回放说明

回放是 MemSnapDump 的核心机制。它会逆序遍历已记录的内存事件，并逐步重建 allocator 状态随时间的变化过程。

## 适用场景
当你需要以下能力时，应使用回放：
- 观察 allocator 状态演进
- 在单个事件回滚前后挂接钩子逻辑
- 基于回放构建切片、SQLite 导出等能力

## 使用要求
snapshot 必须在 `device_traces` 中包含历史内存事件。

## 核心 API
主要实现位于 `src/memsnapdump/simulate/simulate.py`。

典型用法：

```python
import pandas as pd
from memsnapdump.simulate import SimulateDeviceSnapshot

snapshot_dict = pd.read_pickle("tests/test_data/snapshot_expandable.pkl")
snapshot = SimulateDeviceSnapshot(snapshot_dict, 0)
snapshot.replay()
```

## 钩子模型
回放支持两层钩子：
- `SimulateHooker`：围绕单事件回滚前后触发
- `AllocatorHooker`：围绕 allocator 的 block / segment 操作触发

这样你可以在不重写回放内部逻辑的前提下观察状态变化。

## 示例：自定义事件钩子

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

注册钩子并开始回放：

```python
snapshot.register_hooker(ExamplePrintHooker())
snapshot.replay()
```

## 说明
- 回放按事件逆序执行。
- 切片与数据库导出等功能都建立在同一套回放基础之上。
- 如果 snapshot 不包含历史事件，则无法使用基于回放的功能。
