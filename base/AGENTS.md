# base 模块 Agent 指南

## 模块职责

`base` 模块定义了内存快照分析的核心数据模型和实体类，是整个项目的数据基础。

## 核心类

### Frame
调用栈帧信息，记录代码位置。

```python
@dataclass
class Frame:
    filename: str    # 文件名
    line: int        # 行号
    name: str        # 函数名
```

### TraceEntry
内存事件记录，对应 PyTorch 内存分配器的每一次操作。

```python
@dataclass
class TraceEntry:
    action: str      # 事件类型
    addr: int        # 内存地址
    size: int        # 内存大小
    stream: int      # CUDA 流
    frames: List[Frame]  # 调用栈
    idx: int         # 全局索引
```

**事件类型说明**:
- `alloc`: 内存分配
- `free`: 内存释放（旧版）
- `free_requested`: 释放请求
- `free_completed`: 释放完成
- `segment_alloc`: 内存段申请
- `segment_free`: 内存段释放
- `segment_map`/`segment_unmap`: 虚拟内存映射操作
- `oom`: 内存溢出
- `snapshot`: 快照标记

### Block
内存块，表示已分配或缓存的内存单元。

```python
@dataclass
class Block:
    size: int              # 实际大小
    requested_size: int    # 请求大小
    address: int           # 地址
    state: str             # 状态
    frames: List[Frame]    # 分配时的调用栈
    segment_ptr: Segment   # 所属内存段
    alloc_event_idx: int   # 分配事件索引
    free_event_idx: int    # 释放事件索引
```

**状态说明**:
- `active_allocated`: 已分配，正在使用
- `active_pending_free`: 等待释放（多流场景）
- `inactive`: 空闲，可复用

### Segment
内存段，表示从设备申请的连续内存区域。

```python
@dataclass
class Segment:
    address: int           # 起始地址
    total_size: int        # 总大小
    stream: int            # CUDA 流
    segment_type: str      # 'small' 或 'large'
    allocated_size: int    # 已分配大小
    active_size: int       # 活跃大小
    blocks: List[Block]    # 内存块列表
    is_expandable: bool    # 是否可扩展（虚拟内存）
```

### DeviceSnapshot
设备内存快照，包含某一时刻的完整内存状态。

```python
class DeviceSnapshot:
    segments: List[Segment]       # 内存段列表
    trace_entries: List[TraceEntry]  # 事件序列
    total_allocated: int   # 已分配总量
    total_reserved: int    # 内存池总量
    total_activated: int   # 活跃内存总量
```

## 关键方法

### 数据解析
```python
# 从字典创建
snapshot = DeviceSnapshot.from_dict(snapshot_dict, device=0)

# 转换为字典
data = snapshot.to_dict()
```

### 地址查找
```python
# 查找地址所在的内存段索引
seg_idx = snapshot.find_segment_idx_by_addr(addr)

# 查找地址所在的内存块索引
block_idx = segment.find_block_idx_by_block_addr(block_addr)
```

## 使用示例

```python
from base import DeviceSnapshot, TraceEntry, Block, Segment
import pandas as pd

# 加载快照
df = pd.read_pickle('snapshot.pkl')
snapshot = DeviceSnapshot.from_dict(df, device=0)

# 遍历事件
for event in snapshot.trace_entries:
    print(f"Event {event.idx}: {event.action} @ {hex(event.addr)}")

# 遍历内存段
for seg in snapshot.segments:
    print(f"Segment @ {hex(seg.address)}, size={seg.total_size}")
```

## 注意事项

1. **只读属性**: `_origin` 属性保存原始字典，用于无损序列化
2. **地址排序**: segments 和 blocks 按地址排序，支持二分查找
3. **引用关系**: Block 通过 `segment_ptr` 引用所属 Segment
