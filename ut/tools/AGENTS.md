# Tools 模块测试 Agent 指南

## 模块概述

测试 `tools/` 模块中的功能工具，包括快照切片、快照转数据库等功能。

## 文件说明

| 文件 | 说明 |
|------|------|
| `test.py` | 模块测试入口 |
| `test_slice_dump.py` | 快照切片功能测试 |
| `test_snapshot2db.py` | 快照转数据库功能测试 |
| `snapshot_db_helper.py` | 数据库查询辅助类（非测试文件） |

## 测试覆盖

### test_slice_dump.py

| 测试类 | 测试内容 |
|--------|----------|
| `SliceDumpTest` | 快照切片功能测试 |

| 方法 | 说明 |
|------|------|
| `testSplitSnapshotWithDefaultArgs` | 标准快照切片测试 |
| `testSplitExpandableSnapshot` | 可扩展段快照切片测试 |

**验证点**:
- 切片文件数量符合预期
- 每个切片文件可独立回放

### test_snapshot2db.py

| 测试类 | 测试内容 |
|--------|----------|
| `Snapshot2DbTest` | 快照转数据库功能测试 |

| 方法 | 说明 |
|------|------|
| `testSnapshot2Db` | 标准快照转数据库测试 |
| `testVemSnapshot2Db` | 虚拟内存快照转数据库测试 |
| `testEmptyDeviceSnapshot` | 空设备快照测试（预期失败） |
| `testDumpAllMultipleDeviceSnapshot` | 多设备快照转数据库测试 |

**验证点**:
- 数据库文件正确生成
- 数据库内容与快照回放状态一致

### snapshot_db_helper.py

`SnapshotDbHandler` 类提供数据库查询能力，用于测试验证:

- `get_segments_by_event_id(event_id)`: 获取指定事件时刻的 segment 状态
- `query_blocks_by_event_id(event_id)`: 查询指定事件时刻的活跃 block
- `query_segment_events_until(event_id)`: 查询到指定事件的 segment 相关事件

## 运行测试

```bash
# 模块级
python ut/tools/test.py

# 子模块级
python ut/tools/test_slice_dump.py
python ut/tools/test_snapshot2db.py
```

## 测试数据

| 文件 | 用途 |
|------|------|
| `snapshot_with_empty_cache.pkl` | 切片测试、数据库测试 |
| `snapshot_with_empty_cache_expandable.pkl` | 可扩展段切片测试、虚拟内存数据库测试 |
| `snapshot_with_multi_devices.pkl` | 多设备数据库测试 |

## 临时文件

测试过程会生成临时目录，测试结束后自动清理:

- `test-data/slices/`: 切片输出目录
- `test-data/tmp/`: 数据库输出目录

## 依赖关系

```
test_slice_dump.py
    ├── simulate (SimulateDeviceSnapshot)
    ├── tools.slice_dump.hooker (SliceDumpHooker)
    ├── util.file_util (load_pickle_to_dict)
    └── ut.simulate.test_simulate (TestReplayEventHooker, suppress_logs, restore_logs)

test_snapshot2db.py
    ├── base (TraceEntry, DeviceSnapshot, BlockState)
    ├── simulate (SimulateDeviceSnapshot, SimulateHooker)
    ├── tools.adaptors.snapshot2db (dump)
    ├── util.file_util (load_pickle_to_dict)
    ├── ut.simulate.test_simulate (suppress_logs, restore_logs)
    └── ut.tools.snapshot_db_helper (SnapshotDbHandler)
```

## 注意事项

1. 数据库测试较耗时，涉及完整快照回放
2. 多设备测试会生成多个设备的数据库表
3. 切片测试会生成多个 pkl 文件，注意磁盘空间
