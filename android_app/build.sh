#!/bin/bash
# 声笔词库工具 - 一键打包脚本
# 使用方法: bash build.sh

set -e

echo "========================================"
echo "  声笔词库工具 - Android APP 打包"
echo "========================================"
echo ""

# 检查系统
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "⚠️  警告: 建议在Linux系统上打包"
    echo "   推荐使用 Ubuntu 20.04+ 或 WSL2"
fi

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未安装 Python3"
    exit 1
fi
echo "✅ Python3: $(python3 --version)"

# 检查buildozer
if ! command -v buildozer &> /dev/null; then
    echo ""
    echo "正在安装 buildozer..."
    pip3 install --user buildozer cython
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "✅ Buildozer: $(buildozer --version 2>/dev/null || echo '已安装')"

# 检查Java
if ! command -v java &> /dev/null; then
    echo "⚠️  未检测到Java，打包可能失败"
    echo "   请安装: sudo apt install openjdk-17-jdk"
else
    echo "✅ Java: $(java -version 2>&1 | head -1)"
fi

echo ""
echo "开始打包..."
echo ""

# 清理旧文件
if [ -d "bin" ]; then
    echo "清理旧的APK文件..."
    rm -rf bin/
fi

# 打包
buildozer android debug

echo ""
echo "========================================"
echo "  ✅ 打包完成！"
echo "========================================"
echo ""
echo "APK文件位置:"
ls -la bin/*.apk 2>/dev/null || echo "未找到APK文件"
echo ""
echo "安装方法:"
echo "  1. 通过ADB: adb install bin/shengbi-*.apk"
echo "  2. 复制到手机直接安装"
echo ""
