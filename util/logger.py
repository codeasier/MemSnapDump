import logging


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
        创建并返回一个logger实例
    :param name: logger名称
    :param level: 日志级别，默认info
    :return: 配置好的Logger对象
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
