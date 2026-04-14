import os
import tempfile
import logging
import unittest
from memsnapdump.util.logger import get_logger, set_global_log_file


class TestLogger(unittest.TestCase):
    """日志工具模块单元测试类"""

    def setUp(self):
        """测试前的准备工作"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, "test.log")

        from memsnapdump.util.logger import _global_log_file, _global_file_handler
        self.original_global_log_file = _global_log_file
        self.original_global_file_handler = _global_file_handler

    def tearDown(self):
        """测试后的清理工作"""
        import memsnapdump.util.logger as logger_module

        if logger_module._global_file_handler:
            logger_module._global_file_handler.close()

        logger_module._global_log_file = self.original_global_log_file
        logger_module._global_file_handler = self.original_global_file_handler

        if os.path.exists(self.temp_dir):
            for file in os.listdir(self.temp_dir):
                os.remove(os.path.join(self.temp_dir, file))
            os.rmdir(self.temp_dir)

    def test_get_logger_basic(self):
        """测试 get_logger 函数的基本功能"""
        logger = get_logger("test_module")

        self.assertEqual(logger.name, "test_module")

        self.assertEqual(logger.level, logging.INFO)

        self.assertEqual(len(logger.handlers), 1)
        self.assertIsInstance(logger.handlers[0], logging.StreamHandler)

    def test_get_logger_with_custom_level(self):
        """测试 get_logger 函数的自定义级别功能"""
        logger = get_logger("test_module", level=logging.DEBUG)

        self.assertEqual(logger.level, logging.DEBUG)

        self.assertEqual(logger.handlers[0].level, logging.DEBUG)

    def test_set_global_log_file(self):
        """测试 set_global_log_file 函数"""
        set_global_log_file(self.log_file)

        logger = get_logger("test_module")

        self.assertEqual(len(logger.handlers), 2)

        file_handler = None
        for handler in logger.handlers:
            if isinstance(handler, logging.FileHandler):
                file_handler = handler
                break
        self.assertIsNotNone(file_handler)
        self.assertEqual(file_handler.baseFilename, os.path.abspath(self.log_file))

    def test_set_global_log_file_nonexistent_directory(self):
        """测试 set_global_log_file 函数在目录不存在时的情况"""
        nonexistent_dir = os.path.join(self.temp_dir, "nonexistent")
        log_file = os.path.join(nonexistent_dir, "test.log")

        with self.assertRaises(OSError):
            set_global_log_file(log_file)

    def test_set_global_log_file_not_directory(self):
        """测试 set_global_log_file 函数在路径不是目录时的情况"""
        not_dir = os.path.join(self.temp_dir, "not_dir.txt")
        with open(not_dir, "w") as f:
            f.write("")

        log_file = os.path.join(not_dir, "test.log")

        with self.assertRaises(OSError):
            set_global_log_file(log_file)

    def test_logger_output_to_file(self):
        """测试logger是否正确输出到文件"""
        set_global_log_file(self.log_file)

        logger = get_logger("test_module")

        test_message = "Test log message"
        logger.info(test_message)

        for handler in logger.handlers:
            if isinstance(handler, logging.FileHandler):
                handler.close()

        self.assertTrue(os.path.exists(self.log_file))
        with open(self.log_file, "r", encoding="utf-8") as f:
            log_content = f.read()
        self.assertIn(test_message, log_content)

    def test_attach_file_handler_to_existing_loggers(self):
        """测试为已存在的logger添加文件处理器"""
        existing_logger = get_logger("existing_module")

        set_global_log_file(self.log_file)

        self.assertEqual(len(existing_logger.handlers), 2)

        file_handler_count = 0
        for handler in existing_logger.handlers:
            if isinstance(handler, logging.FileHandler):
                file_handler_count += 1
        self.assertEqual(file_handler_count, 1)

    def test_multiple_loggers_share_file_handler(self):
        """测试多个logger共享同一个文件处理器"""
        set_global_log_file(self.log_file)

        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        for logger in [logger1, logger2]:
            file_handler_count = 0
            for handler in logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    file_handler_count += 1
            self.assertEqual(file_handler_count, 1)

        message1 = "Message from module1"
        message2 = "Message from module2"
        logger1.info(message1)
        logger2.info(message2)

        for handler in logger1.handlers:
            if isinstance(handler, logging.FileHandler):
                handler.close()

        with open(self.log_file, "r", encoding="utf-8") as f:
            log_content = f.read()
        self.assertIn(message1, log_content)
        self.assertIn(message2, log_content)


if __name__ == "__main__":
    import unittest
    unittest.main(verbosity=2, module="test_logger")
