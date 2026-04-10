# simulate 模块 Agent 指南

## 模块职责

`simulate` 模块实现了内存快照的回放模拟引擎，是项目的核心功能模块。通过倒序回放事件，重建任意时刻的内存状态。

## 核心类

### SimulateDeviceSnapshot

可回放的设备快照类，提供事件回放和钩子注册功能。

```python
class SimulateDeviceSnapshot:
    def __init__(self, snapshot_dict: dict, device: int = 0)
    def register_hooker(self, hooker: SimulateHooker) -> int
    def unregister_hooker(self, hooker_id: int)
    def register_allocator_hooker(self, hooker: AllocatorHooker) -> int
    def unregister_allocator_hooker(self, hooker_id: int)
    def replay(self) -> bool
```

**使用流程**:
1. 加载快照数据
2. 注册钩子（可选）
3. 调用 `replay()` 开始回放

### SimulatedCachingAllocator

模拟的缓存内存分配器，处理内存块和内存段的分配/释放操作。

```python
class SimulatedCachingAllocator:
    # Block 操作
    def alloc_block(self, new_block: Block) -> bool
    def free_block(self, alloc_event: TraceEntry) -> bool
    def active_block(self, free_requested_event: TraceEntry) -> bool
    
    # Segment 操作
    def alloc_or_map_segment(self, new_segment: Segment, merge: bool = False) -> bool
    def free_segment(self, alloc_seg_event: TraceEntry) -> bool
    def unmap_segment(self, map_event: TraceEntry) -> bool
    
    # 辅助方法
    def find_gap_for_alloc_block(self, event_addr: int, event_size: int) -> Optional[Tuple[Segment, int]]
    def find_block_by_addr(self, seg_idx: int, block_addr: int) -> Optional[Block]
    def find_segment_by_exact_addr(self, addr: int, stream: int) -> Optional[Segment]
    def insert_segment_sorted(self, segment: Segment)
    def split_segment_at(self, seg_idx: int, cut_addr: int, cut_size: int) -> bool
    def shrink_segment(self, seg_idx: int, shrink_addr: int, shrink_size: int, direction: str) -> bool
    def merge_segments(self, target_idx: int, source_idx: int) -> bool
```

### AllocatorContext

分配器上下文，保存回放过程中的状态。

```python
class AllocatorContext:
    device_snapshot: DeviceSnapshot   # 当前快照
    current_undo_event: TraceEntry    # 当前回放事件
    workspace_flag: bool              # 昇腾 workspace 标志
    
    def set_current_undo_event(self, undo_event: TraceEntry)
```

## 钩子系统

### SimulateHooker

事件级钩子，在事件回放前后触发。

```python
class SimulateHooker(ABC):
    @abstractmethod
    def pre_undo_event(self, wait4undo_event: TraceEntry, 
                       current_snapshot: DeviceSnapshot) -> bool
    
    @abstractmethod
    def post_undo_event(self, already_undo_event: TraceEntry, 
                        current_snapshot: DeviceSnapshot) -> bool
```

**触发时机**:
- `pre_undo_event`: 事件回放前，事件仍在列表中
- `post_undo_event`: 事件回放后，内存状态已更新

**返回值**: 返回 `False` 会中断回放

### AllocatorHooker

内存操作级钩子，在块/段操作前后触发。

```python
class AllocatorHooker(ABC):
    # Block 操作钩子
    def pre_replay_alloc_block(self, wait4alloc_block: Block, current_snapshot: DeviceSnapshot)
    def post_replay_alloc_block(self, allocated_block: Block, current_snapshot: DeviceSnapshot)
    def pre_replay_free_block(self, wait4free_block: Block, current_snapshot: DeviceSnapshot)
    def post_replay_free_block(self, released_block: Block, current_snapshot: DeviceSnapshot)
    
    # Segment 操作钩子
    def pre_replay_map_or_alloc_segment(self, wait4alloc_map_segment: Segment, current_snapshot: DeviceSnapshot)
    def post_replay_map_or_alloc_segment(self, allocated_mapped_segment: Segment, current_snapshot: DeviceSnapshot)
    def pre_replay_unmap_or_free_segment(self, wait4release_segment: Segment, current_snapshot: DeviceSnapshot)
    def post_replay_unmap_or_free_segment(self, released_segment: Segment, current_snapshot: DeviceSnapshot)
```

