# 声笔词库工具 - Android APP

将手机通讯录一键转换为Rime输入法声笔方案词库。

## 功能特点

- 📱 **自动读取通讯录** - 直接访问手机通讯录数据库
- 🔤 **智能编码生成** - 按声笔规则自动生成编码
- 📦 **自动备份** - 更新前自动备份原有词库
- 📋 **完整界面** - 主页、设置、预览、历史记录

## 项目结构

```
android_app/
├── main.py           # 主程序
├── shengbi.kv        # 界面布局
├── buildozer.spec    # 打包配置
└── README.md         # 本文档
```

## 打包步骤

### 1. 环境准备

**在Linux系统（推荐Ubuntu 20.04+）上操作：**

```bash
# 安装依赖
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev automake python3 python3-pip python3-venv

# 安装buildozer
pip3 install --user buildozer cython

# 添加到PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### 2. 克隆/复制项目

```bash
# 将项目复制到Linux系统
cd ~
# 假设项目在 android_app 目录
cd android_app
```

### 3. 初始化并打包

```bash
# 首次运行，下载SDK/NDK（需要较长时间）
buildozer init  # 如果没有buildozer.spec
buildozer android debug

# 打包完成后，APK在 bin/ 目录
```

### 4. 安装到手机

```bash
# 通过ADB安装
adb install bin/shengbi-1.0.0-arm64-v8a-debug.apk

# 或直接复制APK到手机安装
```

## 一键打包脚本

创建 `build.sh`：

```bash
#!/bin/bash
set -e

echo "=== 开始打包声笔词库工具 ==="

# 检查buildozer
if ! command -v buildozer &> /dev/null; then
    echo "安装 buildozer..."
    pip3 install --user buildozer cython
fi

# 清理旧文件
rm -rf bin/ .buildozer/

# 打包
echo "开始打包..."
buildozer android debug

echo "=== 打包完成 ==="
echo "APK位置: bin/"
ls -la bin/*.apk
```

## 权限说明

APP需要以下权限：

| 权限 | 用途 |
|------|------|
| READ_CONTACTS | 读取通讯录 |
| READ_EXTERNAL_STORAGE | 读取词库文件 |
| WRITE_EXTERNAL_STORAGE | 写入词库文件 |

## 界面说明

### 主页
- 显示当前配置状态
- 读取通讯录按钮
- 生成词库按钮
- 预览词条按钮

### 设置页
- 词库文件路径
- Rime配置目录
- VCF文件路径（可选）
- 通讯录来源选择

### 预览页
- 显示新增词条列表
- 姓名和编码对照

### 历史页
- 显示更新历史记录
- 时间和新增数量

## 常见问题

### Q: 打包失败，提示SDK下载失败
A: 需要科学上网或配置代理：
```bash
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
```

### Q: APP无法读取通讯录
A: 确保已授予通讯录权限，或在设置中选择VCF文件模式

### Q: 词库没有更新
A: 检查Rime目录路径是否正确，确保有写入权限

## 技术栈

- **Kivy** - 跨平台GUI框架
- **Buildozer** - Android打包工具
- **pypinyin** - 拼音转换库
- **SQLite** - 通讯录数据库访问

## 许可证

MIT License
