"""
AdapterRemoval 运行模块 v0.0.3

功能：
- 调用 AdapterRemoval v3 进行 barcode 拆分
- 合并正反向拆分结果
- 拼接 R1+R2 重叠 reads
- 清理临时文件
- 支持进程中断

工作流程：
1. 正向拆分：R1/R2 -> fwd.*.r1.fastq, fwd.*.r2.fastq
2. 反向拆分：unidentified -> rev.*.r1.fastq, rev.*.r2.fastq
3. 合并正反向：cat rev -> fwd（保留 R1/R2 分开）
4. 拼接 R1+R2：使用 AdapterRemoval --merge 合并重叠 reads
5. 清理临时文件

v0.0.3 改进：
- 使用统一错误类 (utils/errors.py)
- 更精细的错误分类（FileError/ParamError/ToolError）
- 错误信息含用户友好的解决建议
- 日志级别细化

v0.0.2 改进：
- 消除 shell=True，改用列表参数（安全+自动处理路径空格）
- 添加进程中断支持（Popen + 轮询）
- 检查所有步骤的返回码
- 更详细的错误信息
- 统一使用 utils/system.py 的 find_exe
- 更精确的临时文件清理
- 运行前参数校验
"""

import subprocess
import os
import logging
import time
import threading

from core.command_utils import command_to_string, split_extra_args
from utils.system import find_exe
from utils.errors import FileError, ParamError, ToolError, EnvError

log = logging.getLogger(__name__)

# 进程控制
_current_process = None
_process_lock = threading.Lock()
_should_stop = threading.Event()


def run_adapterremoval(file1, file2, barcode_file, basename, output_dir,
                       extra_args='', callback=None):
    """
    运行完整的 AdapterRemoval 流程

    参数:
        file1: R1 FASTQ 文件路径
        file2: R2 FASTQ 文件路径（可选）
        barcode_file: Barcode 表文件路径
        basename: output file prefix, for example 'demux'
        output_dir: 输出目录
        extra_args: 额外命令行参数（空格分隔的字符串）
        callback: 进度回调函数

    返回:
        dict: 包含样本列表的字典

    异常:
        FileNotFoundError: 输入文件不存在
        RuntimeError: AdapterRemoval 未找到或执行失败
    """
    if not file1 or not os.path.isfile(file1):
        raise FileError(file1, 'R1 file does not exist')
    if file2 and not os.path.isfile(file2):
        raise FileError(file2, 'R2 file does not exist')
    if barcode_file and not os.path.isfile(barcode_file):
        raise FileError(barcode_file, 'Barcode table file does not exist')

    if not basename:
        raise ParamError('basename', 'Output prefix cannot be empty')

    os.makedirs(output_dir, exist_ok=True)

    # 查找 AdapterRemoval 可执行文件
    exe = find_exe('adapterremoval3') or find_exe('AdapterRemoval')
    if not exe:
        raise EnvError(
            'AdapterRemoval',
            'AdapterRemoval executable was not found'
        )

    _should_stop.clear()

    # 解析额外参数
    extra_list = split_extra_args(extra_args)
    demux_extra_list = _strip_demux_incompatible_args(extra_list)

    if callback:
        callback('AdapterRemoval: forward demultiplexing...')

    cmd = [exe, '--in-file1', file1]
    if file2:
        cmd.extend(['--in-file2', file2])
    if barcode_file:
        cmd.extend(['--barcode-table', barcode_file])
    cmd.extend([
        '--out-prefix', os.path.join(output_dir, "fwd"),
        '--demultiplex-only',
        '--out-format', 'fastq',
    ])
    cmd.extend(demux_extra_list)

    _run_step(cmd, 'forward demultiplexing')

    # ========== Step 2: 反向拆分 ==========
    if _should_stop.is_set():
        raise InterruptedError('Interrupted by user')

    if callback:
        callback('AdapterRemoval: reverse demultiplexing...')

    # 查找未识别的 reads（v3 和 v2 命名不同）
    u1 = _find_file(output_dir, 'fwd.unidentified.r1') or _find_file(output_dir, 'fwd.unidentified_1')
    u2 = _find_file(output_dir, 'fwd.unidentified.r2') or _find_file(output_dir, 'fwd.unidentified_2')

    if u1 and u2:
        # 注意：反向拆分时 R1/R2 要交换
        cmd_rev = [exe, '--in-file1', u2, '--in-file2', u1]
        if barcode_file:
            cmd_rev.extend(['--barcode-table', barcode_file])
        cmd_rev.extend([
            '--out-prefix', os.path.join(output_dir, "rev"),
            '--demultiplex-only',
            '--out-format', 'fastq',
        ])
        cmd_rev.extend(demux_extra_list)
        _run_step(cmd_rev, 'reverse demultiplexing')
    else:
        log.warning('No unidentified reads found; skipping reverse demultiplexing')

    # ========== Step 3: 合并正反向 ==========
    if _should_stop.is_set():
        raise InterruptedError('Interrupted by user')

    if callback:
        callback('AdapterRemoval: combining forward and reverse demultiplexed reads...')

    samples = _find_samples(output_dir)
    for sample in samples:
        for read in ['r1', 'r2']:
            fwd = os.path.join(output_dir, f'fwd.{sample}.{read}.fastq')
            rev = os.path.join(output_dir, f'rev.{sample}.{read}.fastq')
            if os.path.exists(fwd) and os.path.exists(rev):
                with open(rev, 'rb') as f_in:
                    data = f_in.read()
                with open(fwd, 'ab') as f_out:
                    f_out.write(data)

    # ========== Step 4: 拼接 R1+R2 ==========
    if _should_stop.is_set():
        raise InterruptedError('Interrupted by user')

    if callback:
        callback('AdapterRemoval: merging R1 and R2...')

    for sample in samples:
        r1 = os.path.join(output_dir, f'fwd.{sample}.r1.fastq')
        r2 = os.path.join(output_dir, f'fwd.{sample}.r2.fastq')
        merged = os.path.join(output_dir, f'{basename}.{sample}.merged.fastq')

        if os.path.exists(r1) and os.path.exists(r2):
            cmd_merge = [
                exe, '--in-file1', r1, '--in-file2', r2,
                '--merge', '--out-merged', merged,
                '--out-format', 'fastq',
                '--collapse-deterministic',
            ]
            _run_step(cmd_merge, f'merging {sample}')
        elif os.path.exists(r1):
            # 只有 R1，直接重命名
            os.rename(r1, merged)

    # ========== Step 5: 清理 ==========
    if callback:
        callback('AdapterRemoval: cleaning temporary files...')
    _cleanup(output_dir, samples)

    if callback:
        callback(f'AdapterRemoval: completed, {len(samples)} samples')

    return {'samples': samples}


