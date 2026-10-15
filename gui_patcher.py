# -*- coding: utf-8 -*-
"""NDM 汉化工具 GUI 版 (单文件 exe)

模式:
  ndm-zh-patch.exe                 → 图形界面
  ndm-zh-patch.exe --silent [exe]  → 静默汉化(供看门狗/命令行调用)
  ndm-zh-patch.exe --restore [exe] → 静默恢复原版

GUI 功能:
  - 一键汉化 / 恢复原版 (自动结束运行中的 NDM, 完成后自动拉起)
  - 启动时自动检查 GitHub Releases 更新, 有新版可一键下载
"""
import sys, os, subprocess, time, threading, json, ctypes
import urllib.request

__version__ = '1.0.0'
GITHUB_REPO = 'xyford/NDM-zh-Hans'
DEFAULT_TARGET = r'C:\Program Files (x86)\Neat Download Manager\NeatDM.exe'
BACKUP_DIR = os.path.join(os.environ.get('ProgramData', r'C:\ProgramData'), 'NDM-zh')
BACKUP_EXE = os.path.join(BACKUP_DIR, 'NeatDM.original.bak')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ndm_zh_patch


def resource(name):
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


def ndm_pids():
    """返回正在运行的 NeatDM 进程 PID 列表"""
    try:
        out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq NeatDM.exe', '/FO', 'CSV', '/NH'],
                             capture_output=True, timeout=15).stdout.decode('gbk', errors='replace')
        pids = []
        for line in out.splitlines():
            parts = line.strip().strip('"').split('","')
            if len(parts) >= 2 and parts[0].lower() == 'neatdm.exe':
                pids.append(parts[1])
        return pids
    except Exception:
        return []


def kill_ndm():
    pids = ndm_pids()
    if not pids:
        return False
    subprocess.run(['taskkill', '/F', '/IM', 'NeatDM.exe'], capture_output=True, timeout=20)
    for _ in range(30):
        if not ndm_pids():
            break
        time.sleep(0.3)
    return True


def start_ndm(path):
    try:
        subprocess.Popen([path])
    except Exception:
        pass


def do_patch(target, log=print):
    """打补丁; 返回 (rc, was_running)"""
    if not os.path.exists(target):
        log(f'[X] 找不到文件: {target}')
        return 1, False
    was_running = False
    if ndm_pids():
        log('[*] 检测到 NDM 正在运行, 先结束进程...')
        kill_ndm()
        was_running = True
    # 备份原版(未打补丁的) exe
    if not os.path.exists(BACKUP_EXE):
        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            if not ndm_zh_patch.is_patched(target):
                import shutil
                shutil.copy2(target, BACKUP_EXE)
                log(f'[*] 已备份原版到 {BACKUP_EXE}')
        except Exception as e:
            log(f'[!] 备份失败(不影响汉化): {e}')
    argv_bak = sys.argv
    try:
        sys.argv = [sys.argv[0], target, '--translations', resource('translations.json')]
        rc = ndm_zh_patch.main()
    except PermissionError:
        log('[X] 写入被拒绝: 请以管理员身份运行本程序')
        rc = 1
    except Exception as e:
        log(f'[X] 失败: {e}')
        rc = 1
    finally:
        sys.argv = argv_bak
    if was_running and rc in (0, 2):
        start_ndm(target)
        log('[*] 已自动拉起 NDM')
    return rc, was_running


def do_restore(target, log=print):
    if not os.path.exists(BACKUP_EXE):
        log(f'[X] 找不到原版备份: {BACKUP_EXE}')
        return 1
    was_running = False
    if ndm_pids():
        log('[*] 检测到 NDM 正在运行, 先结束进程...')
        kill_ndm()
        was_running = True
    try:
        import shutil
        shutil.copy2(BACKUP_EXE, target)
        log('[√] 已恢复英文原版')
        rc = 0
    except PermissionError:
        log('[X] 写入被拒绝: 请以管理员身份运行本程序')
        rc = 1
    if was_running and rc == 0:
        start_ndm(target)
        log('[*] 已自动拉起 NDM')
    return rc


def check_update(log=print):
    """返回 (有更新, 最新tag, 下载url) 或 None"""
    try:
        req = urllib.request.Request(
            f'https://api.github.com/repos/{GITHUB_REPO}/releases/latest',
            headers={'User-Agent': 'ndm-zh-patch'})
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read().decode())
        latest = d.get('tag_name', '').lstrip('vV')
        if not latest:
            return None
        def ver(v):
            return tuple(int(x) for x in v.split('.') if x.isdigit())
        if ver(latest) > ver(__version__):
            url = None
            for a in d.get('assets', []):
                if a.get('name', '').endswith('.exe'):
                    url = a['browser_download_url']
                    break
            return latest, url
        return None
    except Exception:
        return None


