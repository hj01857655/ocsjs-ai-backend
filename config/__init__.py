# Backend configuration package
import os
import sys

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from .config import Config
except ImportError:
    try:
        # 尝试绝对导入
        import config as config_module
        Config = config_module.Config
    except ImportError:
        # 最后尝试直接导入文件
        import importlib.util
        config_file = os.path.join(current_dir, 'config.py')
        if os.path.exists(config_file):
            spec = importlib.util.spec_from_file_location("config", config_file)
            if spec and spec.loader:
                config_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(config_module)
                Config = config_module.Config
            else:
                raise ImportError("Cannot load config module")
        else:
            raise ImportError("config.py file not found")

__all__ = ['Config']
