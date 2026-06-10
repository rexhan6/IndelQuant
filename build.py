"""Build script for IndelQuant."""
import subprocess
import os
import sys
import shutil
import glob

# Clean up
for d in ['dist', 'build']:
    if os.path.exists(d):
        shutil.rmtree(d)
for f in glob.glob('*.spec'):
    os.remove(f)

# Get Python executable
python = sys.executable

# Find Tcl/Tk data
import tkinter
tcl_dir = None
tk_dir = None

# Try to find Tcl/Tk directories
for path in sys.path:
    for root, dirs, files in os.walk(path):
        if 'init.tcl' in files and 'tcl8.6' in root:
            tcl_dir = root
        if 'tk.tcl' in files and 'tk8.6' in root:
            tk_dir = root

# Also check common locations
home = os.path.expanduser('~')
for base in [
    os.path.join(home, '.conda', 'envs', 'crispranalysis', 'Library', 'lib'),
    os.path.join(home, 'miniconda3', 'Library', 'lib'),
    os.path.join(home, 'miniconda3', 'tcl'),
]:
    t = os.path.join(base, 'tcl8.6')
    k = os.path.join(base, 'tk8.6')
    if os.path.exists(t):
        tcl_dir = t
    if os.path.exists(k):
        tk_dir = k

print(f'Tcl dir: {tcl_dir}')
print(f'Tk dir: {tk_dir}')

# Build command
cmd = [
    python, '-m', 'PyInstaller',
    '--onefile',
    '--noconsole',
    '--name', 'IndelQuant',
    '--add-data', 'config;config',
    '--add-data', 'core;core',
    '--add-data', 'gui;gui',
    '--add-data', 'utils;utils',
    '--hidden-import', 'customtkinter',
    '--hidden-import', 'matplotlib',
    '--hidden-import', 'numpy',
    '--hidden-import', 'pandas',
    '--hidden-import', 'openpyxl',
    '--hidden-import', 'PIL',
    '--hidden-import', 'PIL._tkinter_finder',
    '--collect-data', 'customtkinter',
    '--collect-data', 'matplotlib',
]

# Add Tcl/Tk data if found
if tcl_dir:
    cmd.extend(['--add-data', f'{tcl_dir};tcl8.6'])
if tk_dir:
    cmd.extend(['--add-data', f'{tk_dir};tk8.6'])

cmd.append('main.py')

print(f'Running: {" ".join(cmd)}')
print()

project_dir = os.path.dirname(os.path.abspath(__file__))
proc = subprocess.run(cmd, cwd=project_dir)

if proc.returncode == 0:
    print('\nBuild successful!')
    exe_path = os.path.join(project_dir, 'dist', 'IndelQuant.exe')
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f'Output: {exe_path} ({size_mb:.1f} MB)')
else:
    print('\nBuild failed!')
