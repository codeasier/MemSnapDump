"""
-------------------------------------------------------------------------
This file is part of the MindStudio project.
Copyright (c) 2026 Huawei Technologies Co.,Ltd.

MindStudio is licensed under Mulan PSL v2.
You can use this software according to the terms and conditions of the Mulan PSL v2.
You may obtain a copy of Mulan PSL v2 at:

         http://license.coscl.org.cn/MulanPSL2

THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
See the Mulan PSL v2 for more details.
-------------------------------------------------------------------------
"""
"""
日志工具模块单元测试
"""

import os
import tempfile
import logging
import unittest
from util.logger import get_logger, set_global_log_file


class TestLogger(unittest.TestCase):
    """日志工具模块单元测试类"""

    def setUp(self):
        """测试前的准备工作"""
        # 创建临时目录用于测试
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, "test.log")

        # 保存原始的全局变量状态
        from util.logger import _global_log_file, _global_file_handler
        self.original_global_log_file = _global_log_file
        self.original_global_file_handler = _global_file_handler

    def tearDown(self):
        """测试后的清理工作"""
        # 导入模块以修改全局变量
        import util.logger

        # 关闭文件处理器
        if util.logger._global_file_handler:
            util.logger._global_file_handler.close()

        # 恢复原始状态
        util.logger._global_log_file = self.original_global_log_file
        util.logger._global_file_handler = self.original_global_file_handler

        # 清理临时文件
        if os.path.exists(self.temp_dir):
            for file in os.listdir(self.temp_dir):
                os.remove(os.path.join(self.temp_dir, file))
            os.rmdir(self.temp_dir)

    def test_get_logger_basic(self):
        """测试 get_logger 函数的基本功能"""
        # 创建logger
        logger = get_logger("test_module")

        # 验证logger的名称
        self.assertEqual(logger.name, "test_module")

        # 验证logger的级别
        self.assertEqual(logger.level, logging.INFO)

        # 验证logger有一个handler（控制台handler）
        self.assertEqual(len(logger.handlers), 1)
        self.assertIsInstance(logger.handlers[0], logging.StreamHandler)

    def test_get_logger_with_custom_level(self):
        """测试 get_logger 函数的自定义级别功能"""
        # 创建debug级别的logger
        logger = get_logger("test_module", level=logging.DEBUG)

        # 验证logger的级别
        self.assertEqual(logger.level, logging.DEBUG)

        # 验证handler的级别
        self.assertEqual(logger.handlers[0].level, logging.DEBUG)

    def test_set_global_log_file(self):
        """测试 set_global_log_file 函数"""
        # 设置全局日志文件
        set_global_log_file(self.log_file)

        # 创建logger
        logger = get_logger("test_module")

        # 验证logger有两个handler（控制台handler和文件handler）
        self.assertEqual(len(logger.handlers), 2)

        # 验证第二个handler是文件handler
        file_handler = None
        for handler in logger.handlers:
            if isinstance(handler, logging.FileHandler):
                file_handler = handler
                break
        self.assertIsNotNone(file_handler)
        self.assertEqual(file_handler.baseFilename, os.path.abspath(self.log_file))

    def test_set_global_log_file_nonexistent_directory(self):
        """测试 set_global_log_file 函数在目录不存在时的情况"""
        # 测试不存在的目录
        nonexistent_dir = os.path.join(self.temp_dir, "nonexistent")
        log_file = os.path.join(nonexistent_dir, "test.log")

        # 验证会抛出OSError
        with self.assertRaises(OSError):
            set_global_log_file(log_file)

    def test_set_global_log_file_not_directory(self):
        """测试 set_global_log_file 函数在路径不是目录时的情况"""
        # 创建一个文件而不是目录
        not_dir = os.path.join(self.temp_dir, "not_dir.txt")
        with open(not_dir, "w") as f:
            f.write("")

        # 尝试在文件路径下创建日志文件
        log_file = os.path.join(not_dir, "test.log")

        # 验证会抛出OSError
        with self.assertRaises(OSError):
            set_global_log_file(log_file)

    def test_logger_output_to_file(self):
        """测试logger是否正确输出到文件"""
        # 设置全局日志文件
        set_global_log_file(self.log_file)

        # 创建logger
        logger = get_logger("test_module")

        # 记录一条日志
        test_message = "Test log message"
        logger.info(test_message)

        # 关闭文件处理器以确保日志被写入
        for handler in logger.handlers:
            if isinstance(handler, logging.FileHandler):
                handler.close()

        # 验证日志文件存在且包含测试消息
        self.assertTrue(os.path.exists(self.log_file))
        with open(self.log_file, "r", encoding="utf-8") as f:
            log_content = f.read()
        self.assertIn(test_message, log_content)

    def test_attach_file_handler_to_existing_loggers(self):
        """测试为已存在的logger添加文件处理器"""
        # 先创建一个logger
        existing_logger = get_logger("existing_module")

        # 设置全局日志文件
        set_global_log_file(self.log_file)

        # 验证existing_logger现在有两个handler
        self.assertEqual(len(existing_logger.handlers), 2)

        # 验证第二个handler是文件handler
        file_handler_count = 0
        for handler in existing_logger.handlers:
            if isinstance(handler, logging.FileHandler):
                file_handler_count += 1
        self.assertEqual(file_handler_count, 1)

    def test_multiple_loggers_share_file_handler(self):
        """测试多个logger共享同一个文件处理器"""
        # 设置全局日志文件
        set_global_log_file(self.log_file)

        # 创建两个logger
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        # 验证两个logger都有文件处理器
        for logger in [logger1, logger2]:
            file_handler_count = 0
            for handler in logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    file_handler_count += 1
            self.assertEqual(file_handler_count, 1)

        # 记录日志
        message1 = "Message from module1"
        message2 = "Message from module2"
        logger1.info(message1)
        logger2.info(message2)

        # 关闭文件处理器
        for handler in logger1.handlers:
            if isinstance(handler, logging.FileHandler):
                handler.close()

        # 验证日志文件包含两条消息
        with open(self.log_file, "r", encoding="utf-8") as f:
            log_content = f.read()
        self.assertIn(message1, log_content)
        self.assertIn(message2, log_content)
