"""
导出工具模块 v0.0.2

功能：
- 将分析结果导出为 Excel 文件
- 将分析结果导出为 PDF 文件
- 支持自定义导出选项

依赖：
    - openpyxl: Excel 文件生成
    - matplotlib: 图表导出
"""

import os
import csv
import logging
from datetime import datetime

log = logging.getLogger(__name__)

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.chart import BarChart, Reference
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

try:
    import matplotlib
    matplotlib.use('Agg')  # 非交互式后端
    from matplotlib.figure import Figure
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


def export_to_excel(summary_data, output_path, title='CRISPR Analysis Report'):
    """
    将分析结果导出为 Excel 文件

    参数:
        summary_data: 汇总数据列表（字典列表）
        output_path: 输出文件路径（.xlsx）
        title: 报告标题

    返回:
        bool: 是否成功
    """
    if not HAS_OPENPYXL:
        log.error('openpyxl 未安装，无法导出 Excel')
        return False

    try:
        wb = Workbook()
        ws = wb.active
        ws.title = '分析结果'

        # 样式定义
        header_font = Font(name='Microsoft YaHei', size=14, bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='4A6CF7', end_color='4A6CF7', fill_type='solid')
        subheader_font = Font(name='Microsoft YaHei', size=11, bold=True, color='1E293B')
        normal_font = Font(name='Microsoft YaHei', size=11, color='1E293B')
        good_fill = PatternFill(start_color='DCFCE7', end_color='DCFCE7', fill_type='solid')
        warn_fill = PatternFill(start_color='FEF3C7', end_color='FEF3C7', fill_type='solid')
        bad_fill = PatternFill(start_color='FEE2E2', end_color='FEE2E2', fill_type='solid')
        thin_border = Border(
            left=Side(style='thin', color='E2E8F0'),
            right=Side(style='thin', color='E2E8F0'),
            top=Side(style='thin', color='E2E8F0'),
            bottom=Side(style='thin', color='E2E8F0'),
        )

        # 标题行
        ws.merge_cells('A1:F1')
        title_cell = ws['A1']
        title_cell.value = title
        title_cell.font = header_font
        title_cell.fill = header_fill
        title_cell.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[1].height = 35

        # 时间戳
        ws.merge_cells('A2:F2')
        ws['A2'].value = f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
        ws['A2'].font = Font(name='Microsoft YaHei', size=9, color='64748B')
        ws['A2'].alignment = Alignment(horizontal='center')

        # 表头
        if not summary_data:
            ws['A3'].value = '无数据'
            wb.save(output_path)
            return True

        headers = ['样本名', 'Reads Aligned', 'Unmodified%', 'Modified%', '状态']
        header_row = 4
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=header_row, column=col, value=h)
            cell.font = subheader_font
            cell.fill = PatternFill(start_color='F0F2F5', end_color='F0F2F5', fill_type='solid')
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = thin_border
            ws.column_dimensions[chr(64 + col)].width = 18

        # 数据行
        for i, row_data in enumerate(summary_data):
            row_num = header_row + 1 + i
            sample = row_data.get('Sample', '')
            reads = row_data.get('Reads_aligned', '')
            unmodified = row_data.get('Unmodified%', '')
            modified = row_data.get('Modified%', '')

            # 解析 modified% 用于颜色
            try:
                mod_val = float(str(modified).replace('%', ''))
            except (ValueError, TypeError):
                mod_val = 0

            status = '高效编辑' if mod_val > 50 else '中等编辑' if mod_val > 10 else '低效编辑'

            values = [sample, reads, unmodified, modified, status]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row_num, column=col, value=val)
                cell.font = normal_font
                cell.alignment = Alignment(horizontal='center', vertical='center')
                cell.border = thin_border

            # 根据编辑效率着色
            fill = bad_fill if mod_val > 50 else warn_fill if mod_val > 10 else good_fill
            for col in range(1, 6):
                ws.cell(row=row_num, column=col).fill = fill

        # 添加图表
        if len(summary_data) > 0 and HAS_MPL:
            try:
                chart = BarChart()
                chart.title = 'Editing Efficiency'
                chart.y_axis.title = 'Modified %'
                chart.x_axis.title = 'Sample'
                chart.style = 10
                chart.width = 20
                chart.height = 12

                data_ref = Reference(ws, min_col=4, min_row=header_row,
                                    max_row=header_row + len(summary_data))
                cats_ref = Reference(ws, min_col=1, min_row=header_row + 1,
                                     max_row=header_row + len(summary_data))
                chart.add_data(data_ref, titles_from_data=True)
                chart.set_categories(cats_ref)
                chart.shape = 4

                ws.add_chart(chart, f'A{header_row + len(summary_data) + 3}')
            except Exception as e:
                log.warning('添加图表失败: %s', e)

        wb.save(output_path)
        log.info('Excel 导出成功: %s', output_path)
        return True

    except Exception as e:
        log.error('Excel 导出失败: %s', e)
        return False


