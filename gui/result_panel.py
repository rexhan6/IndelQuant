"""
结果面板模块

功能：
- 柱状图：编辑效率对比
- 饼图：平均编辑率
- 分布图：编辑效率分布
- 箱线图：数据离散程度
"""

import customtkinter as ctk
from gui.styles import COLORS
import numpy as np

try:
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


class ResultPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color='transparent', **kwargs)
        self._data = []
        self._build_ui()

    def _build_ui(self):
        if HAS_MPL:
            # 2x2 布局：柱状图、饼图、分布图、箱线图
            self.fig = Figure(figsize=(14, 8), dpi=100, facecolor='white')
            self.ax_bar = self.fig.add_subplot(221)
            self.ax_pie = self.fig.add_subplot(222)
            self.ax_dist = self.fig.add_subplot(223)
            self.ax_box = self.fig.add_subplot(224)
            self.canvas = FigureCanvasTkAgg(self.fig, master=self)
            self.canvas.get_tk_widget().pack(fill='both', expand=True, padx=5, pady=5)
            self.fig.tight_layout(pad=3)

    def load_summary(self, summary):
        self._data = summary
        self._update_charts()

    def _update_charts(self):
        if not HAS_MPL or not self._data:
            return

        # 清空所有图表
        self.ax_bar.clear()
        self.ax_pie.clear()
        self.ax_dist.clear()
        self.ax_box.clear()

        # 提取数据
        samples = []
        modified_pcts = []
        for row in self._data:
            samples.append(row.get('Sample', ''))
            try:
                modified_pcts.append(float(str(row.get('Modified%', '0')).replace('%', '')))
            except:
                modified_pcts.append(0)

        colors = [COLORS['danger'] if v > 50 else COLORS['warning'] if v > 10 else COLORS['success'] for v in modified_pcts]

        # 1. 柱状图 - 编辑效率对比
        bars = self.ax_bar.bar(range(len(samples)), modified_pcts, color=colors, edgecolor='white', width=0.7)
        self.ax_bar.set_xticks(range(len(samples)))
        self.ax_bar.set_xticklabels(samples, rotation=45, ha='right', fontsize=10)
        self.ax_bar.set_ylabel('Editing %', fontsize=12)
        self.ax_bar.set_title('Editing Efficiency', fontsize=14, fontweight='bold')
        self.ax_bar.set_ylim(0, 105)
        for bar, val in zip(bars, modified_pcts):
            if val > 0:
                self.ax_bar.text(bar.get_x() + bar.get_width() / 2, val + 1,
                                 f'{val:.1f}%', ha='center', va='bottom', fontsize=9)

        # 2. 饼图 - 平均编辑率
        if modified_pcts:
            avg = sum(modified_pcts) / len(modified_pcts)
            self.ax_pie.pie(
                [avg, 100 - avg],
                labels=['Modified', 'Unmodified'],
                colors=[COLORS['danger'], COLORS['success']],
                autopct='%1.1f%%',
                startangle=90,
                textprops={'fontsize': 12},
                wedgeprops={'edgecolor': 'white', 'linewidth': 2}
            )
            self.ax_pie.set_title('Average Rate', fontsize=14, fontweight='bold')

        # 3. 分布图 - 编辑效率分布
        if modified_pcts:
            self.ax_dist.hist(modified_pcts, bins=10, color=COLORS['primary'],
                            edgecolor='white', alpha=0.8)
            self.ax_dist.set_xlabel('Editing %', fontsize=12)
            self.ax_dist.set_ylabel('Count', fontsize=12)
            self.ax_dist.set_title('Distribution', fontsize=14, fontweight='bold')
            self.ax_dist.axvline(sum(modified_pcts)/len(modified_pcts),
                                color=COLORS['danger'], linestyle='--', label='Mean')
            self.ax_dist.legend(fontsize=10)

        # 4. 箱线图 - 数据离散程度
        if modified_pcts:
            bp = self.ax_box.boxplot(modified_pcts, patch_artist=True)
            bp['boxes'][0].set_facecolor(COLORS['primary'])
            bp['boxes'][0].set_alpha(0.7)
            self.ax_box.set_ylabel('Editing %', fontsize=12)
            self.ax_box.set_title('Box Plot', fontsize=14, fontweight='bold')
            self.ax_box.set_xticklabels(['All Samples'], fontsize=10)

        self.fig.tight_layout(pad=3)
        self.canvas.draw()

    def clear(self):
        self._data.clear()
        if HAS_MPL:
            self.ax_bar.clear()
            self.ax_pie.clear()
            self.ax_dist.clear()
            self.ax_box.clear()
            self.canvas.draw()
