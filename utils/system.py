"""
系统工具模块 v0.0.3

功能：
- 获取系统 CPU 核心数
- 查找可执行文件路径
- 查找 Conda 环境路径（统一入口）

v0.0.2 改进：
- find_exe 支持额外搜索路径
- 新增 find_conda_env_path 统一 Conda 环境路径查找
"""

import os
import multiprocessing
import logging

log = logging.getLogger(__name__)


def get_cpu_count():
    """
    获取系统 CPU 核心数

    返回:
        int: CPU 核心数

    用途：
        - 自动设置 AdapterRemoval 的 --threads 参数
        - 自动设置 CRISPResso2 的 -p 参数
    """
    try:
        return multiprocessing.cpu_count()
    except NotImplementedError:
        return 4  # 合理默认值


def find_exe(name, extra_paths=None):
    """
    在 PATH 和额外路径中查找可执行文件

    参数:
        name: 可执行文件名（不含扩展名）
        extra_paths: 额外搜索目录列表

    返回:
        str: 可执行文件完整路径，未找到返回 None

    示例:
        find_exe('CRISPResso')  # 返回 'C:\\...\\CRISPResso.exe'
        find_exe('adapterremoval3', extra_paths=['C:\\tools\\bin'])
    """
    search_dirs = []

    # 添加 Conda 环境 Scripts 目录
    env_path = find_conda_env_path()
    if env_path:
        search_dirs.append(os.path.join(env_path, 'Scripts'))

    # 添加额外路径
    if extra_paths:
        search_dirs.extend(extra_paths)

    # 添加系统 PATH
    search_dirs.extend(os.environ.get('PATH', '').split(os.pathsep))

    for p in search_dirs:
        if not p:
            continue
        for ext in ['.exe', '']:
            full = os.path.join(p, name + ext)
            if os.path.isfile(full):
                return full
    return None


def find_conda_env_path(env_name='crispranalysis'):
    """
    查找 Conda 环境路径

    统一的 Conda 环境路径查找入口，避免各模块重复硬编码

    参数:
        env_name: 环境名称

    返回:
        str: 环境路径，不存在返回 None
    """
    home = os.path.expanduser('~')
    candidates = [
        os.path.join(home, '.conda', 'envs', env_name),
        os.path.join(home, 'miniconda3', 'envs', env_name),
        os.path.join(home, 'anaconda3', 'envs', env_name),
        os.path.join('C:', os.sep, 'ProgramData', 'miniconda3', 'envs', env_name),
        os.path.join('C:', os.sep, 'ProgramData', 'anaconda3', 'envs', env_name),
    ]
    for p in candidates:
        if os.path.exists(os.path.join(p, 'python.exe')):
            return p
    return None