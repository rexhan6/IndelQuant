"""
CRISPResso2 运行模块 v0.0.3

功能：
- 调用 CRISPResso2 进行基因编辑效率分析
- 支持进程中断
- 详细的错误报告和超时控制

v0.0.3 改进：
- 使用统一错误类 (utils/errors.py)
- 更精细的错误分类（FileError/ParamError/ToolError）
- 错误信息含用户友好的解决建议
- 日志级别细化

v0.0.2 改进：
- 消除 shell=True，改用列表参数（安全+自动处理路径空格）
- 使用 threading.Event 替代裸全局变量管理停止标志
- 添加超时控制（默认 1 小时）
- _kill_process 中 except 改为精确捕获 OSError
- 移除 taskkill 中的 shell=True
- 统一使用 utils/system.py 的 find_exe
- 运行前参数校验
"""

import subprocess
import os
import logging
import threading
import time
import json

from core.command_utils import command_to_string, split_extra_args
from utils.system import find_exe
from utils.errors import FileError, ParamError, ToolError, EnvError

log = logging.getLogger(__name__)

# 进程控制（线程安全）
_current_process = None
_process_lock = threading.Lock()
_should_stop = threading.Event()

# 默认超时时间（秒）
DEFAULT_TIMEOUT = 3600  # 1 小时


def run_crispresso(r1, amplicon_seq, guide_seq, output_dir, sample_name,
                   extra_args='', amplicon_name='Reference', guide_name='sgRNA',
                   callback=None, callback_level=None, timeout=DEFAULT_TIMEOUT):
    """
    运行 CRISPResso2 分析

    参数:
        r1: 输入 FASTQ 文件路径
        amplicon_seq: Amplicon 参考序列
        guide_seq: sgRNA 序列（不含 PAM）
        output_dir: 输出目录
        sample_name: 样本名称
        extra_args: 额外命令行参数
        amplicon_name: Amplicon 名称
        guide_name: sgRNA 名称
        callback: progress callback callback(msg, level='INFO')
        callback_level: log level for error output, default 'ERROR'
        timeout: 超时时间（秒），默认 1 小时

    返回:
        str: CRISPResso2 的 stdout 输出

    异常:
        FileNotFoundError: 输入文件不存在
        ValueError: 必需参数缺失
        RuntimeError: CRISPResso2 未找到或执行失败
        TimeoutError: 运行超时
        InterruptedError: 用户终止
    """
    global _current_process

    if not r1 or not os.path.isfile(r1):
        raise FileError(r1, 'Input file does not exist')
    if not amplicon_seq:
        raise ParamError('amplicon_seq', 'Amplicon sequence cannot be empty')
    if not guide_seq:
        raise ParamError('guide_seq', 'sgRNA sequence cannot be empty')

    exe = _find_crispr()
    if not exe:
        raise EnvError(
            'CRISPResso2',
            'CRISPResso executable was not found'
        )

    cmd_parts = [
        exe,
        '-r1', r1,
        '-a', amplicon_seq,
        '-g', guide_seq,
        '-o', output_dir,
        '-n', sample_name,
        '-an', amplicon_name,
        '-gn', guide_name,
    ]

    if extra_args.strip():
        cmd_parts.extend(split_extra_args(extra_args))

    cmd = command_to_string(cmd_parts)
    log.info('Running CRISPResso: %s', cmd)
    if callback:
        callback(f'CRISPResso: {sample_name}...')
        callback(f'Command: {cmd}')

    _should_stop.clear()

    stdout_lines = []
    stderr_lines = []
    output_lock = threading.Lock()

    with _process_lock:
        _current_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True,
            text=True, encoding='utf-8', errors='replace', bufsize=1
        )
        proc = _current_process

    stdout_thread = threading.Thread(
        target=_consume_stream,
        args=(proc.stdout, stdout_lines, output_lock, callback, 'stdout'),
        daemon=True
    )
    stderr_thread = threading.Thread(
        target=_consume_stream,
        args=(proc.stderr, stderr_lines, output_lock, callback, 'stderr'),
        daemon=True
    )
    stdout_thread.start()
    stderr_thread.start()

    start_time = time.time()
    last_progress_report = start_time
    last_status_report = start_time
    completion_seen = False
    try:
        while proc.poll() is None:
            time.sleep(1)

            elapsed = time.time() - start_time
            now = time.time()
            if callback and now - last_progress_report >= 30:
                callback(f'CRISPResso: {sample_name} running ({elapsed:.0f}s)...')
                last_progress_report = now

            if callback and now - last_status_report >= 10:
                status_msg = _read_status_message(output_dir, sample_name, start_time)
                if status_msg:
                    callback(f'CRISPResso: {sample_name} status - {status_msg}')
                last_status_report = now

            if not completion_seen and _analysis_complete(output_dir, sample_name, start_time):
                completion_seen = True
                if callback:
                    callback(f'CRISPResso: {sample_name} final completion log detected; waiting for normal process exit...')

            if timeout > 0 and elapsed > timeout:
                _kill_process()
                raise ToolError(
                    'CRISPResso2',
                    reason=f'Run timed out ({timeout} seconds), sample: {sample_name}',
                    returncode=None
                )

            if _should_stop.is_set():
                _kill_process()
                raise InterruptedError('Interrupted by user')
    except (InterruptedError, TimeoutError):
        raise
    except Exception as e:
        _kill_process()
        raise RuntimeError(f'CRISPResso runtime error: {e}') from e

    stdout_thread.join(timeout=2)
    stderr_thread.join(timeout=2)
    returncode = proc.returncode
    with output_lock:
        stdout = '\n'.join(stdout_lines)
        stderr = '\n'.join(stderr_lines)

    with _process_lock:
        if _current_process is proc:
            _current_process = None

    if returncode != 0:
        err_msg = stderr.strip() or stdout.strip()
        log.error('CRISPResso failed for %s:\n%s', sample_name, err_msg[:500])
        if callback:
            lvl = callback_level or 'ERROR'
            callback(f'=== CRISPResso2 failed: {sample_name} (return code {returncode}) ===', lvl)
            if err_msg:
                callback('--- stdout/stderr ---', lvl)
                for line in err_msg.split('\n'):
                    callback(f'  {line}', lvl)
            else:
                callback('  (stdout and stderr are both empty)', lvl)
            crispr_log = os.path.join(output_dir, f'CRISPResso2_{sample_name}', 'CRISPResso_RUNNING_LOG.txt')
            if os.path.exists(crispr_log):
                try:
                    with open(crispr_log, 'r', encoding='utf-8', errors='replace') as f:
                        log_content = f.read()
                    callback(f'--- CRISPResso log ({crispr_log}) ---', lvl)
                    for line in log_content.split('\n'):
                        callback(f'  {line}', lvl)
                except OSError:
                    pass
        detail = err_msg.replace('\n', ' ').strip() if err_msg else ''
        reason = f'Sample {sample_name} failed (return code {returncode})'
        if detail:
            reason += f': {detail}'
        raise ToolError(
            'CRISPResso2',
            reason=reason,
            returncode=returncode,
            stderr=err_msg
        )

    elapsed = time.time() - start_time
    log.info('CRISPResso done for %s (%.1fs)', sample_name, elapsed)
    if callback:
        callback(f'CRISPResso: {sample_name} completed ({elapsed:.0f}s)')

    return stdout


