#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
声笔词库工具 - 智能环境检测与安装脚本
自动识别运行环境并提供对应的安装/使用方案

使用方法:
    python3 install.py           # 交互式安装
    python3 install.py --auto   # 自动安装（自动模式）
    python3 install.py --check  # 仅检测环境
"""

import os
import sys
import subprocess
import platform
import shutil
import argparse
from pathlib import Path

# ============================================================
# 颜色定义
# ============================================================
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
CYAN = '\033[96m'
RESET = '\033[0m'
BOLD = '\033[1m'

def log_info(msg):
    print(f"{BLUE}[INFO]{RESET} {msg}")

def log_success(msg):
    print(f"{GREEN}[✓]{RESET} {msg}")

def log_warning(msg):
    print(f"{YELLOW}[!]{RESET} {msg}")

def log_error(msg):
    print(f"{RED}[✗]{RESET} {msg}")

def log_header(msg):
    print(f"\n{CYAN}{BOLD}{'─'*50}{RESET}")
    print(f"{CYAN}{BOLD}  {msg}{RESET}")
    print(f"{CYAN}{BOLD}{'─'*50}{RESET}\n")

def log_step(msg):
    print(f"\n{BOLD}{'━'*50}{RESET}")
    print(f"{BOLD}  {msg}{RESET}")
    print(f"{BOLD}{'━'*50}{RESET}")

# ============================================================
# 工具函数
# ============================================================

def run_command(cmd, check=False):
    """执行命令并返回结果"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, timeout=30
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "命令执行超时"
    except Exception as e:
        return False, "", str(e)

def check_command(cmd_name):
    """检查命令是否存在"""
    success, stdout, _ = run_command(f"which {cmd_name}")
    return success, stdout

def check_python_package(package):
    """检查Python包是否已安装"""
    success, _, _ = run_command(f"python3 -c 'import {package}' 2>/dev/null")
    return success

def get_python_version():
    """获取Python版本"""
    success, stdout, _ = run_command("python3 --version")
    if success:
        return stdout.replace("Python ", "")
    return "未安装"

# ============================================================
# 环境检测
# ============================================================

def detect_environment():
    """检测当前运行环境"""
    info = {
        # 基础信息
        'platform': platform.system(),
        'platform_release': platform.release(),
        'machine': platform.machine(),
        'python_version': get_python_version(),
        
        # 环境类型
        'is_android': False,
        'is_termux': False,
        'is_wsl': False,
        'is_linux': False,
        'is_macos': False,
        'is_windows': False,
        
        # 特殊路径
        'has_contacts_db': False,
        'has_storage_emulated': False,
        'has_termux_pkg': False,
        
        # Rime相关
        'has_rime_dir': False,
        'has_sbzdy': False,
        
        # Python包
        'has_pypinyin': False,
        'has_quopri': False,
    }
    
    # 平台检测
    p = platform.system().lower()
    if 'android' in p or 'linux' in p and os.path.exists('/system'):
        info['is_android'] = True
    if 'linux' in p:
        info['is_linux'] = True
    elif 'darwin' in p:
        info['is_macos'] = True
    elif 'windows' in p:
        info['is_windows'] = True
    
    # Termux检测（需要多个条件同时满足）
    termux_markers_count = 0
    if os.path.exists('/data/data/com.termux'):
        termux_markers_count += 2
    if 'com.termux' in os.environ.get('PREFIX', ''):
        termux_markers_count += 2
    if os.path.exists(os.path.expanduser('~/../usr/bin/pkg')):
        termux_markers_count += 1
    
    # Termux特征：PREFIX包含termux 或有com.termux目录
    if termux_markers_count >= 2 and env_info['is_linux']:
        info['is_termux'] = True
    
    # 特殊环境检测
    if info['is_linux']:
        # WSL检测
        try:
            with open('/proc/version', 'r') as f:
                content = f.read().lower()
                if 'microsoft' in content or 'wsl' in content:
                    info['is_wsl'] = True
        except:
            pass
    
    # Android通讯录数据库
    contacts_db_paths = [
        '/data/data/com.android.providers.contacts/databases/contacts2.db',
        '/data/user/0/com.android.providers.contacts/databases/contacts2.db',
    ]
    for path in contacts_db_paths:
        if os.path.exists(path):
            info['has_contacts_db'] = True
            break
    
    # 存储检测
    if os.path.exists('/storage/emulated/0'):
        info['has_storage_emulated'] = True
    
    # Termux包管理器
    info['has_termux_pkg'], _ = check_command('pkg')
    
    # Rime目录
    rime_dirs = [
        '/storage/emulated/0/rime',
        os.path.expanduser('~/rime'),
        os.path.expanduser('~/storage/shared/rime'),
    ]
    for rdir in rime_dirs:
        if os.path.exists(rdir):
            info['has_rime_dir'] = True
            if os.path.exists(os.path.join(rdir, 'sbzdy.txt')):
                info['has_sbzdy'] = True
            break
    
    # Python包
    info['has_pypinyin'] = check_python_package('pypinyin')
    info['has_quopri'] = check_python_package('quopri')
    
    return info

