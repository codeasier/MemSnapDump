import pickle
from pathlib import Path
from typing import Dict, Any


def load_pickle_to_dict(pickle_file: Path) -> dict:
    """
    从指定路径加载 pickle 文件，并确保其内容为 dict 类型。

    Args:
        pickle_file (Path): pickle 文件路径

    Returns:
        dict: 加载的字典数据

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 文件内容不是 dict 类型
        pickle.UnpicklingError: 反序列化失败（如文件损坏或非 pickle 格式）
    """
    if not pickle_file.is_file():
        raise FileNotFoundError(f"文件不存在: {pickle_file}")

    try:
        with open(pickle_file, "rb") as f:
            data = pickle.load(f)
    except pickle.UnpicklingError as e:
        raise ValueError(f"文件不是有效的 pickle 格式: {pickle_file}") from e

    if not isinstance(data, dict):
        raise ValueError(f"pickle 文件内容不是 dict 类型，实际类型: {type(data).__name__}")

    return data


def save_dict_to_pickle(data: Dict[Any, Any], path: Path, protocol: int = 4) -> None:
    """
    将字典保存为 pickle 文件。

    Args:
        data (dict): 要保存的字典
        path (Path): 保存路径（会自动创建父目录）
        protocol (int): 保存版本

    Raises:
        TypeError: data 不是 dict 类型
        OSError: 文件写入失败（如权限不足、磁盘满等）
    """
    if not isinstance(data, dict):
        raise TypeError(f"仅支持 dict 类型，传入了: {type(data).__name__}")
    path.parent.mkdir(parents=True, exist_ok=True)  # 自动创建父目录

    try:
        with open(path, "wb") as f:
            pickle.dump(data, f, protocol=protocol)
    except OSError as e:
        raise OSError(f"无法写入文件 {path}: {e}") from e
