import os
import sys

# 动态添加项目根目录到 Python 搜索路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from tools.adaptors.snapshot2db import main

if __name__ == '__main__':
    main()
