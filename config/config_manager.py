"""
配置管理模块 v0.0.3

功能：
- 加载/保存 JSON 配置文件
- 管理用户输入历史
- 提供默认配置模板

v0.0.2 改进：
- 配置加载添加异常保护（JSON 损坏时使用默认配置）
- 保存配置时添加原子写入（避免写入中断导致文件损坏）
- DEFAULT_CONFIG 增加更多字段
- 历史记录支持更多类型
"""

import json
import os
import logging

log = logging.getLogger(__name__)

# 默认配置模板
DEFAULT_CONFIG = {
    "adapter_removal": {
        "file1": "",
        "file2": "",
        "barcode_file": "",
        "basename": "demux",
        "threads": "",
        "extra_args": ""
    },
    "crispresso": {
        "amplicon_seq": "",
        "amplicon_name": "Reference",
        "guide_seq": "",
        "guide_name": "sgRNA",
        "editing_tool": "Cas9",
        "output_dir": "./results",
        "qw_center": "-3",
        "qw_size": "1",
        "n_processes": "",
        "extra_args": "",
        "fastp_enabled": False
    },
    "workdir": "",
    "conda_path": "",
    "env_name": "crispranalysis",
    "history": {
        "amplicon_seq": [],
        "guide_seq": [],
        "r1": [],
        "r2": [],
        "barcode_file": [],
        "output_dir": []
    }
}


def load_config(path):
    """
    加载配置文件

    参数:
        path: 配置文件路径

    返回:
        配置字典（如果文件不存在或损坏则返回默认配置）
    """
    if not os.path.exists(path):
        log.info('配置文件不存在，使用默认配置: %s', path)
        return _deep_copy_config(DEFAULT_CONFIG)

    try:
        with open(path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        log.warning('配置文件损坏 (%s)，使用默认配置: %s', e, path)
        return _deep_copy_config(DEFAULT_CONFIG)
    except OSError as e:
        log.warning('无法读取配置文件 (%s)，使用默认配置: %s', e, path)
        return _deep_copy_config(DEFAULT_CONFIG)

    # 确保所有默认字段都存在（递归合并）
    cfg = _merge_defaults(cfg, DEFAULT_CONFIG)

    return cfg


def save_config(path, config):
    """
    保存配置文件（原子写入）

    参数:
        path: 配置文件路径
        config: 配置字典
    """
    try:
        # 原子写入：先写临时文件，再重命名
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        tmp_path = path + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        # 替换原文件
        if os.path.exists(path):
            os.replace(tmp_path, path)
        else:
            os.rename(tmp_path, path)
    except OSError as e:
        log.error('保存配置失败: %s', e)


def add_to_history(config, key, value, max_items=10):
    """
    添加值到历史记录

    参数:
        config: 配置字典
        key: 历史记录键名
        value: 要添加的值
        max_items: 最大历史记录数
    """
    if not value:
        return

    # 确保 history 结构存在
    if 'history' not in config:
        config['history'] = DEFAULT_CONFIG['history'].copy()
    if key not in config['history']:
        config['history'][key] = []

    history = config['history'][key]

    # 如果已存在则移到最前面
    if value in history:
        history.remove(value)
    history.insert(0, value)

    # 限制历史记录数量
    config['history'][key] = history[:max_items]


def _deep_copy_config(cfg):
    """深拷贝配置字典"""
    result = {}
    for k, v in cfg.items():
        if isinstance(v, dict):
            result[k] = _deep_copy_config(v)
        elif isinstance(v, list):
            result[k] = list(v)
        else:
            result[k] = v
    return result


def _merge_defaults(cfg, defaults):
    """递归合并默认值，确保 cfg 包含所有默认字段"""
    result = _deep_copy_config(cfg)
    for k, v in defaults.items():
        if k not in result:
            result[k] = _deep_copy_config(v) if isinstance(v, dict) else (list(v) if isinstance(v, list) else v)
        elif isinstance(v, dict) and isinstance(result[k], dict):
            result[k] = _merge_defaults(result[k], v)
    return result
