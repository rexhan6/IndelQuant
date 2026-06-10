"""
参数面板模块 v0.1

v0.1 将界面从“工具页面堆叠”调整为“工作流参数分组”：
- AdapterRemoval: 输入、barcode 拆分、质量过滤、合并性能
- CRISPResso2: 核心分析、编辑模型、过滤、报告输出
- fastp: 可选预处理/QC，默认关闭以保持兼容
"""

import customtkinter as ctk
from tkinter import filedialog

from gui.styles import (
    COLORS, FONT_TITLE, FONT_SUBTITLE, FONT_NORMAL, FONT_COMBO,
    FONT_CHECK, FONT_HINT, FONT_INPUT
)
from utils.system import get_cpu_count

CPU_COUNT = get_cpu_count()


class DropEntry(ctk.CTkFrame):
    """Entry widget with optional drag-and-drop support."""

    def __init__(self, master, textvariable=None, width=400, **kwargs):
        super().__init__(master, fg_color='transparent')
        self._var = textvariable or ctk.StringVar()
        self._entry = ctk.CTkEntry(
            self, textvariable=self._var, width=width,
            font=FONT_INPUT(), corner_radius=8, height=34
        )
        self._entry.pack(side='left', fill='x', expand=True)

        try:
            import windnd

            def on_drop(files):
                if files:
                    f = files[0]
                    if isinstance(f, bytes):
                        filepath = ''
                        for enc in ['utf-8', 'gbk', 'gb2312', 'cp936']:
                            try:
                                filepath = f.decode(enc)
                                break
                            except UnicodeDecodeError:
                                continue
                    else:
                        filepath = str(f)
                    if filepath:
                        self._var.set(filepath)

            windnd.hook_dropfiles(self._entry, func=on_drop)
        except Exception:
            pass


class Section(ctk.CTkFrame):
    """Collapsible parameter section."""

    def __init__(self, parent, title, subtitle='', **kwargs):
        super().__init__(parent, fg_color=COLORS['card'], corner_radius=8, **kwargs)
        self.pack(fill='x', padx=14, pady=6)
        self._show = True
        self._title = title

        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill='x', padx=12, pady=(10, 4))
        self._btn = ctk.CTkButton(
            header, text=f'▼  {title}', anchor='w',
            font=FONT_SUBTITLE(), fg_color='transparent',
            text_color=COLORS['text'], hover_color=COLORS['bg'],
            height=28, command=self.toggle
        )
        self._btn.pack(side='left', fill='x', expand=True)
        if subtitle:
            ctk.CTkLabel(
                header, text=subtitle, font=FONT_HINT(),
                text_color=COLORS['text_secondary']
            ).pack(side='right', padx=8)
        ctk.CTkFrame(self, height=1, fg_color=COLORS['border']).pack(fill='x', padx=12)

        self._body = ctk.CTkFrame(self, fg_color='transparent')
        self._body.pack(fill='x', padx=8, pady=(4, 10))

    def toggle(self):
        if self._show:
            self._body.pack_forget()
            self._btn.configure(text=f'►  {self._title}')
            self._show = False
        else:
            self._body.pack(fill='x', padx=8, pady=(4, 10))
            self._btn.configure(text=f'▼  {self._title}')
            self._show = True

    @property
    def body(self):
        return self._body


def _row(parent, label, tooltip=''):
    f = ctk.CTkFrame(parent, fg_color='transparent')
    f.pack(fill='x', padx=6, pady=3)
    ctk.CTkLabel(
        f, text=label, width=170, anchor='e',
        font=FONT_NORMAL(), text_color=COLORS['text']
    ).pack(side='left', padx=(8, 8))
    wf = ctk.CTkFrame(f, fg_color='transparent')
    wf.pack(side='left', fill='x', expand=True)
    if tooltip:
        ctk.CTkLabel(
            f, text=tooltip, font=FONT_HINT(), anchor='w',
            text_color=COLORS['text_secondary'], wraplength=250
        ).pack(side='right', padx=(8, 8))
    return wf


def _entry(parent, label, var, tooltip='', width=400, browse=False,
           browse_ft=None, browse_dir=False):
    wf = _row(parent, label, tooltip)
    e = DropEntry(wf, textvariable=var, width=width)
    e.pack(side='left', fill='x', expand=True)

    if browse or browse_dir:
        def do_browse():
            if browse_dir:
                p = filedialog.askdirectory()
            else:
                p = filedialog.askopenfilename(filetypes=browse_ft or [('All', '*.*')])
            if p:
                var.set(p)
        ctk.CTkButton(
            wf, text='Browse', width=64, height=34, corner_radius=8,
            font=FONT_NORMAL(), command=do_browse
        ).pack(side='left', padx=(6, 0))
    return wf


