"""
拖拽支持模块

功能：
- 为输入框添加文件拖拽支持
- 使用 windnd 库实现（Windows 平台）
- 兼容 customtkinter
"""

import customtkinter as ctk
import windnd


class DropEntry(ctk.CTkFrame):
    """
    支持拖拽的输入框
    """

    def __init__(self, master, textvariable=None, width=400, **kwargs):
        super().__init__(master, fg_color='transparent')
        
        self._var = textvariable or ctk.StringVar()
        
        # 创建输入框
        self._entry = ctk.CTkEntry(
            self, textvariable=self._var, width=width,
            font=ctk.CTkFont(size=14), corner_radius=8, height=36
        )
        self._entry.pack(side='left', fill='x', expand=True)
        
        # 绑定拖拽
        self._setup_dnd()
    
    def _setup_dnd(self):
        """设置拖拽支持"""
        try:
            def on_drop(files):
                if files:
                    # windnd 返回 bytes，需要解码
                    filepath = files[0].decode('utf-8') if isinstance(files[0], bytes) else files[0]
                    self._var.set(filepath)
            
            windnd.hook_dropfiles(self._entry, func=on_drop)
            print(f'DnD registered for entry')
        except Exception as e:
            print(f'DnD registration failed: {e}')
    
    def get(self):
        """获取输入框的值"""
        return self._var.get()
    
    def set(self, value):
        """设置输入框的值"""
        self._var.set(value)
    
    @property
    def textvariable(self):
        """获取 StringVar"""
        return self._var
