"""
fastp 运行模块 v0.1

fastp 在 v0.1 中作为可选预处理/QC 阶段：默认不改变兼容工作流，
勾选后为每个样本生成 clean FASTQ 以及 HTML/JSON 质控报告。
"""

import os
import subprocess
import threading
import time
import logging

from core.command_utils import command_to_string, split_extra_args
from utils.errors import FileError, ToolError, EnvError
from utils.system import find_exe

log = logging.getLogger(__name__)

_current_process = None
_process_lock = threading.Lock()
_should_stop = threading.Event()


def run_fastp_single(input_fastq, output_fastq, report_dir, sample_name,
                     options=None, callback=None, timeout=3600):
    """Run single-end fastp preprocessing and return the clean FASTQ path."""
    global _current_process

    if not input_fastq or not os.path.isfile(input_fastq):
        raise FileError(input_fastq, 'fastp input file does not exist')

    exe = find_exe('fastp')
    if not exe:
        raise EnvError('fastp', 'fastp executable was not found')

    options = options or {}
    os.makedirs(os.path.dirname(output_fastq), exist_ok=True)
    os.makedirs(report_dir, exist_ok=True)

    html_report = os.path.join(report_dir, f'{sample_name}.fastp.html')
    json_report = os.path.join(report_dir, f'{sample_name}.fastp.json')

    parts = [
        exe,
        '-i', input_fastq,
        '-o', output_fastq,
        '-h', html_report,
        '-j', json_report,
        '-w', str(options.get('thread', 4)),
        '-l', str(options.get('length_required', 15)),
        '-q', str(options.get('qualified_quality_phred', 15)),
        '-u', str(options.get('unqualified_percent_limit', 40)),
        '-n', str(options.get('n_base_limit', 5)),
    ]

    if options.get('average_qual'):
        parts.extend(['-e', str(options['average_qual'])])
    if options.get('detect_adapter_for_pe'):
        parts.append('--detect_adapter_for_pe')
    if options.get('disable_adapter_trimming'):
        parts.append('--disable_adapter_trimming')
    if options.get('cut_front'):
        parts.append('--cut_front')
    if options.get('cut_tail'):
        parts.append('--cut_tail')
    if options.get('cut_right'):
        parts.append('--cut_right')
    if options.get('cut_window_size'):
        parts.extend(['--cut_window_size', str(options['cut_window_size'])])
    if options.get('cut_mean_quality'):
        parts.extend(['--cut_mean_quality', str(options['cut_mean_quality'])])
    if options.get('trim_poly_g'):
        parts.append('--trim_poly_g')
    if options.get('trim_poly_x'):
        parts.append('--trim_poly_x')
    if options.get('low_complexity_filter'):
        parts.append('--low_complexity_filter')
        if options.get('complexity_threshold'):
            parts.extend(['--complexity_threshold', str(options['complexity_threshold'])])
    if options.get('dont_eval_duplication'):
        parts.append('--dont_eval_duplication')
    if options.get('overrepresentation_analysis'):
        parts.append('--overrepresentation_analysis')

    parts.extend(split_extra_args(options.get('extra_args', '')))
    cmd = command_to_string(parts)

    if callback:
        callback(f'fastp: preprocessing {sample_name}...')
        callback(f'Command: {cmd}')

    _should_stop.clear()
    start = time.time()
    with _process_lock:
        _current_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
        )

    try:
        while _current_process.poll() is None:
            time.sleep(0.5)
            if timeout and time.time() - start > timeout:
                _kill_process()
                raise ToolError('fastp', reason=f'Run timed out for sample: {sample_name}')
            if _should_stop.is_set():
                _kill_process()
                raise InterruptedError('Interrupted by user')

        stdout = _current_process.stdout.read().decode('utf-8', errors='replace')
        stderr = _current_process.stderr.read().decode('utf-8', errors='replace')
        returncode = _current_process.returncode
    finally:
        with _process_lock:
            _current_process = None

    if returncode != 0:
        detail = (stderr.strip() or stdout.strip())
        raise ToolError('fastp', reason=f'Preprocessing failed for sample {sample_name}',
                        returncode=returncode, stderr=detail)

    if callback:
        callback(f'fastp: {sample_name} completed, report: {html_report}')

    return output_fastq


def terminate_current():
    """Terminate the current fastp process."""
    _should_stop.set()
    _kill_process()


def _kill_process():
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
