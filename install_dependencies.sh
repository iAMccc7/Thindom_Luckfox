#!/bin/bash
# tydeus 项目依赖安装脚本

echo "============================================================"
echo "tydeus 项目依赖安装"
echo "============================================================"

# 检查是否为root用户
if [ "$EUID" -eq 0 ]; then 
    echo "⚠ 请不要使用root用户运行此脚本"
    exit 1
fi

# 1. 安装系统级依赖
echo ""
echo "步骤1: 安装系统级依赖..."
echo "----------------------------------------"

# 检查并安装 sox
if ! command -v sox &> /dev/null; then
    echo "安装 sox..."
    sudo apt update && sudo apt install -y sox
else
    echo "✓ sox 已安装"
fi

# 检查并安装 mpv
if ! command -v mpv &> /dev/null; then
    echo "安装 mpv..."
    sudo apt update && sudo apt install -y mpv
else
    echo "✓ mpv 已安装"
fi

# 检查并安装 Python 系统包
echo "检查 Python 系统包..."
if ! python3 -c "import spidev" 2>/dev/null; then
    echo "安装 python3-spidev..."
    sudo apt install -y python3-spidev
else
    echo "✓ python3-spidev 已安装"
fi

# 2. 安装 Python 依赖
echo ""
echo "步骤2: 安装 Python 依赖..."
echo "----------------------------------------"

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 安装 pip 依赖
echo "安装 pip 依赖..."
pip3 install --break-system-packages -r requirements.txt

echo ""
echo "============================================================"
echo "依赖安装完成！"
echo "============================================================"
echo ""
echo "已安装的依赖："
echo "  - Python包: dashscope, pyaudio, requests, lgpio, websockets, pillow"
echo "  - 系统工具: sox, mpv"
echo "  - 系统包: python3-spidev"
echo ""
echo "如果遇到权限问题，请确保："
echo "  1. 用户已添加到 spi 组: sudo usermod -aG spi \$USER"
echo "  2. 重新登录以使组权限生效"
echo ""

