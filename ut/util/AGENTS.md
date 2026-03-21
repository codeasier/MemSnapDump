# Util 模块测试 Agent 指南

## 模块概述

测试 `util/` 模块中的通用工具函数，包括日志系统、文件操作等辅助功能。

## 文件说明

| 文件 | 说明 |
|------|------|
| `test.py` | 模块测试入口 |
| `test_logger.py` | 日志工具单元测试 |

## 测试覆盖

### test_logger.py

| 测试类 | 测试内容 |
|--------|----------|
| `TestLogger` | 日志工具模块单元测试 |

| 方法 | 说明 |
|------|------|
| `test_get_logger_basic` | get_logger 基本功能测试 |
| `test_get_logger_with_custom_level` | 自定义日志级别测试 |
| `test_set_global_log_file` | 全局日志文件设置测试 |
| `test_set_global_log_file_nonexistent_directory` | 不存在目录的异常测试 |
| `test_set_global_log_file_not_directory` | 非目录路径的异常测试 |
| `test_logger_output_to_file` | 日志文件输出测试 |
| `test_attach_file_handler_to_existing_loggers` | 已存在 logger 添加文件处理器测试 |
| `test_multiple_loggers_share_file_handler` | 多 logger 共享文件处理器测试 |

### 关键验证点

1. **Logger 创建**: 验证 logger 名称、级别、handler 配置
2. **文件输出**: 验证日志正确写入文件
3. **全局配置**: 验证 `set_global_log_file` 对已存在 logger 的影响
4. **异常处理**: 验证无效路径的正确错误抛出
5. **多 logger 共享**: 验证多个 logger 共享同一文件处理器

## 运行测试

```bash
# 模块级
python ut/util/test.py

# 子模块级
python ut/util/test_logger.py
```

## 测试特点

### 临时文件管理

测试使用 `tempfile.mkdtemp()` 创建临时目录，测试结束后自动清理:

```python
def setUp(self):
    self.temp_dir = tempfile.mkdtemp()
    self.log_file = os.path.join(self.temp_dir, "test.log")

def tearDown(self):
    # 清理临时文件
    if os.path.exists(self.temp_dir):
        for file in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, file))
        os.rmdir(self.temp_dir)
```

### 全局状态管理

测试需要保存和恢复 logger 模块的全局状态:

```python
def setUp(self):
    from util.logger import _global_log_file, _global_file_handler
    self.original_global_log_file = _global_log_file
    self.original_global_file_handler = _global_file_handler

def tearDown(self):
    import util.logger
    util.logger._global_log_file = self.original_global_log_file
    util.logger._global_file_handler = self.original_global_file_handler
```

### 日志输出

由于测试日志功能本身，此测试文件**不抑制日志输出**，日志消息会显示在测试输出中。

## 依赖关系

```
test_logger.py
    └── util.logger (get_logger, set_global_log_file)
```

无外部测试数据依赖。

## 扩展测试

添加新的 util 模块测试时:

1. 创建 `test_xxx.py` 文件
2. 继承 `unittest.TestCase`
3. 在 `setUp`/`tearDown` 中管理测试状态
4. 添加到模块入口 `test.py` 的 discover 范围（自动）