def silent_main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    mode = next((a for a in sys.argv[1:] if a.startswith('--')), '--silent')
    target = args[0] if args else DEFAULT_TARGET
    logfile = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'ndm-zh-patch.log')
    def log(m):
        try:
            with open(logfile, 'a', encoding='utf-8') as f:
                f.write(time.strftime('%F %T ') + str(m) + '\n')
        except Exception:
            pass
    if mode == '--restore':
        return do_restore(target, log)
    rc, _ = do_patch(target, log)
    return rc


def gui_main():
    import tkinter as tk
    from tkinter import ttk, messagebox

    root = tk.Tk()
    root.title(f'NDM 汉化工具 v{__version__}')
    root.geometry('560x430')
    root.resizable(False, False)

    top = ttk.Frame(root, padding=10)
    top.pack(fill='x')
    status_var = tk.StringVar(value='正在检测 NDM 状态...')
    ttk.Label(top, textvariable=status_var, font=('Microsoft YaHei UI', 10, 'bold')).pack(anchor='w')
    upd_var = tk.StringVar(value='正在检查更新...')
    upd_lbl = ttk.Label(top, textvariable=upd_var, foreground='#666')
    upd_lbl.pack(anchor='w', pady=(4, 0))

    btn_row = ttk.Frame(root, padding=(10, 0))
    btn_row.pack(fill='x')

    log_txt = tk.Text(root, height=14, state='disabled', wrap='word', font=('Consolas', 9))
    log_txt.pack(fill='both', expand=True, padx=10, pady=10)

    def log(m):
        log_txt.configure(state='normal')
        log_txt.insert('end', str(m) + '\n')
        log_txt.see('end')
        log_txt.configure(state='disabled')

    class StdoutToLog:
        def write(self, s):
            s = s.rstrip('\n')
            if s:
                root.after(0, log, s)
        def flush(self):
            pass
    sys.stdout = StdoutToLog()
    sys.stderr = StdoutToLog()

    def refresh_status():
        if not os.path.exists(DEFAULT_TARGET):
            status_var.set('NDM 状态: 未安装 (未找到默认路径)')
        elif ndm_zh_patch.is_patched(DEFAULT_TARGET):
            status_var.set('NDM 状态: 已汉化 √')
        else:
            status_var.set('NDM 状态: 英文原版')

    def run_action(fn, label):
        def worker():
            btn_patch.configure(state='disabled')
            btn_restore.configure(state='disabled')
            log(f'—— {label} ——')
            try:
                rc = fn(DEFAULT_TARGET, log)
                log('完成' if rc == 0 else ('无需操作' if rc == 2 else f'失败 (rc={rc})'))
            finally:
                root.after(0, refresh_status)
                root.after(0, lambda: btn_patch.configure(state='normal'))
                root.after(0, lambda: btn_restore.configure(state='normal'))
        threading.Thread(target=worker, daemon=True).start()

    btn_patch = ttk.Button(btn_row, text='一键汉化', command=lambda: run_action(do_patch, '一键汉化'))
    btn_patch.pack(side='left', padx=(0, 10))
    btn_restore = ttk.Button(btn_row, text='恢复原版', command=lambda: run_action(do_restore, '恢复原版'))
    btn_restore.pack(side='left')

    btn_update = None
    def on_update_click(url, tag):
        def worker():
            log(f'[*] 正在下载新版本 v{tag} ...')
            try:
                dst = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), f'ndm-zh-patch-v{tag}.exe')
                urllib.request.urlretrieve(url, dst)
                log(f'[√] 已下载到: {dst}')
                log('[*] 请关闭本程序后使用新版本替换')
            except Exception as e:
                log(f'[X] 下载失败: {e}')
        threading.Thread(target=worker, daemon=True).start()

    def update_worker():
        r = check_update()
        if r:
            tag, url = r
            root.after(0, lambda: upd_var.set(f'发现新版本 v{tag} (当前 v{__version__})'))
            if url:
                def show_btn():
                    nonlocal btn_update
                    btn_update = ttk.Button(btn_row, text='下载更新', command=lambda: on_update_click(url, tag))
                    btn_update.pack(side='left', padx=(10, 0))
                root.after(0, show_btn)
        else:
            root.after(0, lambda: upd_var.set('已是最新版本'))

    refresh_status()
    threading.Thread(target=update_worker, daemon=True).start()
    root.mainloop()


if __name__ == '__main__':
    if any(a in ('--silent', '--restore') for a in sys.argv[1:]):
        sys.exit(silent_main())
    # 单实例
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, 'NDMZhPatchGuiMutex')
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        sys.exit(0)
    gui_main()