def get_env_type(env_info):
    """根据检测结果判断环境类型"""
    if env_info['is_termux']:
        if env_info['has_contacts_db']:
            return "termux_full", "手机Termux（完整权限）"
        else:
            return "termux_limited", "手机Termux（有限权限）"
    elif env_info['is_android']:
        return "android", "安卓手机"
    elif env_info['is_wsl']:
        return "wsl", "Windows WSL"
    elif env_info['is_linux']:
        return "linux", "Linux系统"
    elif env_info['is_macos']:
        return "macos", "Mac系统"
    else:
        return "unknown", "未知环境"

# ============================================================
# 安装函数
# ============================================================

def install_python_package(package):
    """安装Python包"""
    log_info(f"安装 {package}...")
    success, _, error = run_command(f"pip install {package}")
    if success:
        log_success(f"{package} 安装成功")
        return True
    else:
        # 尝试使用 --user
        success, _, _ = run_command(f"pip install {package} --user")
        if success:
            log_success(f"{package} 安装成功（用户模式）")
            return True
        log_error(f"{package} 安装失败: {error}")
        return False

def install_pip():
    """安装pip"""
    log_info("安装 pip...")
    if os.path.exists('/usr/bin/apt'):
        success, _, _ = run_command("sudo apt install python3-pip -y")
    elif os.path.exists('/usr/bin/yum'):
        success, _, _ = run_command("sudo yum install python3-pip -y")
    elif os.path.exists('/data/data/com.termux'):
        success, _, _ = run_command("pkg install python-pip")
    else:
        success, _, _ = run_command("curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py && python3 get-pip.py")
    
    if success:
        log_success("pip 安装成功")
        return True
    log_error("pip 安装失败")
    return False

def install_termux_pkg(packages):
    """在Termux中安装包"""
    if not env_info['has_termux_pkg']:
        log_error("Termux pkg 未安装")
        return False
    
    for pkg in packages:
        log_info(f"安装 {pkg}...")
        success, _, error = run_command(f"pkg install {pkg} -y")
        if success:
            log_success(f"{pkg} 安装成功")
        else:
            log_error(f"{pkg} 安装失败: {error}")
            return False
    return True

# ============================================================
# 主安装流程
# ============================================================

env_info = None  # 全局变量

def do_install():
    """执行安装"""
    global env_info
    env_info = detect_environment()
    env_type, env_name = get_env_type(env_info)
    
    log_header("环境检测结果")
    
    print(f"{BOLD}检测到的环境:{RESET} {GREEN}{env_name}{RESET}")
    print(f"平台: {env_info['platform']} {env_info['platform_release']}")
    print(f"架构: {env_info['machine']}")
    print(f"Python: {env_info['python_version']}")
    
    print(f"\n{BOLD}功能支持:{RESET}")
    print(f"  通讯录数据库: {'✅' if env_info['has_contacts_db'] else '❌'}")
    print(f"  Rime目录: {'✅' if env_info['has_rime_dir'] else '❌'}")
    print(f"  词库文件: {'✅' if env_info['has_sbzdy'] else '❌'}")
    
    print(f"\n{BOLD}Python依赖:{RESET}")
    print(f"  pypinyin: {'✅' if env_info['has_pypinyin'] else '❌'}")
    print(f"  quopri: {'✅' if env_info['has_quopri'] else '❌'}")
    
    print()
    
    # 根据环境执行对应安装
    if env_type in ["termux_full", "termux_limited"]:
        install_for_termux()
    elif env_type == "android":
        install_for_android()
    elif env_type == "wsl":
        install_for_wsl()
    elif env_type in ["linux", "macos"]:
        install_for_computer()
    else:
        install_for_unknown()
    
    # 复制脚本到目标位置
    install_script()
    
    # 显示使用说明
    show_usage(env_type)

def install_for_termux():
    """Termux环境安装"""
    log_step("正在安装 Termux 环境...")
    
    # 安装必要组件
    packages = ['python', 'termux-api']
    
    if not env_info['has_termux_pkg']:
        log_error("请先在Termux中安装pkg: pkg update && pkg install proot")
        return
    
    if not install_termux_pkg(packages):
        return
    
    # 安装Python依赖
    if not env_info['has_pypinyin']:
        install_python_package('pypinyin')

def install_for_android():
    """Android环境安装（无Termux）"""
    log_step("正在配置 安卓手机 环境...")
    
    log_warning("检测到Android环境但无Termux")
    print("""
    {BOLD}推荐方案:{RESET}
    
    {GREEN}方案A:{RESET} 安装Termux（推荐）
        1. 在应用商店搜索并安装 "Termux"
        2. 安装后运行本脚本即可自动配置
        
    {YELLOW}方案B:{RESET} 使用手动模式
        1. 在手机通讯录中导出为.vcf文件
        2. 将.vcf文件传输到电脑
        3. 在电脑上使用本工具处理
    """.format(BOLD=BOLD, GREEN=GREEN, YELLOW=YELLOW))
    
    # 尝试安装pypinyin
    if not env_info['has_pypinyin']:
        install_python_package('pypinyin')

