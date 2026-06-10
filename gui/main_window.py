"""
主窗口模块 v0.0.3

功能：
- 构建完整的 GUI 界面
- 菜单栏（文件/运行/工具/帮助）
- 管理页面切换（侧边栏导航）
- 协调各模块的交互
- 执行分析流程
- 管理样本列表和结果展示

v0.0.3 改进：
- 使用统一错误处理 (utils/errors.py)
- 日志面板支持级别过滤（INFO/WARNING/ERROR）
- 错误提示使用用户友好消息
- 运行状态更精细的步骤显示
- 菜单栏替代快捷键（文件/运行/工具/帮助）
- 错误输出全量显示，不再截断
- 拖拽文件支持
- 右键菜单（复制、粘贴、清空）

v0.0.2 改进：
- 修复进程终止（移除 shell=True 的 taskkill、用 /PID 替代 /IM）
- 修复配置文件在打包后的路径问题
- Treeview 字体调整为合理大小
- 日志面板支持文件输出
- 运行前更完善的参数校验
- 保存配置时包含更多 CRISPResso2 参数
- 修复 lambda 闭包捕获问题
- 结果面板集成
- 统一使用 utils/system.py 的 Conda 路径查找
"""

import customtkinter as ctk
from tkinter import messagebox, filedialog
import tkinter as tk
from tkinter import ttk
import threading
import logging
import os
import sys
import time
import subprocess

from gui.styles import COLORS, FONT_SUBTITLE, FONT_NORMAL, FONT_BUTTON, FONT_INPUT, FONT_COMBO, FONT_CHECK, FONT_HINT, toggle_theme, get_theme
from gui.params_panel import AdapterRemovalPanel, CRISPRessoPanel
from gui.log_panel import LogPanel, GUILogHandler
from gui.result_panel import ResultPanel
from config.config_manager import load_config, save_config, add_to_history
from utils.system import get_cpu_count, find_conda_env_path
from utils.errors import get_user_friendly_message, format_error_for_log, CRISPRError
from core.adapter_runner import run_adapterremoval, terminate_current as terminate_adapter
from core.crispresso_runner import run_crispresso, terminate_current as terminate_crispresso
from core.fastp_runner import run_fastp_single, terminate_current as terminate_fastp
from core.result_parser import generate_summary, parse_quantification

log = logging.getLogger(__name__)

# 版本信息
APP_NAME = 'IndelQuant'
VERSION = '0.1'
AUTHOR = 'Rex Han'
GITHUB = 'https://github.com/rexhancx/IndelQuant'

# 侧边栏导航项
NAV_ITEMS = [
    ('1', 'Demultiplexing & QC'),
    ('2', 'CRISPResso2'),
    ('3', 'Run Workspace'),
    ('4', 'Visualization'),
    ('5', 'Environment'),
]


