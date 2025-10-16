#!/usr/bin/env python3
"""
监控Hyperliquid大户交易活动 V2
支持配置文件、日志记录等高级功能
"""
import json
import time
import logging
from typing import Dict, List, Optional
from collections import defaultdict
from datetime import datetime
from pathlib import Path


# 配置日志
def setup_logging(log_file: str = None):
    """设置日志"""
    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
        handlers=handlers
    )


class Config:
    """配置管理器"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self) -> dict:
        """加载配置文件"""
        if not Path(self.config_file).exists():
            logging.warning(f"配置文件 {self.config_file} 不存在，使用默认配置")
            return self.get_default_config()
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            return self.get_default_config()
    
    @staticmethod
    def get_default_config() -> dict:
        """默认配置"""
        return {
            "filter": {
                "top_n": 10,
                "time_window": "allTime"
            },
            "monitor": {
                "max_addresses": 10,
                "notify_on_open": True,
                "notify_on_close": True,
                "notify_on_reverse": True,
                "notify_on_add": False,
                "notify_on_reduce": False,
                "min_position_size": 0
            },
            "notification": {
                "console": True,
                "log_file": "trades.log"
            }
        }
    
    def get(self, *keys, default=None):
        """获取配置值"""
        value = self.config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, default)
            else:
                return default
        return value


class PositionTracker:
    """持仓状态追踪器"""
    
    def __init__(self, config: Config):
        self.config = config
        # 结构: {user_address: {coin: position_size}}
        self.positions: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    
    def process_fill(self, user: str, fill_data: Dict) -> Optional[Dict]:
        """处理fill事件并判断交易类型"""
        coin = fill_data.get('coin')
        side = fill_data.get('side')
        size = float(fill_data.get('sz', 0))
        price = float(fill_data.get('px', 0))
        closed_pnl = float(fill_data.get('closedPnl', 0))
        
        # 计算仓位变化
        delta = size if side == 'B' else -size
        
        old_position = self.positions[user][coin]
        new_position = old_position + delta
        
        # 更新仓位
        self.positions[user][coin] = new_position
        
        # 判断交易类型
        action_type = self._identify_action(old_position, new_position)
        
        # 检查是否需要通知
        if not self._should_notify(action_type, size):
            return None
        
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
    
    def _should_notify(self, action: str, size: float) -> bool:
        """检查是否应该通知此事件"""
        monitor_config = self.config.get('monitor', default={})
        
        # 检查仓位大小阈值
        min_size = monitor_config.get('min_position_size', 0)
        if size < min_size:
            return False
        
        # 检查事件类型过滤
        action_map = {
            "开仓": monitor_config.get('notify_on_open', True),
            "平仓": monitor_config.get('notify_on_close', True),
            "反向开仓": monitor_config.get('notify_on_reverse', True),
            "加仓": monitor_config.get('notify_on_add', False),
            "减仓": monitor_config.get('notify_on_reduce', False)
        }
        
        return action_map.get(action, False)


class WhaleMonitor:
    """大户监控器 V2"""
    
    def __init__(self, addresses: List[str], config: Config):
        """初始化监控器"""
        self.config = config
        
        # 限制地址数量
        max_addresses = config.get('monitor', 'max_addresses', default=10)
        if len(addresses) > max_addresses:
            logging.warning(f"提供了{len(addresses)}个地址，但API限制为{max_addresses}个")
            logging.warning(f"仅监控前{max_addresses}个地址")
            addresses = addresses[:max_addresses]
        
        self.addresses = addresses
        self.tracker = PositionTracker(config)
        
        # 尝试导入SDK
        try:
            from hyperliquid.info import Info
            from hyperliquid.utils import constants
            self.info = Info(constants.MAINNET_API_URL, skip_ws=False)
            self.sdk_available = True
        except ImportError:
            logging.error("未找到 hyperliquid-python-sdk")
            logging.error("请运行: pip3 install hyperliquid-python-sdk")
            self.sdk_available = False
        
        logging.info(f"监控器初始化完成，监控 {len(self.addresses)} 个地址")
    
    def start_monitoring(self):
        """开始监控"""
        if not self.sdk_available:
            logging.error("SDK不可用，无法启动监控")
            return
        
        print(f"\n{'='*80}")
        print(f"开始监控 {len(self.addresses)} 个大户地址")
        print(f"{'='*80}\n")
        
        for i, addr in enumerate(self.addresses, 1):
            print(f"{i}. {addr}")
        
        print(f"\n{'='*80}")
        print("正在订阅用户事件...")
        print(f"{'='*80}\n")
        
        # 订阅每个地址的用户事件
        success_count = 0
        for address in self.addresses:
            try:
                self.info.subscribe(
                    {"type": "userEvents", "user": address},
                    lambda data, addr=address: self._handle_user_event(addr, data)
                )
                logging.info(f"✅ 已订阅: {address}")
                success_count += 1
            except Exception as e:
                logging.error(f"❌ 订阅失败 {address}: {e}")
        
        if success_count == 0:
            logging.error("没有成功订阅任何地址，退出...")
            return
        
        print(f"\n{'='*80}")
        print(f"🎯 监控中... 成功订阅 {success_count}/{len(self.addresses)} 个地址")
        print(f"{'='*80}\n")
        
        # 保持运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("\n停止监控...")
    
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
    
    def _notify_trade(self, trade_info: Dict):
        """通知交易事件"""
        action = trade_info['action']
        
        # 控制台输出
        if self.config.get('notification', 'console', default=True):
            symbol = {
                '开仓': '🟢',
                '平仓': '🔴',
                '反向开仓': '🔄',
                '加仓': '⬆️',
                '减仓': '⬇️'
            }.get(action, '📊')
            
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
        
        # 日志记录
        log_file = self.config.get('notification', 'log_file')
        if log_file:
            logging.info(
                f"{action} | {trade_info['user']} | {trade_info['coin']} | "
                f"{trade_info['side']} {trade_info['size']} @ ${trade_info['price']:.2f} | "
                f"PnL: ${trade_info['closed_pnl']:.2f}"
            )


def load_addresses_from_file(file_path: str = "top_traders_addresses.json") -> List[str]:
    """从文件加载地址列表"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('addresses', [])
    except FileNotFoundError:
        logging.error(f"未找到文件: {file_path}")
        logging.error("请先运行 filter_top_traders.py 生成地址列表")
        return []


if __name__ == "__main__":
    # 加载配置
    config = Config()
    
    # 设置日志
    log_file = config.get('notification', 'log_file')
    setup_logging(log_file)
    
    # 从文件加载地址
    addresses = load_addresses_from_file()
    
    if not addresses:
        logging.error("没有找到监控地址，退出...")
        exit(1)
    
    # 创建并启动监控器
    monitor = WhaleMonitor(addresses, config)
    monitor.start_monitoring()

