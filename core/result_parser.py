"""
结果解析模块 v0.0.2

功能：
- 解析 CRISPResso2 输出的 quantification 文件
- 生成汇总 CSV 报告
- 提取编辑效率数据

CRISPResso2 输出文件结构：
CRISPResso_on_<sample_name>/
├── CRISPResso_quantification_of_editing_frequency.txt  # 编辑效率量化
├── CRISPResso_running_log.txt                          # 运行日志
├── Alleles_frequency_table_around_sgRNA_*.txt          # 等位基因频率
└── ...

quantification 文件格式（TSV）：
Amplicon  Unmodified%  Modified%  Reads_aligned  ...
Reference 99.85        0.14       38937          ...

v0.0.2 改进：
- 支持多 amplicon 行解析（不再只取第一行）
- 文件编码容错（支持 UTF-8, UTF-8-BOM, GBK, Latin-1）
- 更健壮的数值解析
- 详细的日志输出
"""

import os
import csv
import glob
import logging

log = logging.getLogger(__name__)


def generate_summary(result_dir, sample_names, output_csv):
    """
    生成汇总 CSV 文件

    参数:
        result_dir: CRISPResso2 输出目录
        sample_names: 样本名列表
        output_csv: 输出 CSV 文件路径

    返回:
        list: 汇总数据列表
    """
    summary = []
    for name in sample_names:
        row = {'Sample': name}
        result = parse_quantification(result_dir, name)
        if result:
            row.update(result)
        else:
            log.warning('Quantification file not found for sample %s', name)
        summary.append(row)

    if summary:
        # 获取所有可能的列名
        keys = sorted(set().union(*[r.keys() for r in summary]))
        with open(output_csv, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(summary)
        log.info('Summary report written: %s', output_csv)

    return summary


def parse_quantification(result_dir, sample_name):
    """
    解析单个样本的 quantification 文件

    参数:
        result_dir: CRISPResso2 输出目录
        sample_name: 样本名

    返回:
        dict: 解析结果，包含 Reads_aligned, Unmodified%, Modified% 等
    """
    if not os.path.isdir(result_dir):
        return None

    # 尝试不同的目录命名模式
    patterns = [
        os.path.join(result_dir, f'CRISPResso_on_{sample_name}'),
        os.path.join(result_dir, f'CRISPResso_{sample_name}'),
    ]
    for folder in patterns:
        if os.path.exists(folder):
            f = os.path.join(folder, 'CRISPResso_quantification_of_editing_frequency.txt')
            if os.path.exists(f):
                return _parse_quant_file(f)

    # 使用 glob 模糊匹配
    found = glob.glob(
        os.path.join(result_dir, f'*{sample_name}*',
                     'CRISPResso_quantification_of_editing_frequency.txt')
    )
    if found:
        return _parse_quant_file(found[0])

    return None


def _parse_quant_file(path):
    """
    解析 quantification 文件

    文件格式（TSV）：
    Amplicon    Unmodified%    Modified%    Reads_aligned    ...
    Reference   99.85          0.14         38937            ...

    v0.0.2: 支持多行解析，主 amplicon 行（第一行）的值加 _primary 后缀，
    同时保留所有行的数据。

    返回:
        dict: 包含 Reads_aligned, Unmodified%, Modified% 的字典
    """
    result = {}

    # 编码容错：依次尝试不同编码
    for encoding in ['utf-8-sig', 'utf-8', 'gbk', 'latin-1']:
        try:
            with open(path, 'r', encoding=encoding) as f:
                reader = csv.DictReader(f, delimiter='\t')
                for i, row in enumerate(reader):
                    if i == 0:
                        # 主 amplicon 行，保留无后缀的键（向后兼容）
                        result['Reads_aligned'] = _safe_int(row.get('Reads_aligned', ''))
                        result['Unmodified%'] = _safe_float_str(row.get('Unmodified%', ''))
                        result['Modified%'] = _safe_float_str(row.get('Modified%', ''))
                    # 所有行都记录
                    amplicon_name = row.get('Amplicon', f'Amplicon_{i}')
                    result[f'Reads_aligned_{amplicon_name}'] = _safe_int(row.get('Reads_aligned', ''))
                    result[f'Unmodified%_{amplicon_name}'] = _safe_float_str(row.get('Unmodified%', ''))
                    result[f'Modified%_{amplicon_name}'] = _safe_float_str(row.get('Modified%', ''))
            break  # 成功读取，退出编码循环
        except UnicodeDecodeError:
            continue
        except Exception as e:
            log.error('Failed to parse file %s: %s', path, e)
            break

    return result


def _safe_int(value):
    """Convert a string to an integer safely; return the original string on failure."""
    try:
        return str(int(float(value)))
    except (ValueError, TypeError):
        return str(value) if value else ''


def _safe_float_str(value):
    """Normalize a percentage string safely; return the original string on failure."""
    try:
        return str(float(value))
    except (ValueError, TypeError):
        return str(value) if value else ''