def install_for_wsl():
    """WSL环境安装"""
    log_step("正在配置 WSL 环境...")
    
    # WSL中无法直接访问手机，但可以处理VCF文件
    log_info("WSL环境检测完成")
    log_info("请将手机通讯录导出为.vcf文件后上传处理")
    
    if not env_info['has_pypinyin']:
        install_python_package('pypinyin')

def install_for_computer():
    """普通电脑安装"""
    log_step("正在配置 电脑 环境...")
    
    log_info("检测到电脑环境")
    log_info("请将手机通讯录导出为.vcf文件后上传处理")
    
    if not env_info['has_pypinyin']:
        install_python_package('pypinyin')

def install_for_unknown():
    """未知环境"""
    log_step("正在配置环境...")
    
    log_warning("无法识别的环境，尝试通用安装...")
    
    if not env_info['has_pypinyin']:
        install_python_package('pypinyin')

def install_script():
    """安装主脚本"""
    log_step("配置脚本...")
    
    script_path = Path(__file__).resolve()
    scripts_dir = Path.home() / '.shengbi'
    
    # 创建目录
    scripts_dir.mkdir(parents=True, exist_ok=True)
    
    # 复制脚本
    target_convert = scripts_dir / 'convert.py'
    target_install = scripts_dir / 'install.py'
    
    shutil.copy(script_path, target_install)
    
    # 复制convert.py（如果存在）
    convert_src = script_path.parent / 'convert.py'
    if convert_src.exists():
        shutil.copy(convert_src, target_convert)
        log_success(f"脚本已安装到: {scripts_dir}")
    else:
        log_warning(f"convert.py 未找到，请手动复制到: {scripts_dir}")

def show_usage(env_type):
    """显示使用说明"""
    log_step("使用说明")
    
    print(f"""
{BOLD}使用方式:{RESET}

{CYAN}一键更新词库:{RESET}
    cd ~/.shengbi && python3 convert.py --auto -d /path/to/sbzdy.txt

{CYAN}查看帮助:{RESET}
    python3 convert.py --help

{CYAN}完整命令示例:{RESET}
    # 指定VCF文件 + 合并词库 + 复制到Rime目录 + 自动备份
    python3 convert.py contacts.vcf \\
        -d /storage/emulated/0/rime/sbzdy.txt \\
        --copy-to /storage/emulated/0/rime/ \\
        --rename sbzdy.txt

{BOLD}环境特点:{RESET}
""")
    
    if env_type == "termux_full":
        print("""
    ✅ 可以使用 --auto 自动模式
       运行: python3 convert.py --auto -d <词库路径>
""")
    else:
        print("""
    ⚠️ 仅支持手动模式
       需要手动导出通讯录为.vcf文件
       或安装Termux以获得完整支持
""")

def do_check():
    """仅检测环境"""
    global env_info
    env_info = detect_environment()
    env_type, env_name = get_env_type(env_info)
    
    print(f"""
{BOLD}环境检测报告{RESET}
{'='*50}

{BOLD}运行环境:{RESET} {GREEN}{env_name}{RESET}

{BOLD}系统信息:{RESET}
  平台: {env_info['platform']} {env_info['platform_release']}
  架构: {env_info['machine']}
  Python: {env_info['python_version']}

{BOLD}功能支持:{RESET}
  通讯录数据库: {'✅ 可用' if env_info['has_contacts_db'] else '❌ 不可用'}
  Rime目录: {'✅ 存在' if env_info['has_rime_dir'] else '❌ 未找到'}
  词库文件: {'✅ 存在' if env_info['has_sbzdy'] else '❌ 未找到'}

{BOLD}Python依赖:{RESET}
  pypinyin: {'✅ 已安装' if env_info['has_pypinyin'] else '❌ 未安装'}
  quopri: {'✅ 已安装' if env_info['has_quopri'] else '❌ 未安装'}

{BOLD}推荐操作:{RESET}
""")
    
    if env_type == "termux_full":
        print(f"""  {GREEN}✅ 可以使用 --auto 自动模式{RESET}
     运行: python3 convert.py --auto -d <词库路径>
""")
    else:
        print(f"""  {YELLOW}⚠️ 建议安装Termux以获得完整支持{RESET}
     或手动导出通讯录为.vcf文件使用
""")

# ============================================================
# 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='声笔词库工具 - 智能环境检测与安装脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--check', action='store_true',
        help='仅检测环境，不执行安装'
    )
    parser.add_argument(
        '--auto', action='store_true',
        help='自动安装所有依赖'
    )
    
    args = parser.parse_args()
    
    if args.check:
        do_check()
    else:
        do_install()

if __name__ == '__main__':
    main()
