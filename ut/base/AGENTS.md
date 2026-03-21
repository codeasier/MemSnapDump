# Base 模块测试 Agent 指南

## 模块概述

测试 `base/` 模块中的基础数据模型，包括 Frame、TraceEntry、Block、Segment、DeviceSnapshot 等核心实体类。

## 文件说明

| 文件 | 说明 |
|------|------|
| `test.py` | 模块测试入口，发现并运行所有 `test_*.py` |
| `test_entities.py` | 实体类单元测试 |

## 测试覆盖

### test_entities.py

| 测试类 | 测试内容 |
|--------|----------|
| `TestFrame` | Frame 数据模型的序列化/反序列化 |
| `TestTraceEntry` | TraceEntry 事件条目的解析与调用栈获取 |
| `TestBlock` | Block 内存块的状态管理与子块校验 |
| `TestSegment` | Segment 内存段的构建与块索引查找 |
| `TestDeviceSnapshot` | DeviceSnapshot 设备快照的整体解析 |

### 关键测试点

1. **from_dict / to_dict**: 验证数据模型的序列化/反序列化一致性
2. **build_from_event**: 验证从事件构建 Block/Segment 的正确性
3. **地址查找**: 验证 `find_block_idx_by_block_addr`、`find_segment_idx_by_addr` 的边界条件
4. **状态校验**: 验证 `valid_sub_block` 的地址范围判断

## 运行测试

```bash
# 模块级
python ut/base/test.py

# 子模块级
python ut/base/test_entities.py
```

## 依赖关系

```
test_entities.py
    └── base.entities (Frame, TraceEntry, Block, Segment, DeviceSnapshot)
```

无外部测试数据依赖，所有测试数据在测试方法内构造。