def export_to_csv(summary_data, output_path):
    """
    将分析结果导出为 CSV 文件

    参数:
        summary_data: 汇总数据列表
        output_path: 输出文件路径

    返回:
        bool: 是否成功
    """
    try:
        if not summary_data:
            return False

        keys = sorted(set().union(*[r.keys() for r in summary_data]))
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(summary_data)

        log.info('CSV 导出成功: %s', output_path)
        return True
    except Exception as e:
        log.error('CSV 导出失败: %s', e)
        return False


def export_chart_image(summary_data, output_path):
    """
    将分析结果导出为图表图片

    参数:
        summary_data: 汇总数据列表
        output_path: 输出图片路径（.png）

    返回:
        bool: 是否成功
    """
    if not HAS_MPL:
        log.error('matplotlib 未安装，无法导出图表')
        return False

    try:
        samples = []
        modified_pcts = []
        for row in summary_data:
            samples.append(row.get('Sample', ''))
            try:
                val = str(row.get('Modified%', '0')).replace('%', '')
                modified_pcts.append(float(val))
            except (ValueError, TypeError):
                modified_pcts.append(0)

        if not samples:
            return False

        fig = Figure(figsize=(12, 5), dpi=150, facecolor='white')

        # 柱状图
        ax1 = fig.add_subplot(121)
        colors = ['#ef4444' if v > 50 else '#f59e0b' if v > 10 else '#22c55e' for v in modified_pcts]
        bars = ax1.bar(range(len(samples)), modified_pcts, color=colors, edgecolor='white')
        ax1.set_xticks(range(len(samples)))
        ax1.set_xticklabels(samples, rotation=45, ha='right', fontsize=10)
        ax1.set_ylabel('Editing %', fontsize=12)
        ax1.set_title('Editing Efficiency by Sample', fontsize=14, fontweight='bold')
        ax1.set_ylim(0, max(105, max(modified_pcts) * 1.2 if modified_pcts else 105))
        for bar, val in zip(bars, modified_pcts):
            if val > 0:
                ax1.text(bar.get_x() + bar.get_width() / 2, val + 1,
                         f'{val:.1f}%', ha='center', va='bottom', fontsize=9)

        # 饼图
        ax2 = fig.add_subplot(122)
        avg = sum(modified_pcts) / len(modified_pcts) if modified_pcts else 0
        ax2.pie(
            [avg, 100 - avg],
            labels=['Modified', 'Unmodified'],
            colors=['#ef4444', '#22c55e'],
            autopct='%1.1f%%',
            startangle=90,
            textprops={'fontsize': 12}
        )
        ax2.set_title(f'Average Editing ({avg:.1f}%)', fontsize=14, fontweight='bold')

        fig.tight_layout(pad=2)
        fig.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')

        log.info('图表导出成功: %s', output_path)
        return True
    except Exception as e:
        log.error('图表导出失败: %s', e)
        return False