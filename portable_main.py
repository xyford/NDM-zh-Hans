# -*- coding: utf-8 -*-
"""便携版入口: 免 Python 环境的 NDM 汉化补丁器 (PyInstaller 打包用)
用法: ndm-zh-patch.exe [NeatDM.exe 路径]   (不带参数则打安装目录)
行为: 若目标程序正在运行(文件被锁), 自动结束它再打补丁, 完成后重启
"""
import sys, os, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ndm_zh_patch

def resource(name):
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)

def image_running(img_name):
    try:
        out = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq {img_name}', '/NH'],
                             capture_output=True, text=True, timeout=15).stdout
        return img_name.lower() in out.lower()
    except Exception:
        return False

def kill_image(img_name):
    subprocess.run(['taskkill', '/F', '/IM', img_name], capture_output=True, timeout=20)
    for _ in range(20):
        if not image_running(img_name):
            return True
        time.sleep(0.3)
    return not image_running(img_name)

def run_patch(target):
    sys.argv = [sys.argv[0], target, '--translations', resource('translations.json')]
    return ndm_zh_patch.main()

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else r'C:\Program Files (x86)\Neat Download Manager\NeatDM.exe'
    if not os.path.exists(target):
        print(f'[X] 找不到文件: {target}')
        print('    请把 NeatDM.exe 的路径作为参数传入, 或先安装 Neat Download Manager')
        return 1

    img = os.path.basename(target)
    killed = False
    try:
        rc = run_patch(target)
    except PermissionError:
        # 多数情况是目标程序正在运行导致 exe 被锁定, 而非真的缺权限
        if image_running(img):
            print(f'[*] 检测到 {img} 正在运行(文件被锁定), 自动结束后重试...')
            kill_image(img)
            killed = True
            try:
                rc = run_patch(target)
            except PermissionError:
                print('[X] 写入仍被拒绝: 请右键"以管理员身份运行"')
                rc = 1
            except Exception as e:
                print(f'[X] 失败: {e}')
                rc = 1
        else:
            print('[X] 权限不足: 请右键"以管理员身份运行"')
            rc = 1
    except Exception as e:
        print(f'[X] 失败: {e}')
        rc = 1

    if killed and rc in (0, 2):
        try:
            subprocess.Popen([target])
            print('[*] 已重启 NDM')
        except Exception:
            pass
    return rc

if __name__ == '__main__':
    sys.exit(main())