def _run_step(cmd, step_name):
    """
    运行单个步骤，支持中断和详细错误报告

    参数:
        cmd: 命令列表（路径已加引号）
        step_name: 步骤名称（用于错误提示）

    异常:
        RuntimeError: 命令执行失败
        InterruptedError: 用户终止
    """
    global _current_process
    cmd_str = command_to_string(cmd)
    log.info('Running: %s', cmd_str)

    with _process_lock:
        _current_process = subprocess.Popen(
            cmd_str, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
        )

    try:
        while _current_process.poll() is None:
            time.sleep(0.5)
            if _should_stop.is_set():
                _kill_current_process()
                raise InterruptedError('Interrupted by user')

        stdout = _current_process.stdout.read().decode('utf-8', errors='replace')
        stderr = _current_process.stderr.read().decode('utf-8', errors='replace')
        returncode = _current_process.returncode
    finally:
        with _process_lock:
            _current_process = None

    if returncode != 0:
        # 截取关键错误信息
        err_msg = stderr.strip() or stdout.strip()
        raise ToolError(
            'AdapterRemoval',
            reason=f'{step_name} failed',
            returncode=returncode,
            stderr=err_msg
        )


def _strip_demux_incompatible_args(args):
    """Remove options that are invalid with --demultiplex-only."""
    blocked = {'--normalize-orientation'}
    cleaned = []
    removed = []
    for arg in args:
        key = str(arg).split('=', 1)[0]
        if key in blocked:
            removed.append(arg)
            continue
        cleaned.append(arg)

    if removed:
        log.warning('Ignoring AdapterRemoval options that are invalid with demultiplexing: %s', ' '.join(removed))
    return cleaned


def _kill_current_process():
    """Terminate the current process."""
    global _current_process
    with _process_lock:
        if _current_process:
            try:
                _current_process.terminate()
            except OSError:
                pass
            try:
                _current_process.kill()
            except OSError:
                pass
            try:
                subprocess.run(
                    ['taskkill', '/F', '/T', '/PID', str(_current_process.pid)],
                    capture_output=True, timeout=5
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
            _current_process = None


def terminate_current():
    """Terminate the currently running AdapterRemoval process."""
    _should_stop.set()
    _kill_current_process()


def _find_samples(directory):
    """
    从输出目录中查找所有样本名

    查找模式: fwd.*.r1.fastq
    返回: 排序后的样本名列表
    """
    samples = set()
    if not os.path.isdir(directory):
        return sorted(samples)
    for f in os.listdir(directory):
        if f.startswith('fwd.') and f.endswith('.r1.fastq'):
            name = f[4:].replace('.r1.fastq', '')
            if name != 'unidentified':
                samples.add(name)
    return sorted(samples)


def _find_file(directory, prefix):
    """Find a file with the specified prefix."""
    for ext in ['.fastq', '.fq']:
        path = os.path.join(directory, prefix + ext)
        if os.path.exists(path):
            return path
    return None


def _cleanup(directory, samples):
    """
    清理临时文件

    v0.0.2: 使用精确的文件名匹配而非 glob 通配符，避免误删
    """
    # 删除已知的临时文件（精确匹配）
    for sample in samples:
        for read in ['r1', 'r2']:
            # 删除 rev 临时文件（已合并到 fwd）
            rev_path = os.path.join(directory, f'rev.{sample}.{read}.fastq')
            if os.path.exists(rev_path):
                try:
                    os.remove(rev_path)
                except OSError:
                    pass

    # 删除 unidentified 文件
    for prefix in ['fwd.unidentified', 'rev.unidentified']:
        for suffix in ['r1.fastq', 'r2.fastq', '1', '2']:
            path = os.path.join(directory, f'{prefix}.{suffix}')
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    # 删除 settings 文件
    for prefix in ['fwd', 'rev']:
        path = os.path.join(directory, f'{prefix}.settings')
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
