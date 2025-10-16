#!/usr/bin/env python3
"""
监控Hyperliquid大户交易活动
基于官方Python SDK实时监听顶级交易者的开仓、平仓行为
"""
import json
import time
from typing import Dict, List, Optional
from collections import defaultdict
from datetime import datetime
from hyperliquid.info import Info
from hyperliquid.utils import constants


class PositionTracker:
    """持仓状态追踪器"""
    
    def __init__(self):
        # 结构: {user_address: {coin: position_size}}
        self.positions: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    
    def process_fill(self, user: str, fill_data: Dict) -> Optional[Dict]:
        """
        处理fill事件并判断交易类型
        
        Args:
            user: 用户地址
            fill_data: fill事件数据
        
        Returns:
            包含交易信息的字典，如果需要通知的话
        """
        coin = fill_data.get('coin')
        side = fill_data.get('side')
        size = float(fill_data.get('sz', 0))
        price = float(fill_data.get('px', 0))
        closed_pnl = float(fill_data.get('closedPnl', 0))
        
        # 计算仓位变化
        # 'B' (买入) = 增加做多仓位, 'S' (卖出) = 增加做空仓位
        delta = size if side == 'B' else -size
        
        old_position = self.positions[user][coin]
        new_position = old_position + delta
        
        # 更新仓位
        self.positions[user][coin] = new_position
        
        # 判断交易类型
        action_type = self._identify_action(old_position, new_position)
        
        return {
            'user': user,
            'coin': coin,
            'action': action_type,
            'side': '买入' if side == 'B' else '卖出',
            'size': size,
            'price': price,
            'old_position': old_position,
            'new_position': new_position,
            'closed_pnl': closed_pnl,
            'timestamp': datetime.now().isoformat()
        }
    
    def _identify_action(self, old_pos: float, new_pos: float) -> str:
        """识别交易行为类型"""
        if abs(old_pos) < 1e-8:  # 原仓位为0
            if abs(new_pos) > 1e-8:
                return "开仓"
            return "无变化"
        
        if abs(new_pos) < 1e-8:  # 新仓位为0
            return "平仓"
        
        # 检查是否反向
        if old_pos * new_pos < 0:
            return "反向开仓"
        
        # 同向但大小变化
        if abs(new_pos) > abs(old_pos):
            return "加仓"
        else:
            return "减仓"


class WhaleMonitor:
    """大户监控器"""
    
    def __init__(self, addresses: List[str], max_addresses: int = 10):
        """
        初始化监控器
        
        Args:
            addresses: 要监控的地址列表
            max_addresses: 最大监控地址数（受限于API限制）
        """
        # Hyperliquid限制: 每个IP最多监控10个用户
        if len(addresses) > max_addresses:
            print(f"⚠️  警告: 提供了{len(addresses)}个地址，但API限制为{max_addresses}个")
            print(f"    仅监控前{max_addresses}个地址\n")
            addresses = addresses[:max_addresses]
        
        self.addresses = addresses
        self.info = Info(constants.MAINNET_API_URL, skip_ws=False)
        self.tracker = PositionTracker()
        
        print(f"🚀 监控器初始化完成")
        print(f"📍 API端点: {constants.MAINNET_API_URL}")
        print(f"👥 监控地址数: {len(self.addresses)}\n")
    
    def start_monitoring(self):
        """开始监控"""
        print(f"{'='*80}")
        print(f"开始监控 {len(self.addresses)} 个大户地址")
        print(f"{'='*80}\n")
        
        for i, addr in enumerate(self.addresses, 1):
            print(f"{i}. {addr}")
        
        print(f"\n{'='*80}")
        print("正在订阅用户事件...")
        print(f"{'='*80}\n")
        
        # 订阅每个地址的用户事件
        for address in self.addresses:
            try:
                self.info.subscribe(
                    {"type": "userEvents", "user": address},
                    lambda data, addr=address: self._handle_user_event(addr, data)
                )
                print(f"✅ 已订阅: {address}")
            except Exception as e:
                print(f"❌ 订阅失败 {address}: {e}")
        
        print(f"\n{'='*80}")
        print("🎯 监控中... (按Ctrl+C停止)")
        print(f"{'='*80}\n")
        
        # 保持运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n停止监控...")
    
    def _handle_user_event(self, user: str, event_data: Dict):
        """处理用户事件"""
        if not event_data or 'data' not in event_data:
            return
        
        data = event_data['data']
        
        # 处理fills事件（成交事件）
        if 'fills' in data:
            fills = data['fills']
            for fill in fills:
                trade_info = self.tracker.process_fill(user, fill)
                if trade_info:
                    self._notify_trade(trade_info)
        
        # 可以处理其他事件类型
        # if 'funding' in data:
        #     self._handle_funding(user, data['funding'])
        # if 'liquidation' in data:
        #     self._handle_liquidation(user, data['liquidation'])
    
    def _notify_trade(self, trade_info: Dict):
        """通知交易事件"""
        action = trade_info['action']
        
        # 只通知关键事件
        if action in ['开仓', '平仓', '反向开仓']:
            symbol = '🟢' if action == '开仓' else '🔴' if action == '平仓' else '🔄'
            
            print(f"{symbol} {action} | {trade_info['timestamp']}")
            print(f"   用户: {trade_info['user'][:10]}...{trade_info['user'][-8:]}")
            print(f"   币种: {trade_info['coin']}")
            print(f"   方向: {trade_info['side']}")
            print(f"   数量: {trade_info['size']}")
            print(f"   价格: ${trade_info['price']:,.2f}")
            print(f"   仓位: {trade_info['old_position']:.4f} → {trade_info['new_position']:.4f}")
            
            if abs(trade_info['closed_pnl']) > 0.01:
                pnl_symbol = '💰' if trade_info['closed_pnl'] > 0 else '📉'
                print(f"   {pnl_symbol} 已实现盈亏: ${trade_info['closed_pnl']:,.2f}")
            
            print()


def load_addresses_from_file(file_path: str = "top_traders_addresses.json") -> List[str]:
    """从文件加载地址列表"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('addresses', [])
    except FileNotFoundError:
        print(f"❌ 未找到文件: {file_path}")
        print("   请先运行 filter_top_traders.py 生成地址列表")
        return []


if __name__ == "__main__":
    # 从文件加载地址
    addresses = load_addresses_from_file()
    
    if not addresses:
        print("没有找到监控地址，退出...")
        exit(1)
    
    # 创建并启动监控器
    monitor = WhaleMonitor(addresses, max_addresses=10)
    monitor.start_monitoring()

