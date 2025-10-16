#!/bin/bash

echo "================================================"
echo "  启动 Hyperliquid 大户交易监控"
echo "================================================"
echo ""

# 检查地址文件是否存在
if [ ! -f "top_traders_addresses.json" ]; then
    echo "⚠️  未找到地址列表文件，正在筛选..."
    python3 filter_top_traders.py
    echo ""
fi

# 启动监控
echo "🚀 启动监控程序..."
echo ""
python3 monitor_whales.py

