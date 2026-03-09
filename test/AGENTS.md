# test 模块 Agent 指南

## 模块职责

`test` 模块包含项目的单元测试和测试数据，验证快照回放、切片和数据库转换等功能的正确性。

## 目录结构

```
test/
├── __init__.py
├── common.py           # 测试公共方法
├── simulate_test.py    # 快照回放测试
├── tools_test/         # 工具模块测试
│   ├── slice_dump_test.py      # 切片功能测试
│   ├── snapshot2db_test.py     # 数据库转换测试
│   └── snapshot_db_analyze.py  # 数据库分析工具
└── test-data/          # 测试数据文件
    ├── snapshot_1768383987920985470.pkl
    ├── snapshot_expandable.pkl
    ├── snapshot_with_empty_cache.pkl
    └── snapshot_with_empty_cache_expandable.pkl
```

## 测试数据说明

### snapshot_*.pkl 文件
不同场景的内存快照测试数据:

| 文件 | 说明 |
|-----|------|
| `snapshot_1768383987920985470.pkl` | 标准快照数据 |
| `snapshot_expandable.pkl` | 包含可扩展内存段（虚拟内存）|
| `snapshot_with_empty_cache.pkl` | 包含空缓存的快照 |
| `snapshot_with_empty_cache_expandable.pkl` | 空缓存 + 可扩展内存段 |

## 测试文件说明

### simulate_test.py
快照回放功能测试。

**测试内容**:
- 快照加载与解析
- 事件回放完整性
- 内存状态一致性
- 钩子注册与回调

### tools_test/slice_dump_test.py
切片功能测试。

**测试内容**:
- 固定切片数切分
- 固定最大事件数切分
- 输出文件格式（pkl/json）
- 切片数据完整性

### tools_test/snapshot2db_test.py
数据库转换测试。

**测试内容**:
- 数据库创建
- 事件记录写入
- 块记录写入
- 值映射正确性

### tools_test/snapshot_db_analyze.py
数据库分析工具，用于验证和分析生成的数据库。

## 运行测试

### 运行单个测试
```bash
python -m pytest test/simulate_test.py -v
python -m pytest test/tools_test/slice_dump_test.py -v
```

### 运行所有测试
```bash
python -m pytest test/ -v
```

### 使用 unittest
```bash
python -m unittest discover -s test -v
```

## 编写测试

### 测试模板
```python
import unittest
from pathlib import Path
from simulate import SimulateDeviceSnapshot
from util.file_util import load_pickle_to_dict

class MyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_data_dir = Path(__file__).parent / 'test-data'
        cls.snapshot_file = cls.test_data_dir / 'snapshot_expandable.pkl'
    
    def test_something(self):
        data = load_pickle_to_dict(self.snapshot_file)
        snapshot = SimulateDeviceSnapshot(data, 0)
        self.assertTrue(snapshot.replay())
```

### 使用 common.py
```python
from test.common import load_test_snapshot

def test_with_common():
    snapshot = load_test_snapshot('snapshot_expandable.pkl')
    # ...
```

## 注意事项

1. **测试数据路径**: 使用 `Path(__file__).parent` 获取相对路径
2. **数据隔离**: 每个测试应使用独立的输出目录
3. **清理资源**: 测试后删除生成的临时文件
4. **边界条件**: 测试空快照、单事件快照等边界情况
