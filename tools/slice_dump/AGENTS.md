# tools/slice_dump 模块 Agent 指南

## 模块职责

`slice_dump` 模块实现快照切片功能，将大型快照文件按事件数量切分为多个小文件。

## 文件说明

### dump.py
命令行入口，负责参数解析和流程控制。

```python
def slice_dump():
    """主入口函数"""
    args = get_args()
    df = load_pickle_to_dict(Path(args.snapshot_file))
    snapshot = SimulateDeviceSnapshot(df, 0)
    slice_dump_hooker = SliceDumpHooker(...)
    snapshot.register_hooker(slice_dump_hooker)
    snapshot.replay()
```

### hooker.py
切片核心实现，`SliceDumpHooker` 类。

## SliceDumpHooker 详解

### 初始化参数
```python
SliceDumpHooker(
    dump_dir: str,           # 输出目录
    num_of_slices: int = 4,  # 切片数量
    max_entries: int = 15000, # 单片最大事件数
    dump_type: str = "pkl"   # 输出格式
)
```

### 切片策略

**优先级**:
1. 如果 `ceil(总事件数/切片数) > max_entries`，则按 `max_entries` 切分
2. 否则按指定切片数平均切分

**示例**:
- 总事件 100，切片数 4，max_entries 30 → 按 4 片切分（每片 25）
- 总事件 100，切片数 4，max_entries 20 → 按 max_entries 切分（每片 20，共 5 片）

### 切片逻辑

```
原始数据: state.61 + evt[1:61]  (61 个事件)

方式一：按 4 片切分
├── slice_1: state.13 + evt[1:13]
├── slice_2: state.29 + evt[14:29]
├── slice_3: state.45 + evt[30:45]
└── slice_4: state.61 + evt[46:61]

方式二：按 max_entries=20 切分
├── slice_1: state.20 + evt[1:20]
├── slice_2: state.40 + evt[21:40]
├── slice_3: state.60 + evt[41:60]
└── slice_4: state.61 + evt[61:61]
```

### 核心方法

```python
def pre_undo_event(self, event, snapshot) -> bool:
    """初始化切片策略，显示进度"""
    if self.num_of_events == -1:
        self.num_of_events = len(snapshot.trace_entries)
        self._init_splitting_strategy()
        self.prev_segments = copy.deepcopy(snapshot.segments)

def post_undo_event(self, event, snapshot) -> bool:
    """缓存事件，判断是否需要 dump"""
    self.events_buffer.insert(0, event)
    if self._is_need_dump(snapshot):
        self.dump()

def dump(self):
    """执行切片输出"""
    slice_snapshot = DeviceSnapshot()
    slice_snapshot.segments = self.prev_segments
    slice_snapshot.trace_entries = self.events_buffer
    # 保存为 pkl 或 json
```

### 文件命名规则
```
slice_{序号}_entry_{起始索引}_{结束索引}.{格式}
```

例如: `slice_1_entry_1_25.pkl`

## 使用示例

### 基础用法
```bash
python tools.split /data/snapshot.pkl --slices 4
```

### 指定输出目录和格式
```bash
python tools.split /data/snapshot.pkl -o /output -t json --slices 8
```

### 按最大事件数切分
```bash
python tools.split /data/snapshot.pkl --max_entries 10000
```

## 编程接口

```python
from tools.slice_dump.hooker import SliceDumpHooker
from simulate import SimulateDeviceSnapshot
import pandas as pd

df = pd.read_pickle('snapshot.pkl')
snapshot = SimulateDeviceSnapshot(df, 0)

hooker = SliceDumpHooker(
    dump_dir='./output',
    num_of_slices=4,
    max_entries=15000,
    dump_type='pkl'
)
snapshot.register_hooker(hooker)
snapshot.replay()
```

## 注意事项

1. **内存拷贝**: 每次切片都会深拷贝 segments，注意内存占用
2. **事件顺序**: `events_buffer.insert(0, event)` 保持事件顺序
3. **空快照**: 无事件记录的快照会直接返回，不做处理
4. **进度日志**: 默认在 25%、50%、75% 时输出进度