def terminate_current():
    """Terminate the current CRISPResso process."""
    _should_stop.set()
    _kill_process()


def _kill_process():
    """Force-terminate the current process and its process tree."""
    global _current_process
    with _process_lock:
        if _current_process:
            # 第一重：terminate
            try:
                _current_process.terminate()
            except OSError:
                pass

            # 第二重：kill
            try:
                _current_process.kill()
            except OSError:
                pass

            # 第三重：Windows taskkill 杀进程树
            try:
                subprocess.run(
                    ['taskkill', '/F', '/T', '/PID', str(_current_process.pid)],
                    capture_output=True, timeout=5
                )
            except (OSError, subprocess.TimeoutExpired):
                pass

            _current_process = None


def _find_crispr():
    """
    查找 CRISPResso 可执行文件

    搜索顺序：
    1. 配置的 Conda 环境 Scripts 目录
    2. 系统 PATH

    返回:
        str: 可执行文件路径，未找到返回 None
    """
    # 先在 Conda 环境中查找
    home = os.path.expanduser('~')
    env_path = os.path.join(home, '.conda', 'envs', 'crispranalysis')
    exe = os.path.join(env_path, 'Scripts', 'CRISPResso.exe')
    if os.path.exists(exe):
        return exe

    # 在 PATH 中查找
    return find_exe('CRISPResso')


def _consume_stream(stream, sink, output_lock, callback, label):
    """Continuously read CRISPResso output to avoid PIPE buffer deadlock."""
    if stream is None:
        return
    try:
        for line in stream:
            text = line.rstrip()
            if not text:
                continue
            with output_lock:
                sink.append(text)
            if callback:
                callback(f'CRISPResso {label}: {text[:800]}')
    except OSError:
        pass


def _analysis_complete(output_dir, sample_name, since=0):
    """Check whether the CRISPResso2 running log reports completion."""
    for folder_name in (f'CRISPResso_on_{sample_name}', f'CRISPResso_{sample_name}'):
        log_path = os.path.join(output_dir, folder_name, 'CRISPResso_RUNNING_LOG.txt')
        if not os.path.exists(log_path):
            continue
        try:
            if since and os.path.getmtime(log_path) < since:
                continue
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                tail = f.read()[-4000:]
            if 'Analysis Complete!' in tail:
                return True
        except OSError:
            continue
    return False


def _read_status_message(output_dir, sample_name, since=0):
    """Read the current status from CRISPResso2 status.json."""
    for folder_name in (f'CRISPResso_on_{sample_name}', f'CRISPResso_{sample_name}'):
        status_path = os.path.join(output_dir, folder_name, 'CRISPResso_status.json')
        if not os.path.exists(status_path):
            continue
        try:
            if since and os.path.getmtime(status_path) < since:
                continue
            with open(status_path, 'r', encoding='utf-8', errors='replace') as f:
                status = json.load(f)
            message = status.get('message', '')
            percent = status.get('percent_complete', '')
            if percent not in ('', None):
                return f'{message} ({percent}%)'
            return message
        except (OSError, ValueError):
            continue
    return ''
