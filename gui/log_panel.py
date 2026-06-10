"""Thread-safe log panel for the IndelQuant GUI."""

import customtkinter as ctk
import tkinter as tk
import logging
import queue
from datetime import datetime

from gui.styles import COLORS


LEVEL_COLORS = {
    'DEBUG': '#94a3b8',
    'INFO': '#cdd6f4',
    'WARNING': '#f59e0b',
    'ERROR': '#ef4444',
    'CRITICAL': '#dc2626',
}


class LogPanel(ctk.CTkFrame):
    """Thread-safe log display panel."""

    def __init__(self, master, log_file=None, **kwargs):
        super().__init__(master, fg_color='transparent', **kwargs)
        self._queue = queue.Queue()
        self._log_file = log_file
        self._filter_level = 'ALL'
        self._all_messages = []
        self._build_ui()

    def _build_ui(self):
        toolbar = ctk.CTkFrame(self, fg_color='transparent', height=28)
        toolbar.pack(fill='x', pady=(0, 4))

        ctk.CTkLabel(
            toolbar,
            text='Log filter:',
            font=ctk.CTkFont(size=11),
            text_color=COLORS['text_secondary'],
        ).pack(side='left', padx=(0, 4))

        self._filter_var = ctk.StringVar(value='ALL')
        for level in ['ALL', 'INFO', 'WARNING', 'ERROR']:
            btn = ctk.CTkButton(
                toolbar,
                text=level,
                width=50,
                height=24,
                corner_radius=4,
                font=ctk.CTkFont(size=10),
                fg_color=COLORS['primary'] if level == 'ALL' else COLORS['bg'],
                text_color='#ffffff' if level == 'ALL' else COLORS['text_secondary'],
                hover_color=COLORS['primary_hover'],
                command=lambda l=level: self._set_filter(l),
            )
            btn.pack(side='left', padx=2)
            setattr(self, f'_btn_{level}', btn)

        self._count_label = ctk.CTkLabel(
            toolbar,
            text='',
            font=ctk.CTkFont(size=10),
            text_color=COLORS['text_secondary'],
        )
        self._count_label.pack(side='right', padx=4)

        self.text = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family='Consolas', size=13),
            fg_color='#1e1e2e',
            text_color='#cdd6f4',
            corner_radius=8,
            height=150,
        )
        self.text.pack(fill='both', expand=True)
        self.text.configure(state='disabled')

        self._context_menu = tk.Menu(self.text, tearoff=0)
        self._context_menu.add_command(label='Copy selection', command=self._copy_selected)
        self._context_menu.add_command(label='Select all', command=self._select_all)
        self._context_menu.add_separator()
        self._context_menu.add_command(label='Clear', command=self.clear)

        self.text._textbox.bind('<Button-3>', self._show_context_menu)
        self.after(100, self._poll)

    def _show_context_menu(self, event):
        try:
            self._context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._context_menu.grab_release()

    def _copy_selected(self):
        try:
            tb = self.text._textbox
            selected = tb.get('sel.first', 'sel.last')
            self.root.clipboard_clear()
            self.root.clipboard_append(selected)
        except tk.TclError:
            pass

    def _select_all(self):
        self.text._textbox.tag_add('sel', '1.0', 'end')

    @property
    def root(self):
        return self.winfo_toplevel()

    def _set_filter(self, level):
        self._filter_level = level
        for item in ['ALL', 'INFO', 'WARNING', 'ERROR']:
            btn = getattr(self, f'_btn_{item}')
            if item == level:
                btn.configure(fg_color=COLORS['primary'], text_color='#ffffff')
            else:
                btn.configure(fg_color=COLORS['bg'], text_color=COLORS['text_secondary'])
        self._refresh_display()

    def _refresh_display(self):
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')

        tb = self.text._textbox
        for level, msg in self._all_messages:
            if self._filter_level == 'ALL' or level == self._filter_level:
                color = LEVEL_COLORS.get(level, '#cdd6f4')
                tag = f'color_{level}'
                tb.tag_configure(tag, foreground=color)
                tb.insert('end', msg + '\n', tag)

        self.text.see('end')
        self.text.configure(state='disabled')

    def _poll(self):
        while not self._queue.empty():
            level, msg = self._queue.get_nowait()
            self._all_messages.append((level, msg))

            if self._filter_level == 'ALL' or level == self._filter_level:
                color = LEVEL_COLORS.get(level, '#cdd6f4')
                tag = f'color_{level}'
                tb = self.text._textbox
                tb.tag_configure(tag, foreground=color)
                self.text.configure(state='normal')
                tb.insert('end', msg + '\n', tag)
                self.text.see('end')
                self.text.configure(state='disabled')

            if self._log_file:
                try:
                    with open(self._log_file, 'a', encoding='utf-8') as f:
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        f.write(f'[{timestamp}] [{level}] {msg}\n')
                except OSError:
                    pass

        self._update_count_label()
        self.after(100, self._poll)

    def _update_count_label(self):
        total = len(self._all_messages)
        if total == 0:
            self._count_label.configure(text='')
            return

        errors = sum(1 for level, _ in self._all_messages if level in ('ERROR', 'CRITICAL'))
        warnings = sum(1 for level, _ in self._all_messages if level == 'WARNING')
        count_text = f'{total} messages'
        if errors:
            count_text += f' | errors: {errors}'
        if warnings:
            count_text += f' | warnings: {warnings}'
        self._count_label.configure(text=count_text)

    def log(self, msg, level='INFO'):
        self._queue.put((level, msg))

    def clear(self):
        self._all_messages.clear()
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.configure(state='disabled')
        self._count_label.configure(text='')


class GUILogHandler(logging.Handler):
    """Forward Python logging records to LogPanel."""

    def __init__(self, log_panel):
        super().__init__()
        self.panel = log_panel

    def emit(self, record):
        level = record.levelname
        self.panel.log(self.format(record), level=level)
