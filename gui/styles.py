"""
样式配置模块 v0.0.3

功能：
- 定义全局颜色方案（浅色/深色双主题）
- 定义字体样式
- 初始化 CustomTkinter 主题
- 支持运行时切换主题

设计理念：
- 使用现代化的扁平化设计
- 深色侧边栏 + 浅色内容区
- 统一的字体和颜色规范
- 深色模式全面支持

v0.0.3 改进：
- 添加深色模式配色
- 主题切换函数
- 侧边栏底部添加主题切换按钮
"""

import customtkinter as ctk

# 设置颜色主题为蓝色
ctk.set_default_color_theme('blue')

# ===== 浅色主题 =====
LIGHT_COLORS = {
    'bg': '#f0f2f5',              # 主背景色（浅灰）
    'card': '#ffffff',            # 卡片背景色（白色）
    'primary': '#4a6cf7',         # 主色调（蓝色）
    'primary_hover': '#3b5de7',   # 主色调悬停态
    'success': '#22c55e',         # 成功色（绿色）
    'danger': '#ef4444',          # 危险色（红色）
    'warning': '#f59e0b',         # 警告色（橙色）
    'text': '#1e293b',            # 主文本色（深灰）
    'text_secondary': '#64748b',  # 次要文本色
    'border': '#e2e8f0',          # 边框色
    'sidebar': '#1e293b',         # 侧边栏背景（深色）
    'sidebar_active': '#4a6cf7',  # 侧边栏选中态
    'sidebar_text': '#94a3b8',    # 侧边栏文本
    'sidebar_text_active': '#ffffff',  # 侧边栏选中文本
    'accent': '#8b5cf6',          # 强调色（紫色）
}

# ===== 深色主题 =====
DARK_COLORS = {
    'bg': '#0f172a',              # 主背景色（深蓝黑）
    'card': '#1e293b',            # 卡片背景色（深蓝灰）
    'primary': '#6383f7',         # 主色调（亮蓝）
    'primary_hover': '#7c9aff',   # 主色调悬停态
    'success': '#4ade80',         # 成功色（亮绿）
    'danger': '#f87171',          # 危险色（亮红）
    'warning': '#fbbf24',         # 警告色（亮黄）
    'text': '#e2e8f0',            # 主文本色（浅灰白）
    'text_secondary': '#94a3b8',  # 次要文本色
    'border': '#334155',          # 边框色
    'sidebar': '#0f172a',         # 侧边栏背景
    'sidebar_active': '#6383f7',  # 侧边栏选中态
    'sidebar_text': '#64748b',    # 侧边栏文本
    'sidebar_text_active': '#ffffff',  # 侧边栏选中文本
    'accent': '#a78bfa',          # 强调色（亮紫）
}

# 当前主题（默认浅色）
COLORS = dict(LIGHT_COLORS)
_current_mode = 'light'


def set_theme(mode):
    """
    切换主题

    参数:
        mode: 'light' 或 'dark'
    """
    global COLORS, _current_mode
    _current_mode = mode
    if mode == 'dark':
        COLORS.update(DARK_COLORS)
        ctk.set_appearance_mode('dark')
    else:
        COLORS.update(LIGHT_COLORS)
        ctk.set_appearance_mode('light')


def get_theme():
    """获取当前主题模式"""
    return _current_mode


def toggle_theme():
    """切换主题（浅色/深色）"""
    if _current_mode == 'light':
        set_theme('dark')
    else:
        set_theme('light')
    return _current_mode


# 初始设置浅色模式
set_theme('light')

# 字体缓存（避免重复创建）
_font_cache = {}


def _get_font(name, **kwargs):
    """
    获取或创建字体对象（带缓存）

    参数:
        name: 字体名称标识
        **kwargs: CTkFont 的参数（size, weight 等）
    """
    if name not in _font_cache:
        _font_cache[name] = ctk.CTkFont(**kwargs)
    return _font_cache[name]


# 预定义字体样式
def FONT_TITLE():
    """标题字体：22px 粗体"""
    return _get_font('title', size=22, weight='bold')

def FONT_SUBTITLE():
    """副标题字体：15px 粗体"""
    return _get_font('subtitle', size=15, weight='bold')

def FONT_NORMAL():
    """正文字体：13px"""
    return _get_font('normal', size=13)

def FONT_LABEL():
    """标签字体：13px 粗体"""
    return _get_font('label', size=13, weight='bold')

def FONT_BUTTON():
    """按钮字体：13px 粗体"""
    return _get_font('button', size=13, weight='bold')

def FONT_HINT():
    """提示字体：11px（较小，用于注释）"""
    return _get_font('hint', size=11)

def FONT_INPUT():
    """输入框字体：13px"""
    return _get_font('input', size=13)

def FONT_COMBO():
    """下拉框字体：13px"""
    return _get_font('combo', size=13)

def FONT_CHECK():
    """复选框字体：13px"""
    return _get_font('check', size=13)
