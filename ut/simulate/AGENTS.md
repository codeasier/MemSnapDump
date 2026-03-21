# Simulate 模块测试 Agent 指南

## 模块概述

测试 `simulate/` 模块中的快照回放模拟引擎，验证回放机制的正确性和钩子系统的工作状态。

## 文件说明

| 文件 | 说明 |
|------|------|
| `test.py` | 模块测试入口 |
| `test_simulate.py` | 回放模拟单元测试及公共钩子类 |

## 测试覆盖

### test_simulate.py

| 测试类 | 测试内容 |
|--------|----------|
| `TestSimulate` | 快照回放核心功能测试 |

#### 测试方法

| 方法 | 说明 |
|------|------|
| `testBlockHookerInSnapshot` | 标准快照的 Block 级别钩子测试 |
| `testBlockHookerInVmemSnapshot` | 虚拟内存快照的 Block 级别钩子测试 |
| `testBlockHookerInSnapshotWithEmptyCache` | 空缓存快照的 Block 级别钩子测试 |
| `testBlockHookerInVmemSnapshotWithEmptyCache` | 空缓存虚拟内存快照的 Block 级别钩子测试 |
| `testReplaySnapshot` | 标准快照的事件级回放测试 |
| `testReplayVmemSnapshot` | 虚拟内存快照的事件级回放测试 |
| `testReplaySnapshotWithEmptyCache` | 空缓存快照的事件级回放测试 |
| `testReplayVmemSnapshotWithEmptyCache` | 空缓存虚拟内存快照的事件级回放测试 |

### 公共组件

#### TestReplayEventHooker
事件级回放验证钩子，每隔一定事件数校验 segment 数据一致性。

#### TestReplayBlockHooker
Block 级别回放验证钩子，校验分配/释放前后的大小变化。

#### suppress_logs() / restore_logs()
日志抑制工具函数，供其他测试模块复用。

## 运行测试

```bash
# 模块级
python ut/simulate/test.py

# 子模块级
python ut/simulate/test_simulate.py
```

## 测试数据

使用 `ut/test-data/` 下的快照文件:

| 文件 | 用途 |
|------|------|
| `snapshot_1768383987920985470.pkl` | 标准快照测试 |
| `snapshot_expandable.pkl` | 虚拟内存快照测试 |
| `snapshot_with_empty_cache.pkl` | 空缓存快照测试 |
| `snapshot_with_empty_cache_expandable.pkl` | 空缓存虚拟内存快照测试 |

## 依赖关系

```
test_simulate.py
    ├── base (TraceEntry, DeviceSnapshot, Segment, Block, BlockState)
    ├── simulate (SimulateDeviceSnapshot, SimulateHooker)
    ├── simulate.hooker_defs (AllocatorHooker)
    ├── util.file_util (load_pickle_to_dict)
    └── ut.common (valid_segments)
```

## 扩展测试

添加新的快照测试时:

1. 将测试数据放入 `ut/test-data/`
2. 在 `TestSimulate.setUp()` 中添加路径
3. 创建对应的测试方法
4. 选择合适的钩子类进行验证