**参数说明**:
- `wait4xxx`: 待操作的块/段（只读）
- `allocated_xxx`/`released_xxx`: 操作后的块/段（副本）
- `current_snapshot`: 当前内存快照（只读）

## 回放机制详解

### 事件映射

回放时，事件与操作的对应关系（倒序）:

| 事件类型 | 回放操作 | 说明 |
|---------|---------|------|
| `free`/`free_completed` | `alloc_block` | 回滚释放 = 分配块 |
| `free_requested` | `active_block` | 回滚释放请求 = 激活块（PENDING_FREE → ALLOCATED） |
| `alloc` | `free_block` | 回滚分配 = 释放块 |
| `segment_free`/`segment_unmap` | `alloc_or_map_segment` | 回滚段释放 = 分配/映射段 |
| `segment_alloc` | `free_segment` | 回滚段分配 = 释放段 |
| `segment_map` | `unmap_segment` | 回滚映射 = 取消映射段 |
| `workspace_snapshot` | 跳过 | 昇腾 workspace 快照标记 |

### 内存段操作细节

#### 分配/映射段 (`alloc_or_map_segment`)
- `merge=False`: 普通分配，直接插入排序后的段列表
- `merge=True`: 虚拟内存映射，尝试与相邻段合并

#### 释放段 (`free_segment`)
- 要求段内无活跃分配 (`active_size == 0`)
- 从段列表中移除

#### 取消映射段 (`unmap_segment`)
- 支持从左/右收缩或分割段
- 虚拟内存场景使用

### 内存块对齐

分配时按 512 字节对齐，并预留 32 字节：
```python
aligned_size = math.ceil((requested_size + 32) / 512) * 512
```

### 昇腾 Workspace 兼容

自动识别 `workspace_snapshot` 事件，启用容忍模式：
- 允许找不到 block 的情况
- 允许 block 状态不匹配的情况

## 使用示例

### 基础回放

```python
from simulate import SimulateDeviceSnapshot
import pandas as pd

df = pd.read_pickle('snapshot.pkl')
snapshot = SimulateDeviceSnapshot(df, device=0)
snapshot.replay()
```

### 自定义事件钩子

```python
from simulate import SimulateHooker
from base import TraceEntry, DeviceSnapshot

class MyHooker(SimulateHooker):
    def pre_undo_event(self, event: TraceEntry, snapshot: DeviceSnapshot) -> bool:
        print(f"About to replay: {event.action}")
        return True  # 返回 False 可中断回放
    
    def post_undo_event(self, event: TraceEntry, snapshot: DeviceSnapshot) -> bool:
        print(f"Replayed: {event.action}, allocated={snapshot.total_allocated}")
        return True

snapshot = SimulateDeviceSnapshot(df, device=0)
hooker_id = snapshot.register_hooker(MyHooker())
snapshot.replay()
# 注销钩子
snapshot.unregister_hooker(hooker_id)
```

### 内存操作钩子

```python
from simulate import AllocatorHooker
from base import Block, DeviceSnapshot

class BlockTracker(AllocatorHooker):
    def post_replay_free_block(self, block: Block, snapshot: DeviceSnapshot):
        print(f"Block freed: addr={hex(block.address)}, size={block.size}")

snapshot = SimulateDeviceSnapshot(df, device=0)
allocator_hooker_id = snapshot.register_allocator_hooker(BlockTracker())
snapshot.replay()
# 注销钩子
snapshot.unregister_allocator_hooker(allocator_hooker_id)
```

## 注意事项

1. **倒序回放**: 事件从最后一个开始向前处理
2. **只读快照**: 钩子中传入的 snapshot 应视为只读
3. **返回值**: 钩子返回 False 会中断回放
4. **昇腾兼容**: 自动识别 `workspace_snapshot` 事件，启用容错模式
5. **进度日志**: 回放过程会输出 25%、50%、75%、100% 进度日志
6. **钩子管理**: 支持动态注册/注销钩子，返回的 ID 用于注销
