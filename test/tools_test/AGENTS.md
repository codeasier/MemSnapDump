# test/tools_test 模块 Agent 指南

## 模块职责

`tools_test` 子模块包含工具功能的单元测试，验证切片和数据库转换的正确性。

## 文件说明

### slice_dump_test.py
快照切片功能测试。

**测试场景**:
- 固定切片数切分
- 固定最大事件数切分
- pkl 格式输出
- json 格式输出
- 切片数据完整性验证

### snapshot2db_test.py
快照转数据库功能测试。

**测试场景**:
- 数据库文件创建
- trace_entry 表数据正确性
- block 表数据正确性
- 值映射字典表

### snapshot_db_analyze.py
数据库分析工具，用于手动验证和分析生成的数据库。

## 运行测试

```bash
# 运行切片测试
python -m pytest test/tools_test/slice_dump_test.py -v

# 运行数据库测试
python -m pytest test/tools_test/snapshot2db_test.py -v

# 运行所有工具测试
python -m pytest test/tools_test/ -v
```

## 测试验证点

### 切片测试验证
1. 输出文件数量正确
2. 每个切片的事件数量符合预期
3. 切片文件可正常加载
4. 切片数据完整性（segments + events）

### 数据库测试验证
1. 数据库文件创建成功
2. 表结构正确
3. 事件记录数量正确
4. 块记录数量正确
5. 值映射正确存储

## 注意事项

1. 使用 `test-data/` 目录下的测试数据
2. 测试输出写入临时目录，测试后清理
3. 验证边界情况（空快照、单事件等）