def _get_app_dir():
    """Return the application directory, including packaged builds."""
    if getattr(sys, 'frozen', False):
        # PyInstaller build: use the executable directory.
        return os.path.dirname(sys.executable)
    else:
        # Development mode: use the project root.
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class MainWindow:
    def __init__(self):
        self.root = ctk.CTk()
        self._dnd_enabled = True
        
        self.root.title(f'{APP_NAME} v{VERSION}')
        self.root.geometry('1200x800')
        self.root.minsize(1000, 650)

        # Configuration path works in source and packaged builds.
        self.config_path = os.path.join(_get_app_dir(), 'config.json')
        self.config = load_config(self.config_path)

        # Runtime state.
        self._running = False
        self._stop_flag = False
        self._current_step = None

        # UI components.
        self._nav_buttons = []
        self._cpu_count = get_cpu_count()
        self._env_name = self.config.get('env_name', 'crispranalysis')

        # Sample data.
        self._samples = []
        self._sample_checks = {}
        self._summary_by_sample = {}
        self._run_token = 0
        self._monitored_results = set()

        # Build UI.
        self._build_ui()
        self._setup_logging()
        self._load_config_to_ui()
        self._switch_page(0)

        # Close event.
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

    def _build_menubar(self):
        """Build the menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu.
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label='Save Configuration', command=self._save_current_config)
        file_menu.add_command(label='Export Excel', command=self._export_excel)
        file_menu.add_separator()
        file_menu.add_command(label='Exit', command=self._on_close)
        menubar.add_cascade(label='File', menu=file_menu)

        # Run menu.
        run_menu = tk.Menu(menubar, tearoff=0)
        run_menu.add_command(label='Run Full Workflow', command=lambda: self._run_step(0))
        run_menu.add_command(label='Step 1: AdapterRemoval', command=lambda: self._run_step(1))
        run_menu.add_command(label='Step 2: CRISPResso2', command=lambda: self._run_step(2))
        run_menu.add_separator()
        run_menu.add_command(label='Stop', command=self._stop)
        menubar.add_cascade(label='Run', menu=run_menu)

        # Tools menu.
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label='Check Environment', command=self._check_env)
        tools_menu.add_command(label='Refresh Samples', command=self._refresh_samples)
        tools_menu.add_separator()
        tools_menu.add_command(label='Create Conda Environment', command=self._create_env)
        tools_menu.add_command(label='Install Dependencies', command=self._install_deps)
        menubar.add_cascade(label='Tools', menu=tools_menu)

        # Help menu.
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label='About', command=self._show_about)
        menubar.add_cascade(label='Help', menu=help_menu)

    def _show_about(self):
        """Show the About dialog."""
        messagebox.showinfo(
            'About',
            f'{APP_NAME} v{VERSION}\n\n'
            f'Author: {AUTHOR}\n'
            f'GitHub: {GITHUB}\n\n'
            f'Powered by CRISPResso2 and AdapterRemoval\n'
            f'For amplicon-based indel quantification'
        )

    def _build_ui(self):
        """Build the main UI."""
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # Menu bar.
        self._build_menubar()

        # Sidebar.
        sidebar = ctk.CTkFrame(self.root, width=200, corner_radius=0, fg_color=COLORS['sidebar'])
        sidebar.grid(row=0, column=0, sticky='nsw')
        sidebar.grid_propagate(False)

        # Logo
        logo = ctk.CTkFrame(sidebar, fg_color='transparent')
        logo.pack(fill='x', padx=16, pady=(24, 16))
        ctk.CTkLabel(logo, text='Indel', font=ctk.CTkFont(size=24, weight='bold'), text_color='#ffffff').pack(anchor='w')
        ctk.CTkLabel(logo, text='Quant', font=ctk.CTkFont(size=15), text_color=COLORS['sidebar_text']).pack(anchor='w')
        ctk.CTkLabel(logo, text=f'v{VERSION}', font=ctk.CTkFont(size=10), text_color=COLORS['sidebar_text']).pack(anchor='w', pady=(2, 0))

        # Navigation buttons.
        nav = ctk.CTkFrame(sidebar, fg_color='transparent')
        nav.pack(fill='x', padx=12, pady=8)
        for i, (icon, text) in enumerate(NAV_ITEMS):
            btn = ctk.CTkButton(
                nav, text=f'  {icon}  {text}', anchor='w',
                font=ctk.CTkFont(size=13, weight='bold'), height=42, corner_radius=8,
                fg_color='transparent', text_color=COLORS['sidebar_text'],
                hover_color=COLORS['sidebar_active'],
                command=lambda idx=i: self._switch_page(idx)
            )
            btn.pack(fill='x', pady=4)
            self._nav_buttons.append(btn)

        # Content area.
        self.content = ctk.CTkFrame(self.root, corner_radius=0, fg_color=COLORS['bg'])
        self.content.grid(row=0, column=1, sticky='nsew')
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        # Build pages.
        self.pages = [
            AdapterRemovalPanel(self.content),
            CRISPRessoPanel(self.content),
            self._build_run_page(),
            self._build_visualization_page(),
            self._build_settings_page(),
        ]

    def _build_run_page(self):
        """Build the run workspace page."""
        page = ctk.CTkFrame(self.content, fg_color=COLORS['bg'])

        # Top control bar.
        top = ctk.CTkFrame(page, fg_color=COLORS['card'], corner_radius=14)
        top.pack(fill='x', padx=20, pady=(20, 10))

        btn_row = ctk.CTkFrame(top, fg_color='transparent')
        btn_row.pack(fill='x', padx=20, pady=(16, 8))

        # Run buttons.
        self.btn_run_all = ctk.CTkButton(
            btn_row, text='▶  Run All', font=ctk.CTkFont(size=14, weight='bold'),
            height=42, corner_radius=10, fg_color=COLORS['success'],
            hover_color='#16a34a', command=lambda: self._run_step(0)
        )
        self.btn_run_all.pack(side='left', padx=(0, 8))

        self.btn_step1 = ctk.CTkButton(
            btn_row, text='Step 1: AR', font=ctk.CTkFont(size=13),
            height=42, corner_radius=10, fg_color=COLORS['primary'],
            hover_color=COLORS['primary_hover'], command=lambda: self._run_step(1)
        )
        self.btn_step1.pack(side='left', padx=(0, 8))

        self.btn_step2 = ctk.CTkButton(
            btn_row, text='Step 2: CR', font=ctk.CTkFont(size=13),
            height=42, corner_radius=10, fg_color=COLORS['accent'],
            hover_color='#7c3aed', command=lambda: self._run_step(2)
        )
        self.btn_step2.pack(side='left', padx=(0, 8))

        # Stop button.
        self.btn_stop = ctk.CTkButton(
            btn_row, text='■ Stop', font=ctk.CTkFont(size=13),
            height=42, corner_radius=10, fg_color=COLORS['danger'],
            hover_color='#dc2626', command=self._stop, state='disabled'
        )
        self.btn_stop.pack(side='left', padx=(16, 0))

        # Status bar.
        status_row = ctk.CTkFrame(top, fg_color='transparent')
        status_row.pack(fill='x', padx=20, pady=(4, 16))
        self.lbl_status = ctk.CTkLabel(status_row, text='Ready', font=ctk.CTkFont(size=13), text_color=COLORS['text_secondary'])
        self.lbl_status.pack(side='left')
        self.progress = ctk.CTkProgressBar(status_row, width=300, height=8, corner_radius=4)
        self.progress.pack(side='right', padx=10)
        self.progress.set(0)

        # Bottom area: log and sample table.
        bottom = ctk.CTkFrame(page, fg_color='transparent')
        bottom.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_rowconfigure(0, weight=1)
        bottom.grid_rowconfigure(1, weight=4)

        # Log area.
        log_card = ctk.CTkFrame(bottom, fg_color=COLORS['card'], corner_radius=14)
        log_card.grid(row=0, column=0, sticky='nsew', pady=(0, 10))

        # Log file path.
        log_dir = os.path.join(_get_app_dir(), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f'crispr_{time.strftime("%Y%m%d_%H%M%S")}.log')
        self.log_panel = LogPanel(log_card, log_file=log_file)
        self.log_panel.pack(fill='both', expand=True, padx=12, pady=8)

        # Sample table area.
        table_card = ctk.CTkFrame(bottom, fg_color=COLORS['card'], corner_radius=14)
        table_card.grid(row=1, column=0, sticky='nsew', pady=(0, 10))

        # Header and buttons.
        table_header = ctk.CTkFrame(table_card, fg_color='transparent')
        table_header.pack(fill='x', padx=14, pady=(10, 4))
        ctk.CTkLabel(table_header, text='Sample Analysis Results', font=ctk.CTkFont(size=16, weight='bold'),
                     text_color=COLORS['text']).pack(side='left')
        ctk.CTkButton(table_header, text='Export Excel', width=92, height=30, corner_radius=8,
                      font=ctk.CTkFont(size=12), command=self._export_excel).pack(side='right', padx=2)
        ctk.CTkButton(table_header, text='Select All', width=78, height=30, corner_radius=8,
                      font=ctk.CTkFont(size=12), command=self._select_all).pack(side='right', padx=2)
        ctk.CTkButton(table_header, text='Deselect All', width=92, height=30, corner_radius=8,
                      font=ctk.CTkFont(size=12), command=self._deselect_all).pack(side='right', padx=2)
        ctk.CTkButton(table_header, text='Refresh', width=72, height=30, corner_radius=8,
                      font=ctk.CTkFont(size=12), command=self._refresh_samples).pack(side='right', padx=2)

        # Treeview table.
        tree_frame = ctk.CTkFrame(table_card, fg_color='transparent')
        tree_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        cols = ('select', 'sample', 'status', 'reads', 'modified', 'unmodified')
        self.tree = ttk.Treeview(tree_frame, columns=cols, show='headings', selectmode='none')
        self.tree.heading('select', text='✓')
        self.tree.heading('sample', text='Sample')
        self.tree.heading('status', text='Status')
        self.tree.heading('reads', text='Reads')
        self.tree.heading('modified', text='Modified%')
        self.tree.heading('unmodified', text='Unmodified%')
        self.tree.column('select', width=60, anchor='center')
        self.tree.column('sample', width=180, anchor='center')
        self.tree.column('status', width=150, anchor='center')
        self.tree.column('reads', width=150, anchor='center')
        self.tree.column('modified', width=150, anchor='center')
        self.tree.column('unmodified', width=150, anchor='center')

        # Configure readable Treeview fonts.
        style = ttk.Style()
        style.configure('Treeview', font=('Segoe UI', 16), rowheight=42)
        style.configure('Treeview.Heading', font=('Segoe UI', 16, 'bold'))

        sb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        self.tree.bind('<Button-1>', self._on_tree_click)

        return page

    def _on_tree_click(self, event):
        """Toggle a sample checkbox from the table."""
        item = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if item and col == '#1':
            sample = self.tree.item(item, 'values')[1]
            if sample in self._sample_checks:
                current = self._sample_checks[sample]
                self._sample_checks[sample] = not current
                self.tree.set(item, 'select', '☑' if not current else '☐')

    def _export_excel(self):
        """Export analysis results to Excel."""
        from utils.export import export_to_excel, export_chart_image
        cr = self.pages[1].get_params()
        workdir = self.var_workdir.get()
        output_dir = os.path.join(workdir, cr.get('output_dir', './results').lstrip('./'))

        # Collect current result data.
        summary = []
        for sample in self._samples:
            row_data = {'Sample': sample}
            result = parse_quantification(output_dir, sample)
            if result:
                row_data.update(result)
            summary.append(row_data)

        if not summary:
            messagebox.showinfo('Notice', 'No data available for export.')
            return

        # Choose save path.
        path = filedialog.asksaveasfilename(
            defaultextension='.xlsx',
            filetypes=[('Excel', '*.xlsx'), ('CSV', '*.csv'), ('PNG', '*.png')],
            initialdir=output_dir,
            initialfile='crispr_analysis_report'
        )
        if not path:
            return

        if path.endswith('.xlsx'):
            if export_to_excel(summary, path):
                messagebox.showinfo('Success', f'Exported to:\n{path}')
                self._log(f'Excel export completed: {path}')
            else:
                messagebox.showerror('Export Failed', 'Export failed. Please check whether openpyxl is installed.')
        elif path.endswith('.csv'):
            from utils.export import export_to_csv
            if export_to_csv(summary, path):
                messagebox.showinfo('Success', f'Exported to:\n{path}')
            else:
                messagebox.showerror('Export Failed', 'Export failed.')
        elif path.endswith('.png'):
            if export_chart_image(summary, path):
                messagebox.showinfo('Success', f'Exported to:\n{path}')
            else:
                messagebox.showerror('Export Failed', 'Export failed. Please check whether matplotlib is installed.')

    def _refresh_samples(self):
        """Refresh the sample list."""
        cr = self.pages[1].get_params()
        workdir = self.var_workdir.get()
        output_dir = os.path.join(workdir, cr.get('output_dir', './results').lstrip('./'))
        basename = self.pages[0].get_params().get('basename', 'demux')
        samples = self._find_merged_samples(output_dir, basename)
        if samples:
            self._update_sample_table(samples, output_dir)
            self.log_panel.log(f'Found {len(samples)} samples')
        else:
            self.log_panel.log('No sample files found')

    def _update_sample_table(self, samples, output_dir=''):
        """Update the sample table."""
        self._samples = samples
        self._sample_checks = {s: True for s in samples}
        self._summary_by_sample = {}
        for item in self.tree.get_children():
            self.tree.delete(item)
        for sample in samples:
            reads = modified = unmodified = ''
            status = 'Pending'
            if output_dir:
                result = parse_quantification(output_dir, sample)
                if result:
                    row = {'Sample': sample}
                    row.update(result)
                    self._summary_by_sample[sample] = row
                    reads = result.get('Reads_aligned', '')
                    modified = result.get('Modified%', '')
                    unmodified = result.get('Unmodified%', '')
                    status = '✓ Completed'
            self.tree.insert('', 'end', values=('☑', sample, status, reads, modified, unmodified))

        # Update result plots.
        self._refresh_result_panel(samples)

    def _select_all(self):
        """Select all samples."""
        for item in self.tree.get_children():
            sample = self.tree.item(item, 'values')[1]
            self._sample_checks[sample] = True
            self.tree.set(item, 'select', '☑')

    def _deselect_all(self):
        """Deselect all samples."""
        for item in self.tree.get_children():
            sample = self.tree.item(item, 'values')[1]
            self._sample_checks[sample] = False
            self.tree.set(item, 'select', '☐')

    def _get_selected_samples(self):
        """Return selected sample names."""
        return [s for s, checked in self._sample_checks.items() if checked]

    def _update_sample_status(self, sample_name, status, reads='', modified='', unmodified=''):
        """Update one sample status."""
        for item in self.tree.get_children():
            if self.tree.item(item, 'values')[1] == sample_name:
                self.tree.set(item, 'status', status)
                if reads:
                    self.tree.set(item, 'reads', reads)
                if modified:
                    self.tree.set(item, 'modified', modified)
                if unmodified:
                    self.tree.set(item, 'unmodified', unmodified)
                return

    def _record_sample_result(self, sample_name, result, output_dir=None):
        """Record one sample result and sync the table and plots."""
        row = {'Sample': sample_name}
        row.update(result)
        self._summary_by_sample[sample_name] = row
        self._monitored_results.add(sample_name)
        self._update_sample_status(
            sample_name, '✓ Completed',
            result.get('Reads_aligned', ''),
            result.get('Modified%', ''),
            result.get('Unmodified%', '')
        )
        self._refresh_result_panel()
        if output_dir:
            self._write_cached_summary(output_dir)

    def _refresh_result_panel(self, samples=None):
        """Refresh visualization from the current result cache."""
        order = samples or self._samples
        summary = [self._summary_by_sample[s] for s in order if s in self._summary_by_sample]
        if summary:
            self.result_panel.load_summary(summary)

    def _write_cached_summary(self, output_dir):
        """Write parsed sample results to the summary CSV."""
        samples = [s for s in self._samples if s in self._summary_by_sample]
        if not samples:
            return
        try:
            csv_path = os.path.join(output_dir, 'crispr_summary.csv')
            generate_summary(output_dir, samples, csv_path)
        except Exception as e:
            self._log(f'Automatic summary export failed: {e}', level='WARNING')

    def _start_result_monitor(self, output_dir, sample_name, progress_value, run_token):
        """Start automatic monitoring for one sample result."""
        self._monitor_sample_result(output_dir, sample_name, progress_value, run_token, attempts_left=720)

    def _monitor_sample_result(self, output_dir, sample_name, progress_value, run_token, attempts_left):
        """Poll the CRISPResso2 result file and sync the UI as soon as it appears."""
        if run_token != self._run_token or sample_name in self._monitored_results:
            return

        result = parse_quantification(output_dir, sample_name)
        if result:
            self._log(f'{sample_name} result detected; updating table and visualization')
            self._record_sample_result(sample_name, result, output_dir=output_dir)
            self.progress.set(progress_value)
            self.lbl_status.configure(text=f'{sample_name} result detected; waiting for CRISPResso2 to finish...', text_color=COLORS['primary'])
            return

        if attempts_left <= 0 or not self._running:
            return

        self.root.after(
            5000,
            lambda: self._monitor_sample_result(output_dir, sample_name, progress_value, run_token, attempts_left - 1)
        )

    def _build_visualization_page(self):
        """Build the visualization page."""
        page = ctk.CTkFrame(self.content, fg_color=COLORS['bg'])

        # Title.
        title = ctk.CTkFrame(page, fg_color=COLORS['card'], corner_radius=14)
        title.pack(fill='x', padx=20, pady=(20, 10))
        ctk.CTkLabel(title, text='Data Visualization', font=ctk.CTkFont(size=20, weight='bold'),
                     text_color=COLORS['text']).pack(anchor='w', padx=20, pady=16)

        # Chart area.
        chart_card = ctk.CTkFrame(page, fg_color=COLORS['card'], corner_radius=14)
        chart_card.pack(fill='both', expand=True, padx=20, pady=(0, 20))

        self.result_panel = ResultPanel(chart_card)
        self.result_panel.pack(fill='both', expand=True, padx=12, pady=12)

        return page

    def _build_settings_page(self):
        """Build the environment page."""
        page = ctk.CTkFrame(self.content, fg_color=COLORS['bg'])
        scroll = ctk.CTkScrollableFrame(page, fg_color='transparent')
        scroll.pack(fill='both', expand=True, padx=20, pady=20)

        # Working directory.
        card = ctk.CTkFrame(scroll, fg_color=COLORS['card'], corner_radius=14)
        card.pack(fill='x', pady=(0, 12))
        ctk.CTkLabel(card, text='Working Directory', font=FONT_SUBTITLE(), text_color=COLORS['text']).pack(anchor='w', padx=16, pady=(14, 6))
        row = ctk.CTkFrame(card, fg_color='transparent')
        row.pack(fill='x', padx=16, pady=(0, 14))
        self.var_workdir = ctk.StringVar(value=self.config.get('workdir', os.getcwd()))
        ctk.CTkEntry(row, textvariable=self.var_workdir, font=FONT_INPUT(), corner_radius=8, height=34).pack(side='left', fill='x', expand=True, padx=(0, 8))
        ctk.CTkButton(row, text='Browse', width=72, height=34, corner_radius=8,
                      command=lambda: self.var_workdir.set(filedialog.askdirectory() or self.var_workdir.get())).pack(side='left')

        # Conda environment.
        card = ctk.CTkFrame(scroll, fg_color=COLORS['card'], corner_radius=14)
        card.pack(fill='x', pady=(0, 12))
        ctk.CTkLabel(card, text='Conda Environment', font=FONT_SUBTITLE(), text_color=COLORS['text']).pack(anchor='w', padx=16, pady=(14, 6))

        row = ctk.CTkFrame(card, fg_color='transparent')
        row.pack(fill='x', padx=16, pady=4)
        ctk.CTkLabel(row, text='Conda path:', font=FONT_NORMAL(), width=100, anchor='e').pack(side='left')
        self.var_conda = ctk.StringVar(value=self._find_conda())
        ctk.CTkEntry(row, textvariable=self.var_conda, font=FONT_INPUT(), corner_radius=8, height=34).pack(side='left', padx=8, fill='x', expand=True)
        ctk.CTkButton(row, text='Browse', width=72, height=34, corner_radius=8,
                      command=lambda: self.var_conda.set(filedialog.askopenfilename(filetypes=[('Executable', '*.exe')]) or self.var_conda.get())).pack(side='left')

        row = ctk.CTkFrame(card, fg_color='transparent')
        row.pack(fill='x', padx=16, pady=4)
        ctk.CTkLabel(row, text='Environment:', font=FONT_NORMAL(), width=100, anchor='e').pack(side='left')
        self.var_env_name = ctk.StringVar(value=self._env_name)
        ctk.CTkEntry(row, textvariable=self.var_env_name, font=FONT_INPUT(), corner_radius=8, height=34, width=200).pack(side='left', padx=8)

        btn_frame = ctk.CTkFrame(card, fg_color='transparent')
        btn_frame.pack(fill='x', padx=16, pady=(8, 4))
        ctk.CTkButton(btn_frame, text='Create Environment', font=FONT_BUTTON(), height=38, corner_radius=8,
                      fg_color=COLORS['primary'], hover_color=COLORS['primary_hover'], command=self._create_env).pack(side='left', padx=4)
        ctk.CTkButton(btn_frame, text='Install Dependencies', font=FONT_BUTTON(), height=38, corner_radius=8,
                      fg_color=COLORS['accent'], hover_color='#7c3aed', command=self._install_deps).pack(side='left', padx=4)
        ctk.CTkButton(btn_frame, text='Check Environment', font=FONT_BUTTON(), height=38, corner_radius=8,
                      fg_color=COLORS['success'], hover_color='#16a34a', command=self._check_env).pack(side='left', padx=4)

        self.settings_progress = ctk.CTkProgressBar(card, height=8, corner_radius=4)
        self.settings_progress.pack(fill='x', padx=16, pady=(8, 4))
        self.settings_progress.set(0)
        self.lbl_settings_status = ctk.CTkLabel(card, text='Ready', font=FONT_NORMAL(), text_color=COLORS['text_secondary'])
        self.lbl_settings_status.pack(anchor='w', padx=16, pady=(0, 4))
        self.settings_log = ctk.CTkTextbox(card, font=ctk.CTkFont(family='Consolas', size=11),
                                            fg_color='#1e1e2e', text_color='#cdd6f4', corner_radius=8, height=120)
        self.settings_log.pack(fill='x', padx=16, pady=(0, 14))
        self.settings_log.configure(state='disabled')

        # About.
        card = ctk.CTkFrame(scroll, fg_color=COLORS['card'], corner_radius=14)
        card.pack(fill='x', pady=(0, 12))
        ctk.CTkLabel(card, text='About', font=FONT_SUBTITLE(), text_color=COLORS['text']).pack(anchor='w', padx=16, pady=(14, 6))
        info = ctk.CTkFrame(card, fg_color='transparent')
        info.pack(fill='x', padx=16, pady=(0, 14))
        ctk.CTkLabel(info, text=f'{APP_NAME} v{VERSION}', font=ctk.CTkFont(size=16, weight='bold'), text_color=COLORS['primary']).pack(anchor='w', pady=2)
        ctk.CTkLabel(info, text=f'Author: {AUTHOR}', font=FONT_NORMAL()).pack(anchor='w', pady=1)
        ctk.CTkLabel(info, text=f'GitHub: {GITHUB}', font=FONT_NORMAL(), text_color=COLORS['primary']).pack(anchor='w', pady=1)

        return page

    def _find_conda(self):
        """Find the Conda installation path."""
        from utils.env_checker import _find_conda_base
        base = _find_conda_base()
        if base:
            for exe_name in ['_conda.exe', 'conda.exe', 'Scripts\\conda.exe']:
                exe = os.path.join(base, exe_name)
                if os.path.exists(exe):
                    return exe
        return ''

    def _settings_log(self, msg):
        """Add a message to the Environment page log."""
        self.settings_log.configure(state='normal')
        self.settings_log.insert('end', msg + '\n')
        self.settings_log.see('end')
        self.settings_log.configure(state='disabled')

    def _create_env(self):
        """Create the Conda environment."""
        conda = self.var_conda.get()
        env_name = self.var_env_name.get()
        if not conda:
            messagebox.showwarning('Notice', 'Please set the Conda path first.')
            return
        self.lbl_settings_status.configure(text='Creating environment...')
        def task():
            proc = subprocess.run(f'"{conda}" create -n "{env_name}" python=3.10 -y --quiet',
                                 capture_output=True, text=True, timeout=600, shell=True)
            if proc.returncode == 0:
                self.root.after(0, lambda: self._settings_log('Environment created successfully.'))
                self.root.after(0, lambda: self.lbl_settings_status.configure(text='Environment ready'))
            else:
                self.root.after(0, lambda: self._settings_log(f'Environment creation failed: {proc.stderr[-200:]}'))
                self.root.after(0, lambda: self.lbl_settings_status.configure(text='Creation failed'))
        threading.Thread(target=task, daemon=True).start()

    def _install_deps(self):
        """Install dependencies."""
        conda = self.var_conda.get()
        env_name = self.var_env_name.get()
        if not conda:
            messagebox.showwarning('Notice', 'Please set the Conda path first.')
            return
        self.lbl_settings_status.configure(text='Installing dependencies...')
        self.settings_progress.set(0.1)
        def task():
            env_path = find_conda_env_path(env_name)
            if not env_path:
                self.root.after(0, lambda: self._settings_log(f'Environment {env_name} was not found. Create it first.'))
                self.root.after(0, lambda: self.lbl_settings_status.configure(text='Environment not found'))
                return
            env_python = os.path.join(env_path, 'python.exe')
            self.root.after(0, lambda: self._settings_log('Installing AdapterRemoval...'))
            self.root.after(0, lambda: self.settings_progress.set(0.2))
            proc = subprocess.run(f'"{conda}" install -n "{env_name}" -c bioconda adapterremoval -y --quiet',
                                 capture_output=True, text=True, timeout=600, shell=True)
            self.root.after(0, lambda: self._settings_log('AdapterRemoval installed successfully.' if proc.returncode == 0 else 'AdapterRemoval installation failed.'))
            self.root.after(0, lambda: self._settings_log('Installing CRISPResso2...'))
            self.root.after(0, lambda: self.settings_progress.set(0.5))
            proc = subprocess.run(f'"{env_python}" -m pip install CRISPResso2',
                                 capture_output=True, text=True, timeout=600, shell=True)
            self.root.after(0, lambda: self._settings_log('CRISPResso2 installed successfully.' if proc.returncode == 0 else 'CRISPResso2 installation failed.'))
            self.root.after(0, lambda: self._settings_log('Installing fastp...'))
            self.root.after(0, lambda: self.settings_progress.set(0.7))
            proc = subprocess.run(f'"{conda}" install -n "{env_name}" -c bioconda fastp -y --quiet',
                                 capture_output=True, text=True, timeout=600, shell=True)
            self.root.after(0, lambda: self._settings_log('fastp installed successfully.' if proc.returncode == 0 else 'fastp installation failed.'))
            self.root.after(0, lambda: self.settings_progress.set(1.0))
            self.root.after(0, lambda: self.lbl_settings_status.configure(text='Installation complete'))
        threading.Thread(target=task, daemon=True).start()

    def _check_env(self):
        """Check the runtime environment."""
        self.settings_log.configure(state='normal')
        self.settings_log.delete('0.0', 'end')
        self.settings_log.configure(state='disabled')
        from utils.env_checker import check_all
        results = check_all(self.var_env_name.get())
        for tool, info in results.items():
            status = '✓' if info['ok'] else '✗'
            self._settings_log(f'{status} {tool}: {info["version"]}')
        self._settings_log('Environment check complete.')

    def _switch_page(self, idx):
        """Switch page."""
        for i, btn in enumerate(self._nav_buttons):
            btn.configure(fg_color=COLORS['sidebar_active'] if i == idx else 'transparent',
                         text_color=COLORS['sidebar_text_active'] if i == idx else COLORS['sidebar_text'])
        for p in self.pages:
            p.grid_forget()
        self.pages[idx].grid(row=0, column=0, sticky='nsew')

    def _setup_logging(self):
        """Set up logging."""
        handler = GUILogHandler(self.log_panel)
        handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)

    def _load_config_to_ui(self):
        """Load configuration into the UI."""
        self.pages[0].set_params(self.config)
        self.pages[1].set_params(self.config)
        self.pages[0].set_history(self.config.get('history', {}))
        self.pages[1].set_history(self.config.get('history', {}))

    def _set_buttons_state(self, state):
        """Set run button state."""
        for btn in [self.btn_run_all, self.btn_step1, self.btn_step2]:
            btn.configure(state=state)
        self.btn_stop.configure(state='normal' if state == 'disabled' else 'disabled')

    def _run_step(self, step):
        """Run the selected analysis step."""
        ar = self.pages[0].get_params()
        cr = self.pages[1].get_params()

        # Save history.
        add_to_history(self.config, 'r1', ar['r1'])
        add_to_history(self.config, 'r2', ar['r2'])
        add_to_history(self.config, 'barcode_file', ar['barcode_file'])
        add_to_history(self.config, 'amplicon_seq', cr['amplicon_seq'])
        add_to_history(self.config, 'guide_seq', cr['guide_seq'])
        add_to_history(self.config, 'output_dir', cr['output_dir'])

        # Persist workflow settings.
        self.config['crispresso']['editing_tool'] = cr.get('editing_tool', 'Cas9')
        self.config['crispresso']['qw_center'] = cr.get('qw_center', '-3')
        self.config['crispresso']['qw_size'] = cr.get('qw_size', '1')
        self.config['crispresso']['n_processes'] = cr.get('n_processes', '')
        self.config['crispresso']['amplicon_name'] = cr.get('amplicon_name', 'Reference')
        self.config['crispresso']['guide_name'] = cr.get('guide_name', 'sgRNA')
        self.config['crispresso']['extra_args'] = self.pages[1].var_cr_extra.get().strip()
        self.config['adapter_removal']['threads'] = ar.get('ar_threads', '')
        self.config['adapter_removal']['extra_args'] = self.pages[0].var_ar_extra.get().strip()
        save_config(self.config_path, self.config)

        # Validate parameters.
        if step in (0, 1) and not ar['r1']:
            messagebox.showwarning('Missing Parameters', 'Please select the R1 FASTQ file.\n\nUse Browse or drag a file into the input field.')
            self._switch_page(0)
            return
        if step in (0, 1) and not ar['barcode_file']:
            messagebox.showwarning('Missing Parameters', 'Please select the barcode table file.\n\nBarcode table format: Sample name<TAB>barcode sequence')
            self._switch_page(0)
            return
        if step in (0, 2) and (not cr['amplicon_seq'] or not cr['guide_seq']):
            messagebox.showwarning('Missing Parameters', 'Please enter the amplicon sequence and sgRNA sequence.\n\nAmplicon: reference amplicon sequence containing only ATCG\nsgRNA: guide RNA sequence without PAM, usually 20 bp')
            self._switch_page(1)
            return
        if step in (0, 2) and cr.get('fastp_enabled'):
            self.log_panel.log('fastp preprocessing is enabled. CRISPResso2 will use clean FASTQ input.')

        # Start the workflow.
        self._running = True
        self._stop_flag = False
        self._has_errors = False
        self._run_token += 1
        self._monitored_results = set()
        self._set_buttons_state('disabled')
        self.lbl_status.configure(text='Running...', text_color=COLORS['primary'])
        self.progress.set(0)
        self.log_panel.clear()
        self._switch_page(2)

        params = {**ar, **cr, 'workdir': self.var_workdir.get()}
        threading.Thread(target=self._run_thread, args=(params, step), daemon=True).start()

    def _run_thread(self, params, step):
        """Background analysis thread."""
        start = time.time()
        summary = []
        processed_samples = []
        try:
            workdir = params.get('workdir', os.getcwd())
            output_dir = os.path.join(workdir, params.get('output_dir', './results').lstrip('./'))

            # Step 1: AdapterRemoval
            if step in (0, 1):
                self._current_step = 'adapter'
                self._log('=== Step 1: AdapterRemoval ===')
                self.root.after(0, lambda: self.lbl_status.configure(text='Step 1/2: AdapterRemoval...', text_color=COLORS['primary']))
                self.root.after(0, lambda: self.progress.set(0.1))
                run_adapterremoval(
                    params['r1'], params['r2'], params.get('barcode_file', ''),
                    params.get('basename', 'demux'), output_dir, params.get('ar_extra', ''),
                    callback=lambda msg, level='INFO': self._log(msg, level=level)
                )
                self.root.after(0, lambda: self.progress.set(0.4))
                self._log('Step 1 completed.')

                # Refresh sample list.
                samples = self._find_merged_samples(output_dir, params.get('basename', 'demux'))
                if samples:
                    self.root.after(0, lambda s=samples, o=output_dir: self._update_sample_table(s, o))
                    self._log(f'Found {len(samples)} samples.')

            # Step 2: CRISPResso2
            if step in (0, 2):
                if self._stop_flag:
                    return

                self._current_step = 'crispresso'
                stage_title = 'fastp + CRISPResso2' if params.get('fastp_enabled') else 'CRISPResso2'
                self._log(f'=== Step 2: {stage_title} ===')
                self.root.after(0, lambda: self.lbl_status.configure(text=f'Step 2/2: {stage_title}...', text_color=COLORS['primary']))
                self.root.after(0, lambda: self.progress.set(0.5))

                # Find samples.
                if not self._samples:
                    samples = self._find_merged_samples(output_dir, params.get('basename', 'demux'))
                    if samples:
                        self.root.after(0, lambda s=samples, o=output_dir: self._update_sample_table(s, o))
                        time.sleep(0.5)

                # Get selected samples.
                selected = self._get_selected_samples()
                if not selected:
                    self._log('No samples selected.')
                    return

                total = len(selected)
                for i, name in enumerate(selected):
                    if self._stop_flag:
                        self._log('Stopped.')
                        return

                    # Estimate remaining time.
                    elapsed = time.time() - start
                    eta = elapsed / (i + 1) * (total - i - 1) if i > 0 else 0
                    self._log(f'[{i+1}/{total}] {name} (ETA: {eta:.0f}s)')
                    self.root.after(0, lambda n=name: self._update_sample_status(n, 'Processing...'))
                    progress_value = 0.5 + 0.4 * (i + 1) / total

                    # Locate input file.
                    r1 = os.path.join(output_dir, f'{params.get("basename", "demux")}.{name}.merged.fastq')
                    if not os.path.exists(r1):
                        self._log(f'  Skipped: {name}')
                        self.root.after(0, lambda n=name: self._update_sample_status(n, 'Skipped'))
                        continue

                    crispresso_input = r1
                    if params.get('fastp_enabled'):
                        self._current_step = 'fastp'
                        clean_dir = os.path.join(output_dir, 'fastp_clean')
                        report_dir = os.path.join(output_dir, 'fastp_reports')
                        clean_fastq = os.path.join(clean_dir, f'{name}.clean.fastq')
                        try:
                            crispresso_input = run_fastp_single(
                                r1, clean_fastq, report_dir, name,
                                options=params.get('fastp_options', {}),
                                callback=lambda msg, level='INFO': self._log(msg, level=level)
                            )
                        except InterruptedError:
                            self._log('Interrupted by user.')
                            self.root.after(0, lambda n=name: self._update_sample_status(n, 'Interrupted'))
                            return
                        self._current_step = 'crispresso'

                    # Run CRISPResso2.
                    try:
                        self.root.after(
                            0,
                            lambda n=name, p=progress_value, token=self._run_token:
                                self._start_result_monitor(output_dir, n, p, token)
                        )
                        run_crispresso(
                            crispresso_input, params['amplicon_seq'], params['guide_seq'],
                            output_dir, name, params.get('cr_extra', ''),
                            amplicon_name=params.get('amplicon_name', 'Reference'),
                            guide_name=params.get('guide_name', 'sgRNA'),
                            callback=lambda msg, level='INFO': self._tool_callback(msg, level=level)
                        )
                        # Update results.
                        result = parse_quantification(output_dir, name)
                        if result:
                            processed_samples.append(name)
                            self.root.after(0, lambda n=name, r=result, o=output_dir: self._record_sample_result(n, r, o))
                        else:
                            self.root.after(0, lambda n=name: self._update_sample_status(n, 'Completed'))
                    except InterruptedError:
                        result = parse_quantification(output_dir, name)
                        if result:
                            processed_samples.append(name)
                            self._log(f'Results detected for {name}; syncing table and plots.')
                            self.root.after(0, lambda n=name, r=result, o=output_dir: self._record_sample_result(n, r, o))
                            self.root.after(0, lambda p=0.5 + 0.4 * (i + 1) / total: self.progress.set(p))
                            break
                        self._log('Interrupted by user.')
                        self.root.after(0, lambda n=name: self._update_sample_status(n, 'Interrupted'))
                        return
                    except Exception as e:
                        user_msg = get_user_friendly_message(e)
                        self._log(f'  Error: {name} - {user_msg}', level='ERROR')
                        self.root.after(0, lambda n=name: self._update_sample_status(n, 'Failed'))
                        self._has_errors = True

                    self.root.after(0, lambda p=progress_value: self.progress.set(p))

            if self._stop_flag and not processed_samples:
                return

            # Generate summary CSV.
            self._log('Generating summary report...')
            try:
                selected = processed_samples or self._get_selected_samples()
                if selected:
                    csv_path = os.path.join(output_dir, 'crispr_summary.csv')
                    summary = generate_summary(output_dir, selected, csv_path)
                    if summary:
                        self.root.after(0, lambda: self.result_panel.load_summary(summary))
                        self._log(f'Summary report: {csv_path}')
            except Exception as e:
                self._log(f'Failed to generate summary report: {e}')

            self._log(f'=== Completed (elapsed {time.time() - start:.0f}s) ===')
            # Refresh visualization.
            if summary:
                self.root.after(0, lambda: self.result_panel.load_summary(summary))

        except InterruptedError:
            self._log('Workflow interrupted by user.')
        except CRISPRError as e:
            log_msg = format_error_for_log(e)
            self._log(f'✗ {log_msg}')
            self.root.after(0, lambda: messagebox.showerror('Error', get_user_friendly_message(e)))
            self._has_errors = True
        except FileNotFoundError as e:
            self._log(f'✗ File error: {e}')
            self._has_errors = True
        except PermissionError as e:
            self._log(f'✗ Permission error: {e}')
            self._has_errors = True
        except Exception as e:
            self._log(f'✗ ERROR: {get_user_friendly_message(e)}')
            self._has_errors = True
        finally:
            self._current_step = None
            self.root.after(0, self._run_done)

    def _find_merged_samples(self, output_dir, basename):
        """Find merged sample FASTQ files."""
        samples = []
        if not os.path.exists(output_dir):
            return samples
        for f in os.listdir(output_dir):
            if f.startswith(basename + '.') and f.endswith('.merged.fastq'):
                name = f[len(basename) + 1:].replace('.merged.fastq', '')
                if name and name != 'unidentified':
                    samples.append(name)
        return sorted(samples)

    def _run_done(self):
        """Handle workflow completion."""
        self._running = False
        self._set_buttons_state('normal')
        if getattr(self, '_has_errors', False):
            self.lbl_status.configure(text='Errors detected', text_color=COLORS['danger'])
            self.progress.set(1)
        else:
            self.progress.set(1)
            self.lbl_status.configure(text='Completed', text_color=COLORS['success'])

    def _stop(self):
        """Stop the workflow."""
        self._stop_flag = True
        self._running = False
        self._log('Terminating process...')
        self.lbl_status.configure(text='Stopping...', text_color=COLORS['danger'])

        try:
            if self._current_step == 'adapter':
                terminate_adapter()
            elif self._current_step == 'fastp':
                terminate_fastp()
            elif self._current_step == 'crispresso':
                terminate_crispresso()
            else:
                terminate_adapter()
                terminate_fastp()
                terminate_crispresso()
        except Exception as e:
            log.warning('Error while terminating process: %s', e)

        self.lbl_status.configure(text='Stopped', text_color=COLORS['danger'])

    def _log(self, msg, level='INFO'):
        """Add a log message."""
        self.log_panel.log(msg, level=level)

    def _tool_callback(self, msg, level='INFO'):
        """Log external tool output and mirror long-running status in the status bar."""
        self._log(msg, level=level)
        status_markers = ('running', 'status -', 'final completion log', 'completed (')
        if any(marker in msg.lower() for marker in status_markers):
            self.root.after(0, lambda m=msg: self.lbl_status.configure(text=m, text_color=COLORS['primary']))

    def _toggle_theme(self):
        """Toggle light/dark theme."""
        new_mode = toggle_theme()
        self._log(f'Switched to {"dark" if new_mode == "dark" else "light"} mode.')

    def _on_close(self):
        """Close the window."""
        if self._running:
            if not messagebox.askyesno('Confirm', 'The workflow is still running. Exit anyway?'):
                return
            self._stop()
        self._save_current_config()
        self.root.destroy()

    def _save_current_config(self):
        """Save the current configuration."""
        try:
            ar = self.pages[0].get_params()
            cr = self.pages[1].get_params()
            self.config['adapter_removal'].update({
                'file1': ar.get('r1', ''),
                'file2': ar.get('r2', ''),
                'barcode_file': ar.get('barcode_file', ''),
                'basename': ar.get('basename', 'demux'),
                'threads': ar.get('ar_threads', ''),
                'extra_args': self.pages[0].var_ar_extra.get().strip(),
            })
            self.config['crispresso'].update({
                'amplicon_seq': cr.get('amplicon_seq', ''),
                'amplicon_name': cr.get('amplicon_name', 'Reference'),
                'guide_seq': cr.get('guide_seq', ''),
                'guide_name': cr.get('guide_name', 'sgRNA'),
                'editing_tool': cr.get('editing_tool', 'Cas9'),
                'output_dir': cr.get('output_dir', './results'),
                'qw_center': cr.get('qw_center', '-3'),
                'qw_size': cr.get('qw_size', '1'),
                'n_processes': cr.get('n_processes', ''),
                'extra_args': self.pages[1].var_cr_extra.get().strip(),
            })
            self.config['workdir'] = self.var_workdir.get()
            self.config['conda_path'] = self.var_conda.get()
            self.config['env_name'] = self.var_env_name.get()
            save_config(self.config_path, self.config)
            self._log('Configuration saved.')
        except Exception as e:
            self._log(f'Failed to save configuration: {e}')

    def run(self):
        """Start the application."""
        self.root.mainloop()
