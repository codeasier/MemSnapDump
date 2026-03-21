# UT 模块 Agent 指南

## 模块概述

`ut/` 目录包含 MemSnapDump 项目的所有单元测试代码和测试数据。采用分层模块化结构，每个子模块可独立运行测试。

## 目录结构

```
ut/
├── __init__.py           # 包标识
├── common.py             # 测试公共工具函数
├── test.py               # 全量测试入口
├── test-data/            # 测试数据文件
│   ├── snapshot_*.pkl    # 内存快照测试数据
│   └── ...
├── base/                 # base 模块测试
│   ├── test.py           # 模块测试入口
│   └── test_entities.py  # 实体类测试
├── simulate/             # simulate 模块测试
│   ├── test.py           # 模块测试入口
│   └── test_simulate.py  # 回放模拟测试
├── tools/                # tools 模块测试
│   ├── test.py           # 模块测试入口
│   ├── test_slice_dump.py      # 切片功能测试
│   ├── test_snapshot2db.py     # 数据库导出测试
│   └── snapshot_db_helper.py   # 数据库查询辅助类
└── util/                 # util 模块测试
    ├── test.py           # 模块测试入口
    └── test_logger.py    # 日志工具测试
```

## 运行测试

### 全量测试
```bash
python ut/test.py
```

### 模块级测试
```bash
python ut/base/test.py
python ut/simulate/test.py
python ut/tools/test.py
python ut/util/test.py
```

### 子模块级测试
```bash
python ut/base/test_entities.py
python ut/simulate/test_simulate.py
python ut/tools/test_slice_dump.py
python ut/tools/test_snapshot2db.py
python ut/util/test_logger.py
```

## 测试约定

### 命名规范
- 测试文件: `test_*.py`
- 测试类: `Test*` 继承 `unittest.TestCase`
- 测试方法: `test_*`

### 独立运行支持
每个测试文件末尾包含:
```python
if __name__ == "__main__":
    import unittest
    unittest.main(verbosity=2, module="test_xxx")
```

### 日志抑制
测试期间自动抑制 INFO 级别日志，仅显示 WARNING 及以上级别:
```python
from ut.simulate.test_simulate import suppress_logs, restore_logs

class TestXxx(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        suppress_logs()

    @classmethod
    def tearDownClass(cls):
        restore_logs()
```

## 公共工具

### common.py
提供测试辅助函数:

- `valid_segment(segment, test_util)`: 校验单个 segment 数据一致性
- `valid_segments(segments, test_util)`: 校验 segment 列表数据一致性

### snapshot_db_helper.py
提供数据库查询辅助类 `SnapshotDbHandler`，用于验证 snapshot2db 导出结果。

## 测试数据

`test-data/` 目录包含各类内存快照测试文件:

| 文件 | 说明 |
|------|------|
| `snapshot_1768383987920985470.pkl` | 标准内存快照 |
| `snapshot_expandable.pkl` | 包含可扩展段的快照 |
| `snapshot_with_empty_cache.pkl` | 空缓存快照 |
| `snapshot_with_empty_cache_expandable.pkl` | 空缓存可扩展段快照 |
| `snapshot_with_multi_devices.pkl` | 多设备快照 |

## sys.path 处理

由于 `ut/` 目录下有与根目录同名的子模块目录，测试文件需正确设置 `sys.path`:

```python
import sys
from pathlib import Path

project_dir = Path(__file__).parent.parent.parent.resolve()
if project_dir not in sys.path:
    sys.path.append(str(project_dir))
```

全量入口 `ut/test.py` 需确保项目根目录优先于 ut 目录:
```python
ut_dir = Path(__file__).parent.resolve()
project_dir = Path(__file__).parent.parent.resolve()
if project_dir not in sys.path:
    idx = sys.path.index(str(ut_dir)) if str(ut_dir) in sys.path else -1
    sys.path.insert(idx, str(project_dir))
```