def _combo(parent, label, var, values, tooltip='', width=160):
    wf = _row(parent, label, tooltip)
    cb = ctk.CTkComboBox(
        wf, variable=var, values=values, width=width,
        font=FONT_COMBO(), corner_radius=8, height=34
    )
    cb.pack(side='left')
    return wf


def _check(parent, text, var):
    ctk.CTkCheckBox(
        parent, text=f'  {text}', variable=var,
        font=FONT_CHECK(), text_color=COLORS['text']
    ).pack(anchor='w', padx=22, pady=3)


def _append_value(parts, flag, value):
    value = str(value).strip()
    if value:
        parts.extend([flag, value])


def _append_flag(parts, flag, enabled):
    if enabled:
        parts.append(flag)


FASTQ_FT = [('FASTQ', '*.fastq *.fq *.fastq.gz *.fq.gz'), ('All', '*.*')]
TXT_FT = [('Text/TSV/CSV', '*.txt *.tsv *.csv'), ('All', '*.*')]
FASTA_FT = [('FASTA', '*.fa *.fasta *.fna'), ('All', '*.*')]


class AdapterRemovalPanel(ctk.CTkFrame):
    """AdapterRemoval v3 parameter panel."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS['bg'], corner_radius=0, **kwargs)
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(
            self, text='Workflow Setup / AdapterRemoval v3',
            font=FONT_TITLE(), text_color=COLORS['text']
        ).pack(anchor='w', padx=20, pady=(16, 8))
        scroll = ctk.CTkScrollableFrame(self, fg_color='transparent')
        scroll.pack(fill='both', expand=True)

        sec = Section(scroll, 'Input FASTQ Files', 'Drag-and-drop supported')
        self.var_r1 = ctk.StringVar()
        _entry(sec.body, 'R1 FASTQ:', self.var_r1, 'Read 1; .gz supported', browse=True, browse_ft=FASTQ_FT)
        self.var_r2 = ctk.StringVar()
        _entry(sec.body, 'R2 FASTQ:', self.var_r2, 'Read 2; leave blank for single-end data', browse=True, browse_ft=FASTQ_FT)

        sec = Section(scroll, 'Barcode Demultiplexing', 'Compatible with the legacy workflow')
        self.var_barcode_file = ctk.StringVar()
        _entry(sec.body, 'Barcode table:', self.var_barcode_file, '2/3 columns: sample barcode1 [barcode2]', browse=True, browse_ft=TXT_FT)
        self.var_basename = ctk.StringVar(value='demux')
        _entry(sec.body, 'Output prefix:', self.var_basename, 'Final sample file prefix', width=160)
        self.var_barcode_mm = ctk.StringVar(value='0')
        _combo(sec.body, 'Barcode mismatches:', self.var_barcode_mm, ['0', '1', '2', '3'], 'AdapterRemoval --barcode-mm')
        self.var_barcode_orientation = ctk.StringVar(value='unspecified')
        _combo(sec.body, 'Barcode orientation:', self.var_barcode_orientation,
               ['unspecified', 'forward', 'reverse', 'explicit'],
               'Use forward/reverse/explicit for known-orientation designs')
        self.var_multiple_barcodes = ctk.BooleanVar(value=False)
        _check(sec.body, 'Allow multiple barcodes per sample', self.var_multiple_barcodes)
        # The current workflow demultiplexes first and merges per sample later;
        # AdapterRemoval only accepts --normalize-orientation in combined
        # demultiplex+merge mode, so this is intentionally not exposed.
        self.var_normalize_orientation = ctk.BooleanVar(value=False)

        sec = Section(scroll, 'Quality Filtering and Trimming', 'Conservative defaults')
        self.var_min_length = ctk.StringVar(value='15')
        _entry(sec.body, 'Minimum read length:', self.var_min_length, 'AdapterRemoval --min-length', width=100)
        self.var_max_ns = ctk.StringVar()
        _entry(sec.body, 'Maximum Ns:', self.var_max_ns, 'Leave blank for no limit', width=100)
        self.var_min_mean_quality = ctk.StringVar()
        _entry(sec.body, 'Minimum mean quality:', self.var_min_mean_quality, 'Leave blank for no limit', width=100)
        self.var_trim_windows = ctk.StringVar()
        _entry(sec.body, 'Trim window size:', self.var_trim_windows, '--trim-windows; leave blank to disable', width=100)
        self.var_trim_min_quality = ctk.StringVar()
        _entry(sec.body, 'Trim quality threshold:', self.var_trim_min_quality, '--trim-min-quality', width=100)

        sec = Section(scroll, 'Performance and Logging')
        self.var_threads = ctk.StringVar(value=str(CPU_COUNT))
        _combo(sec.body, 'Threads:', self.var_threads, ['1', '2', '4', '8', '16', '32'], f'CPU: {CPU_COUNT}')
        self.var_simd = ctk.StringVar(value='auto')
        _combo(sec.body, 'SIMD:', self.var_simd, ['auto', 'none', 'SSE2', 'AVX2', 'AVX512', 'NEON'], 'Usually keep auto')
        self.var_log_progress = ctk.StringVar(value='log')
        _combo(sec.body, 'Progress output:', self.var_log_progress, ['auto', 'log', 'spin', 'never'])

        sec = Section(scroll, 'AdapterRemoval Advanced Arguments')
        self.var_ar_extra = ctk.StringVar()
        _entry(sec.body, 'Extra arguments:', self.var_ar_extra, 'Appended to demultiplexing commands; quoted paths supported', width=520)

    def get_params(self):
        extra = []
        _append_value(extra, '--threads', self.var_threads.get())
        if self.var_simd.get() != 'auto':
            _append_value(extra, '--simd', self.var_simd.get())
        if self.var_log_progress.get():
            _append_value(extra, '--log-progress', self.var_log_progress.get())
        if self.var_barcode_mm.get():
            _append_value(extra, '--barcode-mm', self.var_barcode_mm.get())
        if self.var_barcode_orientation.get() != 'unspecified':
            _append_value(extra, '--barcode-orientation', self.var_barcode_orientation.get())
        _append_flag(extra, '--multiple-barcodes', self.var_multiple_barcodes.get())
        # --normalize-orientation is only valid in AdapterRemoval's combined
        # demultiplex+merge mode. This GUI runs demultiplexing and merging as
        # separate steps, so appending it here makes the split command invalid.
        _append_value(extra, '--min-length', self.var_min_length.get())
        _append_value(extra, '--max-ns', self.var_max_ns.get())
        _append_value(extra, '--min-mean-quality', self.var_min_mean_quality.get())
        _append_value(extra, '--trim-windows', self.var_trim_windows.get())
        _append_value(extra, '--trim-min-quality', self.var_trim_min_quality.get())
        user = self.var_ar_extra.get().strip()
        if user:
            extra.append(user)
        return {
            'r1': self.var_r1.get().strip(),
            'r2': self.var_r2.get().strip(),
            'barcode_file': self.var_barcode_file.get().strip(),
            'basename': self.var_basename.get().strip() or 'demux',
            'ar_extra': ' '.join(extra),
            'ar_threads': self.var_threads.get().strip(),
        }

    def set_params(self, cfg):
        ar = cfg.get('adapter_removal', {})
        self.var_r1.set(ar.get('file1', ''))
        self.var_r2.set(ar.get('file2', ''))
        self.var_barcode_file.set(ar.get('barcode_file', ''))
        self.var_basename.set(ar.get('basename', 'demux'))
        self.var_threads.set(ar.get('threads', str(CPU_COUNT)) or str(CPU_COUNT))
        self.var_ar_extra.set(ar.get('extra_args', ''))

    def set_history(self, history):
        for key, var in [
            ('r1', self.var_r1), ('r2', self.var_r2), ('barcode_file', self.var_barcode_file)
        ]:
            if history.get(key):
                var.set(history[key][0])


class CRISPRessoPanel(ctk.CTkFrame):
    """CRISPResso2 + fastp parameter panel."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS['bg'], corner_radius=0, **kwargs)
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(
            self, text='Analysis Setup / CRISPResso2 + fastp',
            font=FONT_TITLE(), text_color=COLORS['text']
        ).pack(anchor='w', padx=20, pady=(16, 8))
        scroll = ctk.CTkScrollableFrame(self, fg_color='transparent')
        scroll.pack(fill='both', expand=True)

        sec = Section(scroll, 'CRISPResso2 Core Input', 'Comma-separated amplicons/guides supported')
        self.var_amplicon = ctk.StringVar()
        _entry(sec.body, 'Amplicon sequence:', self.var_amplicon, 'Reference amplicon; use commas for multiple sequences', width=520)
        self.var_amplicon_name = ctk.StringVar(value='Reference')
        _entry(sec.body, 'Amplicon name:', self.var_amplicon_name, 'Matches amplicon order', width=260)
        self.var_guide = ctk.StringVar()
        _entry(sec.body, 'sgRNA sequence:', self.var_guide, 'Guide sequence without PAM; use commas for multiple guides', width=520)
        self.var_guide_name = ctk.StringVar(value='sgRNA')
        _entry(sec.body, 'sgRNA name:', self.var_guide_name, 'Matches sgRNA order', width=260)
        self.var_output = ctk.StringVar(value='./results')
        _entry(sec.body, 'Output directory:', self.var_output, 'Relative to working directory or absolute path', width=380, browse_dir=True)

        sec = Section(scroll, 'Editing Model Presets')
        self.var_editing_tool = ctk.StringVar(value='Cas9')
        _combo(sec.body, 'Editing tool:', self.var_editing_tool,
               ['Cas9', 'Cpf1/Cas12a', 'Base editor', 'Prime editor', 'HDR', 'Custom'],
               'Automatically sets the quantification window')
        self.var_editing_tool.trace_add('write', self._on_tool_change)
        self.var_qw_center = ctk.StringVar(value='-3')
        _combo(sec.body, 'Window center:', self.var_qw_center, ['-15', '-10', '-3', '0', '+1', '+5'])
        self.var_qw_size = ctk.StringVar(value='1')
        _combo(sec.body, 'Window size:', self.var_qw_size, ['1', '2', '3', '5', '10', '15', '20'])
        self.var_hdr_amplicon = ctk.StringVar()
        _entry(sec.body, 'HDR amplicon:', self.var_hdr_amplicon, 'HDR/edited reference sequence; optional', width=520)

        sec = Section(scroll, 'Base / Prime Editing')
        self.var_base_editor_output = ctk.BooleanVar(value=False)
        _check(sec.body, 'Enable base editor output', self.var_base_editor_output)
        self.var_conversion_from = ctk.StringVar(value='C')
        _combo(sec.body, 'Conversion from:', self.var_conversion_from, ['A', 'C', 'G', 'T'])
        self.var_conversion_to = ctk.StringVar(value='T')
        _combo(sec.body, 'Conversion to:', self.var_conversion_to, ['A', 'C', 'G', 'T'])
        self.var_pegrna_spacer = ctk.StringVar()
        _entry(sec.body, 'pegRNA spacer:', self.var_pegrna_spacer, '', width=420)
        self.var_pegrna_extension = ctk.StringVar()
        _entry(sec.body, 'pegRNA extension:', self.var_pegrna_extension, '', width=420)
        self.var_nicking_guide = ctk.StringVar()
        _entry(sec.body, 'nicking guide:', self.var_nicking_guide, 'Optional', width=420)

        sec = Section(scroll, 'Filtering, Alignment, and Quantification')
        self.var_min_average_read_quality = ctk.StringVar()
        _entry(sec.body, 'Minimum average read quality:', self.var_min_average_read_quality, '--min_average_read_quality', width=100)
        self.var_min_bp_quality = ctk.StringVar()
        _entry(sec.body, 'Minimum base quality:', self.var_min_bp_quality, '--min_bp_quality_or_N', width=100)
        self.var_ignore_substitutions = ctk.BooleanVar(value=True)
        _check(sec.body, 'Ignore substitutions (commonly used for indel efficiency)', self.var_ignore_substitutions)
        self.var_ignore_insertions = ctk.BooleanVar(value=False)
        _check(sec.body, 'Ignore insertions', self.var_ignore_insertions)
        self.var_ignore_deletions = ctk.BooleanVar(value=False)
        _check(sec.body, 'Ignore deletions', self.var_ignore_deletions)
        self.var_expand_ambiguous = ctk.BooleanVar(value=False)
        _check(sec.body, 'Expand ambiguous alignments for multiple references', self.var_expand_ambiguous)

        sec = Section(scroll, 'Output and Reports')
        self.var_n_processes = ctk.StringVar(value=str(CPU_COUNT))
        _combo(sec.body, 'Processes:', self.var_n_processes, ['1', '2', '4', '8', '16', '32'], f'CPU: {CPU_COUNT}')
        self.var_min_freq_alleles = ctk.StringVar(value='0.01')
        _entry(sec.body, 'Minimum allele frequency:', self.var_min_freq_alleles, '', width=100)
        self.var_plot_histogram_outliers = ctk.BooleanVar(value=True)
        _check(sec.body, 'Exclude outliers in histogram plots', self.var_plot_histogram_outliers)
        self.var_zip_output = ctk.BooleanVar(value=False)
        _check(sec.body, 'Zip CRISPResso output', self.var_zip_output)
        self.var_no_rerun = ctk.BooleanVar(value=False)
        _check(sec.body, 'Skip completed analyses', self.var_no_rerun)
        self.var_suppress_report = ctk.BooleanVar(value=False)
        _check(sec.body, 'Suppress HTML report (faster)', self.var_suppress_report)

        sec = Section(scroll, 'fastp Preprocessing / QC', 'Disabled by default')
        self.var_fastp_enabled = ctk.BooleanVar(value=False)
        _check(sec.body, 'Run fastp before CRISPResso2', self.var_fastp_enabled)
        self.var_fastp_thread = ctk.StringVar(value='4')
        _combo(sec.body, 'fastp threads:', self.var_fastp_thread, ['1', '2', '4', '8', '16'])
        self.var_fastp_length = ctk.StringVar(value='15')
        _entry(sec.body, 'Minimum length:', self.var_fastp_length, '-l / --length_required', width=100)
        self.var_fastp_q = ctk.StringVar(value='15')
        _entry(sec.body, 'Qualified base quality:', self.var_fastp_q, '-q / --qualified_quality_phred', width=100)
        self.var_fastp_u = ctk.StringVar(value='40')
        _entry(sec.body, 'Low-quality base percentage:', self.var_fastp_u, '-u / --unqualified_percent_limit', width=100)
        self.var_fastp_n = ctk.StringVar(value='5')
        _entry(sec.body, 'Maximum Ns:', self.var_fastp_n, '-n / --n_base_limit', width=100)
        self.var_fastp_average = ctk.StringVar()
        _entry(sec.body, 'Average quality:', self.var_fastp_average, '-e / --average_qual; leave blank to disable', width=100)
        self.var_fastp_cut_front = ctk.BooleanVar(value=False)
        _check(sec.body, "Enable 5' sliding-window quality trimming", self.var_fastp_cut_front)
        self.var_fastp_cut_tail = ctk.BooleanVar(value=False)
        _check(sec.body, "Enable 3' sliding-window quality trimming", self.var_fastp_cut_tail)
        self.var_fastp_cut_right = ctk.BooleanVar(value=False)
        _check(sec.body, 'Trim after a low-quality window', self.var_fastp_cut_right)
        self.var_fastp_poly_g = ctk.BooleanVar(value=False)
        _check(sec.body, 'Force polyG trimming', self.var_fastp_poly_g)
        self.var_fastp_poly_x = ctk.BooleanVar(value=False)
        _check(sec.body, 'Enable polyX trimming', self.var_fastp_poly_x)
        self.var_fastp_no_dup = ctk.BooleanVar(value=True)
        _check(sec.body, 'Skip duplication evaluation to reduce runtime and memory use', self.var_fastp_no_dup)

        sec = Section(scroll, 'CRISPResso2 Advanced Arguments')
        self.var_cr_extra = ctk.StringVar()
        _entry(sec.body, 'Extra arguments:', self.var_cr_extra, 'Appended directly to the CRISPResso command; quoted paths supported', width=540)

        self._on_tool_change()

    def _on_tool_change(self, *args):
        tool = self.var_editing_tool.get()
        presets = {
            'Cas9': ('-3', '1'),
            'Cpf1/Cas12a': ('+1', '1'),
            'Base editor': ('-10', '10'),
            'Prime editor': ('-3', '1'),
            'HDR': ('-3', '1'),
        }
        if tool in presets:
            self.var_qw_center.set(presets[tool][0])
            self.var_qw_size.set(presets[tool][1])
        self.var_base_editor_output.set(tool == 'Base editor')

    def get_params(self):
        extra = []
        _append_value(extra, '-wc', self.var_qw_center.get())
        _append_value(extra, '-w', self.var_qw_size.get())
        _append_value(extra, '-e', self.var_hdr_amplicon.get())
        _append_value(extra, '-p', self.var_n_processes.get())
        _append_value(extra, '--min_average_read_quality', self.var_min_average_read_quality.get())
        _append_value(extra, '--min_bp_quality_or_N', self.var_min_bp_quality.get())
        _append_value(extra, '--min_frequency_alleles_around_cut_to_plot', self.var_min_freq_alleles.get())
        _append_flag(extra, '--ignore_substitutions', self.var_ignore_substitutions.get())
        _append_flag(extra, '--ignore_insertions', self.var_ignore_insertions.get())
        _append_flag(extra, '--ignore_deletions', self.var_ignore_deletions.get())
        _append_flag(extra, '--expand_ambiguous_alignments', self.var_expand_ambiguous.get())
        _append_flag(extra, '--plot_histogram_outliers', self.var_plot_histogram_outliers.get())
        _append_flag(extra, '--zip_output', self.var_zip_output.get())
        _append_flag(extra, '--no_rerun', self.var_no_rerun.get())
        _append_flag(extra, '--suppress_report', self.var_suppress_report.get())

        if self.var_base_editor_output.get():
            _append_flag(extra, '--base_editor_output', True)
            _append_value(extra, '--conversion_nuc_from', self.var_conversion_from.get())
            _append_value(extra, '--conversion_nuc_to', self.var_conversion_to.get())

        _append_value(extra, '--prime_editing_pegRNA_spacer_seq', self.var_pegrna_spacer.get())
        _append_value(extra, '--prime_editing_pegRNA_extension_seq', self.var_pegrna_extension.get())
        _append_value(extra, '--prime_editing_nicking_guide_seq', self.var_nicking_guide.get())

        user = self.var_cr_extra.get().strip()
        if user:
            extra.append(user)

        return {
            'amplicon_seq': self.var_amplicon.get().strip(),
            'amplicon_name': self.var_amplicon_name.get().strip() or 'Reference',
            'guide_seq': self.var_guide.get().strip(),
            'guide_name': self.var_guide_name.get().strip() or 'sgRNA',
            'output_dir': self.var_output.get().strip(),
            'editing_tool': self.var_editing_tool.get(),
            'qw_center': self.var_qw_center.get(),
            'qw_size': self.var_qw_size.get(),
            'n_processes': self.var_n_processes.get(),
            'cr_extra': ' '.join(extra),
            'fastp_enabled': self.var_fastp_enabled.get(),
            'fastp_options': {
                'thread': self.var_fastp_thread.get(),
                'length_required': self.var_fastp_length.get(),
                'qualified_quality_phred': self.var_fastp_q.get(),
                'unqualified_percent_limit': self.var_fastp_u.get(),
                'n_base_limit': self.var_fastp_n.get(),
                'average_qual': self.var_fastp_average.get(),
                'cut_front': self.var_fastp_cut_front.get(),
                'cut_tail': self.var_fastp_cut_tail.get(),
                'cut_right': self.var_fastp_cut_right.get(),
                'cut_window_size': 4,
                'cut_mean_quality': 20,
                'trim_poly_g': self.var_fastp_poly_g.get(),
                'trim_poly_x': self.var_fastp_poly_x.get(),
                'dont_eval_duplication': self.var_fastp_no_dup.get(),
            },
        }

    def set_params(self, cfg):
        cr = cfg.get('crispresso', {})
        self.var_amplicon.set(cr.get('amplicon_seq', ''))
        self.var_amplicon_name.set(cr.get('amplicon_name', 'Reference'))
        self.var_guide.set(cr.get('guide_seq', ''))
        self.var_guide_name.set(cr.get('guide_name', 'sgRNA'))
        self.var_output.set(cr.get('output_dir', './results'))
        self.var_editing_tool.set(cr.get('editing_tool', 'Cas9'))
        self.var_qw_center.set(cr.get('qw_center', '-3'))
        self.var_qw_size.set(cr.get('qw_size', '1'))
        self.var_n_processes.set(cr.get('n_processes', str(CPU_COUNT)) or str(CPU_COUNT))
        self.var_cr_extra.set(cr.get('extra_args', ''))

    def set_history(self, history):
        for key, var in [
            ('amplicon_seq', self.var_amplicon),
            ('guide_seq', self.var_guide),
            ('output_dir', self.var_output),
        ]:
            if history.get(key):
                var.set(history[key][0])
