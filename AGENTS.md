# MemSnapDump 项目 Agent 指南

## 项目概述

MemSnapDump 是一个用于分析、处理 PyTorch/PyTorch-NPU 内存快照（snapshot）文件的工具集。项目提供快照回放、快照切片、快照转数据库等核心功能，帮助开发者进行显存问题分析。

## 核心架构

```
MemSnapDump/
├── base/               # 基础数据模型（Frame, TraceEntry, Block, Segment, DeviceSnapshot）
├── simulate/           # 快照回放模拟引擎（SimulateDeviceSnapshot, SimulatedCachingAllocator）
├── tools/              # 功能工具模块（切片、转数据库）
├── util/               # 通用工具（日志、计时器、文件操作、SQLite封装）
└── test/               # 测试代码与测试数据
```

## 数据流

1. **输入**: PyTorch/PyTorch-NPU 采集的内存快照 pickle 文件
2. **解析**: `DeviceSnapshot.from_dict()` 解析为内存段(segments)和事件序列(device_traces)
3. **回放**: `SimulateDeviceSnapshot.replay()` 倒序回放事件，支持注册钩子
4. **输出**: 切片文件(pkl/json) 或 SQLite 数据库

## 关键概念

### 内存快照数据结构
- **segments**: dump 时刻的内存池静态状态
- **device_traces**: 历史内存事件序列（动态）

### 事件类型
- `alloc`: 内存分配
- `free_requested`/`free_completed`: 内存释放请求/完成
- `segment_alloc`/`segment_free`: 内存段申请/释放
- `segment_map`/`segment_unmap`: 虚拟内存映射/取消映射

### 回放机制
回放采用**倒序撤销**方式：从最后一个事件开始，逐步回滚到初始状态。这使得可以在任意时刻获取当时的内存状态。

## 开发约定

### 代码风格
- 使用 Python dataclass 定义数据结构
- 钩子类继承 `SimulateHooker` 或 `AllocatorHooker` 抽象基类
- 日志使用 `util.get_logger()` 获取

### 扩展新功能
1. 在 `simulate/hooker_defs.py` 定义钩子接口（如需）
2. 实现具体的钩子类，继承相应基类
3. 在 `tools/` 下创建命令行入口

## 常用命令

```bash
# 快照切片
python tools.split /path/to/snapshot.pkl --slices 4

# 快照转数据库
python tools.dump2db /path/to/snapshot.pkl -o /output/dir
```

## 依赖

- Python 3.10+
- pandas（用于解析 pickle 文件）
- 标准库: pickle, sqlite3, json, argparse

## 日志系统

项目使用统一的日志系统，支持全局日志文件输出：

```python
from util import get_logger, set_global_log_file

# 设置全局日志文件（可选，所有 logger 都会输出到该文件）
set_global_log_file('/path/to/app.log')

logger = get_logger(__name__)
logger.info("Processing started")
```
