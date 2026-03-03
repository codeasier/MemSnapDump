"""
日志工具模块

提供日志记录器的创建和配置功能。
"""

import logging


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    创建并返回一个配置好的 Logger 实例。

    该函数会创建一个带有控制台输出的日志记录器，使用统一的格式化样式。
    如果 logger 已存在 handlers，会先清除再添加新的 handler。

    Args:
        name: logger 名称，通常使用 __name__ 或模块名
        level: 日志级别，默认为 logging.INFO

    Returns:
        logging.Logger: 配置好的 Logger 对象

    Examples:
        >>> logger = get_logger(__name__)
        >>> logger.info("This is an info message")
        2024-01-01 12:00:00 [ INFO ][ __main__ ]: This is an info message

        >>> logger = get_logger("my_module", level=logging.DEBUG)
        >>> logger.debug("Debug message")
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加handler
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        fmt='{asctime} [{levelname:^6}][ {name:^12} ]: {message}',
        datefmt='%Y-%m-%d %H:%M:%S',
        style='{'
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger