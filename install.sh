#!/bin/bash

echo "================================================"
echo "  Hyperliquid 大户交易监控系统 - 安装脚本"
echo "================================================"
echo ""

# 检查Python版本
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 python3，请先安装 Python 3.7+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✅ Python 版本: $PYTHON_VERSION"

# 安装依赖
echo ""
echo "正在安装依赖包..."
pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 依赖安装完成！"
    echo ""
    echo "================================================"
    echo "  使用方法"
    echo "================================================"
    echo ""
    echo "1️⃣  筛选大户地址:"
    echo "   python3 filter_top_traders.py"
    echo ""
    echo "2️⃣  开始监控:"
    echo "   python3 monitor_whales.py"
    echo ""
    echo "================================================"
else
    echo "❌ 依赖安装失败，请手动运行: pip3 install -r requirements.txt"
    exit 1
fi

