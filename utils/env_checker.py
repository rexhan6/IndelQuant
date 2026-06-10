"""
环境检测模块 v0.0.3

功能：
- 检测 Conda 安装状态
- 检测 crispranalysis 环境是否存在
- 检测 AdapterRemoval 和 CRISPResso2 是否安装
- 返回详细的检测结果

v0.0.2 改进：
- 使用 utils/system.py 的统一路径查找
- 增加更多 Conda 路径候选
- check_tool 增加超时和错误分类
- 更健壮的版本检测
"""

import subprocess
import os
import logging

from core.command_utils import command_to_string
from utils.system import find_conda_env_path

log = logging.getLogger(__name__)


def check_tool(exe_path, cmd=None, timeout=10):
    """
    检测工具是否可用

    参数:
        exe_path: 可执行文件路径
        cmd: 测试命令（默认使用 --version）
        timeout: 超时时间（秒）

    返回:
        tuple: (是否成功, 版本信息或错误信息)
    """
    if not os.path.exists(exe_path):
        return False, 'not installed'

    if cmd is None:
        cmd = f'"{exe_path}" --version'
    elif isinstance(cmd, (list, tuple)):
        cmd = command_to_string(cmd)

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=True)
        # 版本信息可能在 stdout 或 stderr
        ver = r.stdout.strip().split('\n')[0] if r.stdout.strip() else ''
        if not ver:
            ver = r.stderr.strip().split('\n')[0] if r.stderr.strip() else ''
        if not ver:
            ver = f'installed (exit code: {r.returncode})'
        return r.returncode == 0, ver
    except subprocess.TimeoutExpired:
        return False, 'timeout'
    except OSError as e:
        return False, f'error: {e}'


def check_all(env_name='crispranalysis'):
    """
    检测所有依赖

    参数:
        env_name: Conda 环境名称

    返回:
        dict: 检测结果，格式为 {工具名: {ok: bool, version: str}}

    示例:
        {
            'Conda': {'ok': True, 'version': 'C:\\miniconda3'},
            'Environment': {'ok': True, 'version': 'crispranalysis (...)'},
            'AdapterRemoval': {'ok': True, 'version': 'adapterremoval3 v3.0.0'},
            'CRISPResso': {'ok': True, 'version': 'CRISPResso 2.3.4'},
            'Python': {'ok': True, 'version': 'Python 3.10.20'}
        }
    """
    results = {}

    # 检测 Conda
    conda_base = _find_conda_base()
    results['Conda'] = {'ok': bool(conda_base), 'version': conda_base or 'not found'}

    # 检测环境
    env_path = find_conda_env_path(env_name)
    if env_path:
        results['Environment'] = {'ok': True, 'version': f'{env_name} ({env_path})'}

        scripts = os.path.join(env_path, 'Scripts')

        # 检测 AdapterRemoval
        ar = os.path.join(scripts, 'adapterremoval3.exe')
        ok, ver = check_tool(ar) if os.path.exists(ar) else (False, 'not installed')
        results['AdapterRemoval'] = {'ok': ok, 'version': ver}

        # 检测 CRISPResso
        cr = os.path.join(scripts, 'CRISPResso.exe')
        ok, ver = check_tool(cr) if os.path.exists(cr) else (False, 'not installed')
        results['CRISPResso'] = {'ok': ok, 'version': ver}

        # 检测 fastp（CRISPResso2 v2.3.0+ 必需）
        fp = os.path.join(scripts, 'fastp.exe')
        ok, ver = check_tool(fp) if os.path.exists(fp) else (False, 'not installed')
        results['fastp'] = {'ok': ok, 'version': ver}

        # 检测 Python
        py = os.path.join(env_path, 'python.exe')
        ok, ver = check_tool(py, [py, '--version']) if os.path.exists(py) else (False, 'not found')
        results['Python'] = {'ok': ok, 'version': ver}

        for package in ['customtkinter', 'matplotlib', 'numpy', 'pandas', 'openpyxl', 'windnd']:
            ok, ver = check_python_package(py, package)
            results[f'Python package: {package}'] = {'ok': ok, 'version': ver}

        ok, ver = check_python_package(py, 'CRISPResso2')
        results['Python package: CRISPResso2'] = {'ok': ok, 'version': ver}
    else:
        results['Environment'] = {'ok': False, 'version': f'{env_name} not found'}
        results['AdapterRemoval'] = {'ok': False, 'version': 'N/A'}
        results['CRISPResso'] = {'ok': False, 'version': 'N/A'}
        results['fastp'] = {'ok': False, 'version': 'N/A'}
        results['Python'] = {'ok': False, 'version': 'N/A'}
        for package in ['customtkinter', 'matplotlib', 'numpy', 'pandas', 'openpyxl', 'windnd', 'CRISPResso2']:
            results[f'Python package: {package}'] = {'ok': False, 'version': 'N/A'}

    return results


def check_python_package(python_exe, package, timeout=10):
    """检测指定 Python 包是否可导入，并尽量返回版本。"""
    if not os.path.exists(python_exe):
        return False, 'python not found'

    code = (
        "import importlib, sys; "
        f"m=importlib.import_module('{package}'); "
        "print(getattr(m, '__version__', 'installed'))"
    )
    cmd = command_to_string([python_exe, '-c', code])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=True)
        text = (r.stdout or r.stderr).strip().split('\n')[0] if (r.stdout or r.stderr).strip() else ''
        if r.returncode == 0:
            return True, text or 'installed'
        return False, text or 'not installed'
    except subprocess.TimeoutExpired:
        return False, 'timeout'
    except OSError as e:
        return False, f'error: {e}'


def _find_conda_base():
    """
    查找 Conda 安装根目录

    返回:
        str: Conda 根目录路径，不存在返回 None
    """
    home = os.path.expanduser('~')
    candidates = [
        os.path.join(home, 'miniconda3'),
        os.path.join(home, 'anaconda3'),
        r'C:\ProgramData\miniconda3',
        r'C:\ProgramData\anaconda3',
    ]
    for p in candidates:
        # 检查 conda 可执行文件
        for exe_name in ['_conda.exe', 'conda.exe', 'Scripts\\conda.exe']:
            if os.path.exists(os.path.join(p, exe_name)):
                return p
    return None
