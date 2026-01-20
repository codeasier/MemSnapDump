# MemSnapDump
本工具用于对 `torch / torch_npu` 采集的内存快照（`snapshot`）文件进行分析、处理。
## 1. 前言
项目持续更新中...
如果您有好的想法、建议或诉求，欢迎您提交issue及PR。
### 1.1 memory snapshot
可参考：[Understanding CUDA Memory Usage](docpys.pytorch.org/docs/stable/torch_cuda_memory.html)中的采集与可视化方法。
### 1.2 可视化：memory_viz
pytorch社区提供了snapshot数据可视化的工具[memory_viz](https://pytorch.org/memory_viz)。

虽然其功能已经足够强大，但仍然存在一些痛点，如：
- Snapshot数据量较大（尤其entries量大时）时，性能瓶颈较为严重，如`Active Memory Timeline`卡顿，缩放耗时长等；`Allocator State History`点击事件搜索卡顿、点击事件后卡顿等。
- 联动分析易用性不足，如`Timeline`与`State History`仅能通过地址进行关联。调用栈无法直接搜索等。

本项目旨在提供一些：
- `数据分析能力`(暂未实现）：利用固化的经验直接分析snapshot数据识别一些常见的显存问题，如`内存泄漏`、`碎片分析`、`峰值拆解`等能力。
- `数据剪裁能力`：针对数据量较大的场景，能够对数据进行无损剪裁或切片，以支持分片后导入memory_viz进行局部的内存分析。
- ...
<a id="1.3"></a>
### 1.3 关于内存快照数据的一些简单说明与理解
内存快照数据，其核心组成包含量部分：
- （dump时刻，静态的）内存段状态`segments`：即调用`_dump_snapshot`**时刻**的，当前PyTorch内存池组成与状态的数据。
- （从使能开始到dump之间历史的发生过的，动态的）内存事件序列`device_traces`：即从开始记录到dump时发生过的历史内存事件。

而memory_viz之所以能在`Timeline`查看随“时间”变化的内存块生命周期、`State History`查看任意事件发生时的内存池状态，主要就是基于上述dump时刻的静态数据+ _**回放**_
历史事件形成了动态的可视化呈现。

因此可以做出如下简单的定义：
- 第x个事件发生时的内存段状态：`state.x`
- 从第x1个事件到第x2个事件的序列：`evt[x1:x2]`

对于任意时刻dump出的内存快照数据，假设其在dump前一共记录了X个内存事件，那么该内存快照实际承载的数据可以简单表示为

`state.X + evt[1:X]`
## 2. 核心功能说明
### 2.1 快照回放
#### 2.1.1 简介
如[前言](#13-关于内存快照数据的一些简单说明与理解)所述，对于snapshot
数据，如果想要分析采集时段内的内存分配情况或进行数据剪裁，进行`快照回放`将是一个必不可少的功能。本项目当前`快照回放`功能，作为一个基础功能，主要用于进行内存回放，并在回放过程中支持`注册单事件回放前、后钩子`，以便使用者能够不必花费过多时间了解内存事件回放的原理、过程与各类内存池状态的转化处理。
#### 2.1.2 使用约束
- 采集的内存快照数据需要包含历史内存事件
```python
# 昇腾torch_npu
# import torch_npu
torch_npu.npu.memory._record_memory_history()
# Nvdia
# import torch
torch.cuda.memory._record_memory_history()
```
#### 2.1.3 使用方式
核心回放实现 `simulate/simulate.py`，其中`SimulateHooker`钩子类如下：
```python
class SimulateHooker(ABC):
    @abstractmethod
    def pre_undo_event(self, wait4undo_event: TraceEntry, current_snapshot: DeviceSnapshot) -> bool:
        """
            【READONLY】在回放事件前回调，此时事件列表**并未POP**出该事件
        :param wait4undo_event: （只读）待回放的事件（仍在事件列表中）
        :param current_snapshot: （制度）当前的内存块快照
        :return 返回true继续执行，返回false将中断
        """
        ...

    @abstractmethod
    def post_undo_event(self, already_undo_event: TraceEntry, current_snapshot: DeviceSnapshot):
        """
            【READONLY】在回放事件后回调，此时snapshot已经将该事件从事件列表中丢弃，且segments已回放到事件发生前
        :param already_undo_event: 已回放的事件
        :param current_snapshot: （只读）当前内存快照
        :return 返回true继续执行，返回false将中断
        """
        ...
```
使用示例代码如下：
```python
from base import TraceEntry, DeviceSnapshot
from simulate import SimulateDeviceSnapshot, SimulateHooker


class ExamplePrintHooker(SimulateHooker):
    def post_undo_event(self, already_undo_event: TraceEntry, current_snapshot: DeviceSnapshot) -> bool:
        print(already_undo_event.to_dict())
        return True

    def pre_undo_event(self, wait4undo_event: TraceEntry, current_snapshot: DeviceSnapshot) -> bool:
        print(wait4undo_event.to_dict())
        return True


if __name__ == '__main__':
    import pandas as pd

    df = pd.read_pickle('test-data/snapshot.pkl')  # 基于pandas解析pickle文件
    snapshot = SimulateDeviceSnapshot(df, 0)  # 初始化可回放的snapshot对象
    snapshot.register_hooker(ExamplePrintHooker())  # 注册样例钩子
    snapshot.replay()  # 开始回放

```

### 2.2 快照切片
#### 2.2.1 简介
快照切片当前可按照事件顺序平均切分固定个数，或按照固定最大事件数量，对快照文件进行切分。在采集的数据量较大的情况下，可通过该脚本进行剪裁后先局部细节分析。
#### 2.2.2 使用约束
同[快照回放](#212-使用约束)功能
#### 2.2.3 使用方式
```shell
# 在项目根目录下执行
python dump.py [-h] [--device DEVICE] [--slices SLICES] [--max_entries MAX_ENTRIES] [--dump_dir DUMP_DIR] [--dump_type {pkl,json}] snapshot_file
```
  | 参数                  | 类型 | 必填 | 默认值            | 说明                                                                    |
  |---------------------|------|------|----------------|-----------------------------------------------------------------------|
  | `<snapshot_file>`   | 路径 | ✅ 是 | —              | 输入的 snapshot pickle 文件路径                                              |
  | `--dump_dir`, `-d`  | 路径 | 否 | snapshot文件所在目录 | 切片转储输出目录                                                              |
  | `--slices`, `-s`    | 整数 ≥1 | 否 | `4`            | <br/>指定将事件平均切分为多少个片段；<br/>❗仅当按照`slices`平均切片后单片事件数量不超过`max_entries`时生效 |
  | `--max_entries`     | 整数 ≥1 | 否 | `15000`        | 单个切片最多包含的事件数（若指定 `slices`，此参数作为上限）                                    |
  | `--dump_type`, `-f` | `pkl` \| `json` | 否 | `pkl`          | 转储文件格式，仅支持 `pkl` 或 `json`                                             |
  | `--device`          | 整数 ≥0 | 否 | `0`            | 指定回放的设备索引（从 `device_traces` 中选择）                                      |
#### 2.3.4 示例
假设已有采集自`0`卡的snapshot文件`/data/snapshot.pickle`，其包含**61**个内存事件，其采集时刻的数据可以表示为：`state.61 + evt[1:61]`

_**方式一**_：按照固定切片数进行切片

以切分4份为例，执行如下命令：

`python dump.py /data/snapshot.pickle --slices 4`

将 61 个事件平均分为 4 个切片，每个切片约 15–16 个事件。 每段输出：该段结束时的内存状态 + 本段包含的事件列表。

| 切片 | 内存状态       | 事件范围     | 事件数量 | 输出件             |
|------|------------|--------------|----------|-----------------|
| 1    | `state.13` | `evt[1:13]`  | 13       | slice_1_entry_1_13.pkl |
| 2    | `state.29` | `evt[14:29]` | 16       | slice_2_entry_14_29.pkl |
| 3    | `state.45` | `evt[30:45]` | 16       | slice_3_entry_30_45.pkl |
| 4    | `state.61` | `evt[46:61]` | 16       | slice_4_entry_46_61.pkl |

_**方式二**_：固定单片最大事件数切片

以每片最大20个事件为例，执行如下命令
`python dump.py /data/snapshot.pickle --max_entries 20`

| 切片 | 内存状态       | 事件范围         | 事件数量 | 输出件 |
|------|------------|--------------|------| ------ |
| 1    | `state.1`  | `evt[1:1]`   | 1    | slice_1_entry_1_1.pkl |
| 2    | `state.21` | `evt[2:21]`  | 20   | slice_2_entry_2_21.pkl |
| 3    | `state.41` | `evt[22:41]` | 20   | slice_3_entry_22_41.pkl |
| 4    | `state.61` | `evt[42:61]` | 20   | slice_4_entry_42_61.pkl |


## 3. 项目结构说明
```text
MemSnapDump/
├── base/               # 基础Snapshot相关数据模型与实体定义
│   ├── __init__.py     
│   └── entities.py     # 定义核心数据结构（如 Event, Segment, DeviceTrace 等）
│
├── simulate/           # 模拟与回放逻辑
│   ├── __init__.py     
│   └── simulate.py     # 主要类：SimulateDeviceSnapshot，负责事件回放与 hook 注册
│
├── util/               # 工具函数与辅助模块
│   ├── __init__.py     
│   └── logger.py       # 日志模块
│
├── dump.py             # 快照剪裁脚本
└── README.md           # 项目说明文档
```
