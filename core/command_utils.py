"""
命令行构建工具 v0.1

集中处理 Windows 路径、额外参数解析和日志脱敏。外部生信工具仍然通过
shell=True 运行，以兼容部分工具对含空格路径的内部解析问题。
"""

import shlex
import subprocess


def quote(value):
    """按 Windows 命令行规则安全引用一个参数。"""
    return subprocess.list2cmdline([str(value)])


def split_extra_args(extra_args):
    """解析用户手写的额外参数，保留带引号的路径或标题。"""
    if not extra_args or not extra_args.strip():
        return []
    return shlex.split(extra_args, posix=False)


def command_to_string(parts):
    """把命令参数列表转换为适合 shell=True 的字符串。"""
    return ' '.join(quote(p) for p in parts if p not in (None, ''))


def append_option(parts, flag, value):
    """仅当 value 非空时追加 flag/value 参数。"""
    if value not in (None, ''):
        parts.extend([flag, str(value)])


def append_flag(parts, flag, enabled):
    """仅当 enabled 为真时追加布尔 flag。"""
    if enabled:
        parts.append(flag)
