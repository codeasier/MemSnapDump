# tools 模块 Agent 指南

## 模块职责

`tools` 模块提供内存快照处理的命令行工具，包括快照切片和快照转数据库功能。

## 目录结构

```
tools/
├── split.py           # 快照切片命令行入口
├── dump2db.py         # 快照转数据库命令行入口
├── slice_dump/        # 切片功能核心实现
│   ├── dump.py        # 参数解析与入口
│   └── hooker.py      # SliceDumpHooker 实现
└── adaptors/          # 数据适配器
    ├── snapshot2db.py # 数据库转换核心实现（支持多设备）
    └── database/      # 数据库相关定义
```

## 多设备支持

快照转数据库功能现已支持多设备快照。每个设备的数据存储在独立的数据库表中，表名带有设备后缀（如 `trace_entry_0`, `block_0`）。

## 快照切片 (split)

### 功能
将大型快照文件按事件数量切分为多个小文件，便于分片分析。

### 命令行
```bash
python tools.split <snapshot_file> [options]

参数:
  snapshot_file        快照文件路径（必需）
  --device, -d         设备索引，默认 0
  --slices, -s         切片数量，默认 4
  --max_entries, -m    单片最大事件数，默认 15000
  --dump_dir, -o       输出目录，默认为快照文件所在目录
  --dump_type, -t      输出格式 (pkl/json)，默认 pkl
```

### 切片策略

**方式一：固定切片数**
```bash
python tools.split snapshot.pkl --slices 4
```
将 N 个事件平均分为 4 份。

**方式二：固定最大事件数**
```bash
python tools.split snapshot.pkl --max_entries 20000
```
每片最多 20000 个事件。

### 输出文件命名
```
slice_<序号>_entry_<起始>_<结束>.<格式>
```

### 核心实现
- `SliceDumpHooker`: 继承 `SimulateHooker`，在回放过程中按条件切分数据

## 快照转数据库 (dump2db)

### 功能
将快照数据转换为 SQLite 数据库，便于查询和分析。

### 命令行
```bash
python tools.dump2db <snapshot_file> [options]

参数:
  snapshot_file        快照文件路径（必需）
  --dump_dir, -o       输出目录，默认为快照文件所在目录
```

### 数据库表结构

#### trace_entry 表
| 字段 | 类型 | 说明 |
|-----|------|------|
| id | INTEGER | 事件ID（主键）|
| action | INTEGER | 动作类型编码 |
| address | INTEGER | 内存地址 |
| size | INTEGER | 大小 |
| stream | INTEGER | CUDA 流 |
| allocated | INTEGER | 已分配总量 |
| active | INTEGER | 活跃总量 |
| reserved | INTEGER | 内存池总量 |
| callstack | TEXT | 调用栈 |

#### block 表
| 字段 | 类型 | 说明 |
|-----|------|------|
| id | INTEGER | 块ID（主键）|
| address | INTEGER | 地址 |
| size | INTEGER | 大小 |
| requestedSize | INTEGER | 请求大小 |
| state | INTEGER | 状态编码 |
| allocEventId | INTEGER | 分配事件ID |
| freeEventId | INTEGER | 释放事件ID |

### 核心实现
- `DumpEventHooker`: 同时继承 `SimulateHooker` 和 `AllocatorHooker`
- `SnapshotDbHandler`: 数据库批量写入处理器

## 扩展新工具

### 步骤
1. 在 `tools/` 下创建子模块目录
2. 实现继承 `SimulateHooker` 的钩子类
3. 创建命令行入口脚本
4. 在根目录 `tools/` 下添加入口函数

### 示例：峰值分析工具
```python
# tools/peak_analysis/hooker.py
from simulate import SimulateHooker
from base import TraceEntry, DeviceSnapshot

class PeakAnalysisHooker(SimulateHooker):
    def __init__(self):
        self.peak_allocated = 0
        self.peak_event_idx = -1
    
    def post_undo_event(self, event: TraceEntry, snapshot: DeviceSnapshot) -> bool:
        if snapshot.total_allocated > self.peak_allocated:
            self.peak_allocated = snapshot.total_allocated
            self.peak_event_idx = event.idx
        return True

# tools/peak_analysis.py
def peak_analysis():
    args = get_args()
    snapshot = SimulateDeviceSnapshot(load_pickle_to_dict(args.snapshot_file))
    hooker = PeakAnalysisHooker()
    snapshot.register_hooker(hooker)
    snapshot.replay()
    print(f"Peak: {hooker.peak_allocated} at event {hooker.peak_event_idx}")
```

## 注意事项

1. **内存管理**: 切片时使用 `copy.deepcopy` 保存内存状态
2. **批量写入**: 数据库写入使用缓存，默认每 1000 条提交一次
3. **进度显示**: 回放过程中会输出进度日志
