#!/usr/bin/env python3
"""
演示脚本：展示如何使用监控系统
不需要实际连接WebSocket，仅展示数据处理流程
"""
import json
from filter_top_traders import get_top_traders, load_leaderboard, filter_positive_pnl_traders


def demo_filter_traders():
    """演示筛选交易者功能"""
    print("\n" + "="*80)
    print("演示 1: 筛选不同时间窗口的交易者")
    print("="*80 + "\n")
    
    time_windows = ['day', 'week', 'month', 'allTime']
    
    for window in time_windows:
        print(f"\n{'='*60}")
        print(f"时间窗口: {window}")
        print(f"{'='*60}\n")
        
        traders = load_leaderboard()
        positive_traders = filter_positive_pnl_traders(traders, window)
        
        print(f"正收益交易者数量: {len(positive_traders)}")
        
        if positive_traders:
            top3 = positive_traders[:3]
            print(f"\n前3名:")
            for i, trader in enumerate(top3, 1):
                print(f"  {i}. {trader['ethAddress'][:10]}... | "
                      f"PnL: ${trader['pnl']:,.2f} | "
                      f"ROI: {trader['roi']*100:.2f}%")


def demo_position_tracking():
    """演示仓位追踪逻辑"""
    print("\n" + "="*80)
    print("演示 2: 仓位状态追踪")
    print("="*80 + "\n")
    
    # 模拟交易序列
    trades = [
        {'coin': 'BTC', 'side': 'B', 'sz': '1.0', 'px': '67000', 'closedPnl': '0'},
        {'coin': 'BTC', 'side': 'B', 'sz': '0.5', 'px': '67500', 'closedPnl': '0'},
        {'coin': 'BTC', 'side': 'S', 'sz': '0.5', 'px': '68000', 'closedPnl': '250'},
        {'coin': 'BTC', 'side': 'S', 'sz': '1.0', 'px': '68500', 'closedPnl': '1500'},
        {'coin': 'BTC', 'side': 'S', 'sz': '1.0', 'px': '68000', 'closedPnl': '0'},
        {'coin': 'BTC', 'side': 'B', 'sz': '1.0', 'px': '67500', 'closedPnl': '500'},
    ]
    
    position = 0.0
    
    print("交易序列模拟:\n")
    for i, trade in enumerate(trades, 1):
        old_pos = position
        delta = float(trade['sz']) if trade['side'] == 'B' else -float(trade['sz'])
        position += delta
        
        action = determine_action(old_pos, position)
        
        print(f"交易 #{i}:")
        print(f"  币种: {trade['coin']}")
        print(f"  方向: {'买入' if trade['side'] == 'B' else '卖出'}")
        print(f"  数量: {trade['sz']}")
        print(f"  价格: ${float(trade['px']):,.2f}")
        print(f"  仓位: {old_pos:.1f} → {position:.1f}")
        print(f"  行为: {action}")
        if float(trade['closedPnl']) != 0:
            print(f"  已实现盈亏: ${float(trade['closedPnl']):,.2f}")
        print()


def determine_action(old_pos: float, new_pos: float) -> str:
    """判断交易类型"""
    if abs(old_pos) < 1e-8:
        if abs(new_pos) > 1e-8:
            return "🟢 开仓"
        return "无变化"
    
    if abs(new_pos) < 1e-8:
        return "🔴 平仓"
    
    if old_pos * new_pos < 0:
        return "🔄 反向开仓"
    
    if abs(new_pos) > abs(old_pos):
        return "⬆️ 加仓"
    else:
        return "⬇️ 减仓"


def demo_data_structure():
    """演示数据结构"""
    print("\n" + "="*80)
    print("演示 3: 数据结构说明")
    print("="*80 + "\n")
    
    print("1. Leaderboard 数据结构:")
    print("-" * 60)
    sample_trader = {
        "ethAddress": "0x1234...5678",
        "accountValue": "1000000.00",
        "windowPerformances": [
            ["allTime", {
                "pnl": "500000.00",
                "roi": "1.0",
                "vlm": "10000000.00"
            }]
        ],
        "displayName": "Whale Trader"
    }
    print(json.dumps(sample_trader, indent=2))
    
    print("\n2. Fill 事件数据结构:")
    print("-" * 60)
    sample_fill = {
        "coin": "BTC",
        "px": "67890.00",
        "sz": "1.5",
        "side": "B",
        "startPosition": "0.0",
        "closedPnl": "0.0"
    }
    print(json.dumps(sample_fill, indent=2))
    
    print("\n3. 处理后的交易信息:")
    print("-" * 60)
    sample_trade = {
        "user": "0x1234...5678",
        "coin": "BTC",
        "action": "开仓",
        "side": "买入",
        "size": 1.5,
        "price": 67890.00,
        "old_position": 0.0,
        "new_position": 1.5,
        "closed_pnl": 0.0,
        "timestamp": "2025-10-15T14:30:25"
    }
    print(json.dumps(sample_trade, indent=2, ensure_ascii=False))


def demo_config_options():
    """演示配置选项"""
    print("\n" + "="*80)
    print("演示 4: 配置选项说明")
    print("="*80 + "\n")
    
    print("筛选配置 (filter_top_traders.py):")
    print("-" * 60)
    print("• top_n: 筛选前N名 (建议10以内)")
    print("• time_window: 时间窗口")
    print("  - 'day': 当日收益")
    print("  - 'week': 本周收益")
    print("  - 'month': 本月收益")
    print("  - 'allTime': 历史总收益 (推荐)")
    
    print("\n监控配置 (jsons/config.json):")
    print("-" * 60)
    print("• notify_on_open: 开仓时通知 (默认: true)")
    print("• notify_on_close: 平仓时通知 (默认: true)")
    print("• notify_on_reverse: 反向开仓时通知 (默认: true)")
    print("• notify_on_add: 加仓时通知 (默认: false)")
    print("• notify_on_reduce: 减仓时通知 (默认: false)")
    print("• min_position_size: 最小仓位阈值 (默认: 0)")


def main():
    """主函数"""
    print("\n" + "="*80)
    print("  Hyperliquid 大户交易监控系统 - 功能演示")
    print("="*80)
    
    try:
        # 演示1: 筛选交易者
        demo_filter_traders()
        
        # 演示2: 仓位追踪
        demo_position_tracking()
        
        # 演示3: 数据结构
        demo_data_structure()
        
        # 演示4: 配置选项
        demo_config_options()
        
        print("\n" + "="*80)
        print("演示完成！")
        print("="*80)
        print("\n下一步:")
        print("1. 运行 python3 filter_top_traders.py 筛选大户地址")
        print("2. 运行 python3 monitor_whales.py 开始实时监控")
        print("\n提示: 监控功能需要安装 hyperliquid-python-sdk")
        print("      pip3 install hyperliquid-python-sdk")
        print()
        
    except FileNotFoundError:
        print("\n⚠️  未找到 jsons/leaderboard.json 文件")
        print("请先下载排行榜数据:")
        print("curl -o jsons/leaderboard.json https://stats-data.hyperliquid.xyz/Mainnet/leaderboard")
        print()


if __name__ == "__main__":
    main()

