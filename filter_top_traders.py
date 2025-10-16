#!/usr/bin/env python3
"""
从leaderboard.json中提取正收益前10名交易者的地址
"""
import json
from typing import List, Dict, Any


def load_leaderboard(file_path: str = "leaderboard.json") -> List[Dict[str, Any]]:
    """加载leaderboard数据"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('leaderboardRows', [])


def filter_positive_pnl_traders(traders: List[Dict[str, Any]], time_window: str = "allTime") -> List[Dict[str, Any]]:
    """
    过滤正收益的交易者
    
    Args:
        traders: 交易者列表
        time_window: 时间窗口 ('day', 'week', 'month', 'allTime')
    
    Returns:
        过滤后的交易者列表，按收益降序排列
    """
    positive_traders = []
    
    for trader in traders:
        # 获取指定时间窗口的性能数据
        window_perfs = dict(trader.get('windowPerformances', []))
        perf = window_perfs.get(time_window, {})
        
        pnl = float(perf.get('pnl', 0))
        
        # 只保留正收益的交易者
        if pnl > 0:
            trader_info = {
                'ethAddress': trader['ethAddress'],
                'accountValue': float(trader.get('accountValue', 0)),
                'pnl': pnl,
                'roi': float(perf.get('roi', 0)),
                'vlm': float(perf.get('vlm', 0)),
                'displayName': trader.get('displayName')
            }
            positive_traders.append(trader_info)
    
    # 按收益降序排列
    positive_traders.sort(key=lambda x: x['pnl'], reverse=True)
    
    return positive_traders


def get_top_traders(top_n: int = 10, time_window: str = "allTime") -> List[str]:
    """
    获取收益前N名的交易者地址
    
    Args:
        top_n: 返回前N名
        time_window: 时间窗口 ('day', 'week', 'month', 'allTime')
    
    Returns:
        交易者地址列表
    """
    traders = load_leaderboard()
    positive_traders = filter_positive_pnl_traders(traders, time_window)
    
    top_traders = positive_traders[:top_n]
    
    # 打印详细信息
    print(f"\n{'='*80}")
    print(f"正收益前{top_n}名交易者 (时间窗口: {time_window})")
    print(f"{'='*80}\n")
    
    for i, trader in enumerate(top_traders, 1):
        print(f"排名 #{i}")
        print(f"  地址: {trader['ethAddress']}")
        print(f"  账户价值: ${trader['accountValue']:,.2f}")
        print(f"  盈亏 (PnL): ${trader['pnl']:,.2f}")
        print(f"  收益率 (ROI): {trader['roi']*100:.2f}%")
        print(f"  交易量: ${trader['vlm']:,.2f}")
        if trader['displayName']:
            print(f"  显示名: {trader['displayName']}")
        print()
    
    # 保存地址列表到文件
    addresses = [trader['ethAddress'] for trader in top_traders]
    with open('top_traders_addresses.json', 'w', encoding='utf-8') as f:
        json.dump({
            'time_window': time_window,
            'addresses': addresses,
            'details': top_traders
        }, f, indent=2, ensure_ascii=False)
    
    print(f"地址列表已保存到: top_traders_addresses.json")
    
    return addresses


if __name__ == "__main__":
    # 可以选择不同的时间窗口: 'day', 'week', 'month', 'allTime'
    addresses = get_top_traders(top_n=10, time_window="allTime")
    
    print(f"\n{'='*80}")
    print("监控地址列表:")
    print(f"{'='*80}")
    for addr in addresses:
        print(addr)

