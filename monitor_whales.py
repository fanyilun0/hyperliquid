#!/usr/bin/env python3
"""
监控Hyperliquid大户交易活动 V2
支持配置文件、日志记录等高级功能
"""
import json
import time
import logging
import os
from typing import Dict, List, Optional
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# 导入持仓管理器
from position_manager import PositionManager


# 配置日志
def setup_logging(log_file: str = None, debug: bool = False):
    """设置日志
    
    Args:
        log_file: 日志文件路径（如果为空，自动生成到logs目录）
        debug: 是否启用DEBUG级别日志
    
    Returns:
        实际使用的日志文件路径
    """
    handlers = [logging.StreamHandler()]
    
    # 如果没有指定日志文件，使用时间戳生成
    if not log_file:
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = str(logs_dir / f"{timestamp}.log")
    else:
        # 如果指定了日志文件，确保目录存在
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
    
    log_level = logging.DEBUG if debug else logging.INFO
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s | %(levelname)s | %(message)s',
        handlers=handlers,
        force=True  # 强制重新配置，即使已经配置过
    )
    
    if debug:
        logging.info("DEBUG模式已启用")
    
    return log_file


class Config:
    """配置管理器"""
    
    def __init__(self, config_file: str = "jsons/config.json"):
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
                "notify_on_add": True,
                "notify_on_reduce": True,
                "min_position_size": 0
            },
            "notification": {
                "console": True,
                "log_file": "trades.log"
            },
            "debug": False
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
        # 结构: {user_address: {coin: {'entry_px': float, 'unrealized_pnl': float}}}
        self.position_details: Dict[str, Dict[str, Dict]] = defaultdict(lambda: defaultdict(dict))
    
    def init_positions_from_state(self, user: str, user_state: Dict):
        """从用户状态初始化仓位信息
        
        Args:
            user: 用户地址
            user_state: 用户状态数据（来自 /info userState 接口）
        """
        if not user_state or 'assetPositions' not in user_state:
            return
        
        asset_positions = user_state.get('assetPositions', [])
        for position in asset_positions:
            try:
                coin = position.get('position', {}).get('coin')
                szi = position.get('position', {}).get('szi')
                entry_px = position.get('position', {}).get('entryPx')
                unrealized_pnl = position.get('position', {}).get('unrealizedPnl')
                
                if coin and szi:
                    size = float(szi)
                    self.positions[user][coin] = size
                    
                    # 保存详细信息
                    self.position_details[user][coin] = {
                        'entry_px': float(entry_px) if entry_px else 0,
                        'unrealized_pnl': float(unrealized_pnl) if unrealized_pnl else 0
                    }
                    
                    logging.debug(
                        f"初始化仓位: {user[:8]}... | {coin} | "
                        f"仓位: {size:,.4f} | 入场价: ${float(entry_px) if entry_px else 0:,.4f} | "
                        f"未实现盈亏: ${float(unrealized_pnl) if unrealized_pnl else 0:,.2f}"
                    )
            except Exception as e:
                logging.debug(f"解析仓位数据失败: {e}, 数据: {position}")
    
    def process_fill(self, user: str, fill_data: Dict) -> Optional[Dict]:
        """处理fill事件并判断交易类型
        
        根据 Hyperliquid API 文档:
        - side 'B' = Bid (买入/做多)
        - side 'A' = Ask (卖出/做空)
        - closedPnl: 此次成交产生的已实现盈亏
        - startPosition: 交易前的仓位（SDK提供的字段）
        """
        coin = fill_data.get('coin')
        side = fill_data.get('side')
        size = float(fill_data.get('sz', 0))
        price = float(fill_data.get('px', 0))
        closed_pnl = float(fill_data.get('closedPnl', 0))
        start_position = fill_data.get('startPosition')  # 交易前仓位
        dir_field = fill_data.get('dir')  # 方向描述，如 "Open Long", "Close Short"
        
        # 计算仓位变化
        # 'B' (Bid/买入) = 增加做多仓位, 'A' (Ask/卖出) = 减少仓位(或增加做空)
        delta = size if side == 'B' else -size
        
        old_position = self.positions[user][coin]
        
        # 如果SDK提供了startPosition，优先使用（更准确）
        if start_position is not None:
            try:
                old_position = float(start_position)
                # 同步更新我们的追踪
                self.positions[user][coin] = old_position
            except (ValueError, TypeError):
                pass
        
        new_position = old_position + delta
        
        # 更新仓位
        self.positions[user][coin] = new_position
        
        # 判断交易类型
        action_type = self._identify_action(old_position, new_position)
        
        # 检查是否需要通知
        if not self._should_notify(action_type, size):
            return None
        
        # 判断交易方向的文字描述
        if side == 'B':
            side_text = '买入 (Bid)'
        elif side == 'A':
            side_text = '卖出 (Ask)'
        else:
            side_text = f'未知 ({side})'
        
        # 获取仓位详细信息（如果有）
        position_detail = self.position_details[user].get(coin, {})
        entry_px = position_detail.get('entry_px', 0)
        unrealized_pnl = position_detail.get('unrealized_pnl', 0)
        
        return {
            'user': user,
            'coin': coin,
            'action': action_type,
            'side': side_text,
            'size': size,
            'price': price,
            'old_position': old_position,
            'new_position': new_position,
            'closed_pnl': closed_pnl,
            'entry_px': entry_px,
            'unrealized_pnl': unrealized_pnl,
            'dir_field': dir_field,  # 原始方向字段
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
        
        # 检查仓位大小阈值（修复：只有当设置了阈值且大于0时才过滤）
        min_size = monitor_config.get('min_position_size', 0)
        if min_size > 0 and size < min_size:
            logging.debug(f"交易大小 {size} 小于最小阈值 {min_size}，已过滤")
            return False
        
        # 检查事件类型过滤
        action_map = {
            "开仓": monitor_config.get('notify_on_open', True),
            "平仓": monitor_config.get('notify_on_close', True),
            "反向开仓": monitor_config.get('notify_on_reverse', True),
            "加仓": monitor_config.get('notify_on_add', False),
            "减仓": monitor_config.get('notify_on_reduce', False)
        }
        
        should_notify = action_map.get(action, False)
        if not should_notify:
            logging.debug(f"交易类型 '{action}' 不在通知范围内，已过滤")
        
        return should_notify


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
            self.Info = Info
            self.constants = constants
            self.sdk_available = True
            logging.debug("SDK导入成功")
        except ImportError:
            logging.error("未找到 hyperliquid-python-sdk")
            logging.error("请运行: pip3 install hyperliquid-python-sdk")
            self.sdk_available = False
        
        # 为每个用户创建独立的Info实例（解决多用户订阅问题）
        self.info_instances = {}
        
        # 资产名称缓存 {asset_id: coin_name}
        self.asset_name_cache = {}
        
        logging.info(f"监控器初始化完成，监控 {len(self.addresses)} 个地址")
    
    def _get_coin_name(self, coin_id: str) -> str:
        """获取币种名称
        
        Args:
            coin_id: 币种ID，可能是 '@107' 这样的资产ID或直接的币种名称
        
        Returns:
            币种名称
        """
        # 如果不是以@开头，说明已经是币种名称
        if not coin_id.startswith('@'):
            return coin_id
        
        # 检查缓存
        if coin_id in self.asset_name_cache:
            return self.asset_name_cache[coin_id]
        
        # 尝试通过API获取资产信息
        try:
            if hasattr(self, 'Info') and self.info_instances:
                # 使用任意一个info实例获取元数据
                info = list(self.info_instances.values())[0]
                meta = info.meta()
                
                # 查找资产ID对应的币种名称
                asset_id = int(coin_id[1:])  # 去掉@符号并转为整数
                
                # 在universe中查找
                if 'universe' in meta:
                    for asset in meta['universe']:
                        if asset.get('index') == asset_id or asset.get('name') == coin_id:
                            coin_name = asset.get('name', coin_id)
                            self.asset_name_cache[coin_id] = coin_name
                            return coin_name
                
                # 在spot元数据中查找
                spot_meta = info.spot_meta()
                if 'universe' in spot_meta:
                    for asset in spot_meta['universe']:
                        if asset.get('index') == asset_id:
                            coin_name = asset.get('name', coin_id)
                            self.asset_name_cache[coin_id] = coin_name
                            return coin_name
        except Exception as e:
            logging.debug(f"获取资产名称失败: {e}")
        
        # 如果无法获取，返回原始ID
        return coin_id
    
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
        
        # 获取初始仓位信息并生成positions.log
        print(f"\n{'='*80}")
        print("正在获取用户初始仓位信息...")
        print(f"{'='*80}\n")
        
        # 创建持仓管理器
        position_manager = PositionManager(self.Info, self.constants)
        
        # 获取所有地址的持仓并生成HTML报告
        all_positions = position_manager.fetch_and_log_positions(self.addresses)
        
        # 初始化追踪器的仓位数据
        for address, positions in all_positions.items():
            if not positions:
                continue
            
            # 为追踪器构造 user_state 格式的数据
            user_state = {
                'assetPositions': [
                    {
                        'position': {
                            'coin': pos['coin'],
                            'szi': str(pos['raw_szi']),
                            'entryPx': str(pos['entry_px']),
                            'unrealizedPnl': str(pos['unrealized_pnl'])
                        }
                    }
                    for pos in positions
                ]
            }
            self.tracker.init_positions_from_state(address, user_state)
        
        print(f"\n{'='*80}")
        print("正在订阅用户事件...")
        print(f"{'='*80}\n")
        
        # WebSocket连接状态检查
        logging.debug(f"准备为 {len(self.addresses)} 个地址创建独立连接...")
        
        # 为每个地址创建独立的Info实例并订阅
        success_count = 0
        failed_addresses = []
        
        for idx, address in enumerate(self.addresses, 1):
            logging.debug(f"[{idx}/{len(self.addresses)}] 准备订阅地址: {address}")
            
            try:
                # 为每个用户创建独立的WebSocket连接
                logging.debug(f"创建独立的Info实例...")
                info = self.Info(self.constants.MAINNET_API_URL, skip_ws=False)
                
                # 保存Info实例
                self.info_instances[address] = info
                
                # 创建订阅配置
                subscription = {"type": "userEvents", "user": address}
                logging.debug(f"订阅配置: {subscription}")
                
                # 执行订阅
                info.subscribe(
                    subscription,
                    lambda data, addr=address: self._handle_user_event(addr, data)
                )
                
                logging.info(f"✅ 已订阅 [{idx}/{len(self.addresses)}]: {address}")
                success_count += 1
                
                # 添加短暂延迟，避免连接创建过快
                time.sleep(0.2)
                
            except Exception as e:
                error_msg = str(e)
                logging.error(f"❌ 订阅失败 [{idx}/{len(self.addresses)}] {address}: {error_msg}")
                logging.debug(f"详细错误信息: ", exc_info=True)
                failed_addresses.append(address)
        
        # 输出订阅总结
        print(f"\n{'='*80}")
        print(f"📊 订阅总结")
        print(f"{'='*80}")
        print(f"✅ 成功: {success_count}/{len(self.addresses)}")
        if failed_addresses:
            print(f"❌ 失败: {len(failed_addresses)}/{len(self.addresses)}")
            logging.warning(f"失败地址列表: {failed_addresses}")
        print(f"{'='*80}\n")
        
        if success_count == 0:
            logging.error("没有成功订阅任何地址，退出...")
            return
        
        print(f"🎯 监控中... (按Ctrl+C停止)\n")
        
        # 保持运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("\n停止监控...")
    
    def _handle_user_event(self, user: str, event_data: Dict):
        """处理用户事件"""
        logging.debug(f"📨 收到用户事件 - 用户: {user}")
        logging.debug(f"📋 事件数据结构: {list(event_data.keys()) if event_data else 'None'}")
        
        if not event_data or 'data' not in event_data:
            logging.debug("⚠️  事件数据为空或缺少'data'字段，跳过")
            return
        
        data = event_data['data']
        logging.debug(f"📦 数据内容类型: {list(data.keys()) if isinstance(data, dict) else type(data)}")
        
        # 处理fills事件（成交事件）
        if 'fills' in data:
            fills = data['fills']
            logging.debug(f"✅ 收到 {len(fills)} 个fill事件")
            
            for idx, fill in enumerate(fills, 1):
                coin_raw = fill.get('coin')
                side = fill.get('side')
                size = fill.get('sz')
                
                # 转换side显示
                side_display = '买入(B)' if side == 'B' else '卖出(A)' if side == 'A' else side
                
                logging.debug(
                    f"🔍 处理第 {idx}/{len(fills)} 个fill - "
                    f"币种: {coin_raw}, 方向: {side_display}, 数量: {size}"
                )
                
                trade_info = self.tracker.process_fill(user, fill)
                if trade_info:
                    logging.debug(f"✨ 交易信息已生成: {trade_info['action']}")
                    self._notify_trade(trade_info)
                else:
                    logging.debug(f"🔇 交易不满足通知条件，已过滤")
        else:
            logging.debug(f"ℹ️  事件中没有fills数据，可能是其他类型事件")
    
    def _notify_trade(self, trade_info: Dict):
        """通知交易事件"""
        action = trade_info['action']
        
        # 获取币种名称（转换@ID格式）
        coin_name = self._get_coin_name(trade_info['coin'])
        
        # 控制台输出
        if self.config.get('notification', 'console', default=True):
            # 行为符号
            action_symbols = {
                '开仓': '🟢',
                '平仓': '🔴',
                '反向开仓': '🔄',
                '加仓': '⬆️',
                '减仓': '⬇️'
            }
            symbol = action_symbols.get(action, '📊')
            
            # 分隔线
            print(f"\n{'━' * 80}")
            
            # 标题行 - 更醒目
            print(f"{symbol}  {action.upper()}")
            
            # 添加原始方向字段（如果有）
            if trade_info.get('dir_field'):
                print(f"    ({trade_info['dir_field']})")
            
            # 时间戳
            timestamp = trade_info['timestamp'].replace('T', ' ')
            print(f"⏰ 时间: {timestamp}")
            
            # 用户地址 - 显示完整地址
            user_addr = trade_info['user']
            print(f"👤 用户: {user_addr}")
            
            # 交易详情
            print(f"💎 币种: {coin_name}")
            print(f"📊 方向: {trade_info['side']}")
            print(f"📈 数量: {trade_info['size']:,.4f}")
            print(f"💵 价格: ${trade_info['price']:,.4f}")
            
            # 仓位变化
            old_pos = trade_info['old_position']
            new_pos = trade_info['new_position']
            pos_change = new_pos - old_pos
            pos_arrow = "📈" if pos_change > 0 else "📉"
            print(f"{pos_arrow} 仓位: {old_pos:,.4f} → {new_pos:,.4f} (变化: {pos_change:+,.4f})")
            
            # 入场价（如果有）
            if trade_info.get('entry_px', 0) > 0:
                entry_px = trade_info['entry_px']
                print(f"🎯 入场价: ${entry_px:,.4f}")
            
            # 已实现盈亏
            closed_pnl = trade_info.get('closed_pnl', 0)
            if abs(closed_pnl) > 0.01:
                pnl_symbol = '💰' if closed_pnl > 0 else '💸'
                pnl_status = '盈利' if closed_pnl > 0 else '亏损'
                print(f"{pnl_symbol} 本次已实现盈亏: ${closed_pnl:,.2f} ({pnl_status})")
            
            # 未实现盈亏（如果有）
            unrealized_pnl = trade_info.get('unrealized_pnl', 0)
            if abs(unrealized_pnl) > 0.01:
                upnl_symbol = '📊' if unrealized_pnl > 0 else '📉'
                upnl_status = '浮盈' if unrealized_pnl > 0 else '浮亏'
                print(f"{upnl_symbol} 剩余持仓未实现盈亏: ${unrealized_pnl:,.2f} ({upnl_status})")
            
            # 底部分隔线
            print(f"{'━' * 80}\n")
        
        # 日志记录
        log_file = self.config.get('notification', 'log_file')
        if log_file:
            # 构建盈亏信息
            pnl_info = f"已实现: ${trade_info.get('closed_pnl', 0):,.2f}"
            if abs(trade_info.get('unrealized_pnl', 0)) > 0.01:
                pnl_info += f", 未实现: ${trade_info.get('unrealized_pnl', 0):,.2f}"
            
            dir_field = f" ({trade_info.get('dir_field', '')})" if trade_info.get('dir_field') else ""
            
            logging.info(
                f"{action}{dir_field} | {trade_info['user']} | {coin_name} | "
                f"{trade_info['side']} {trade_info['size']:,.4f} @ ${trade_info['price']:,.4f} | "
                f"仓位: {trade_info['old_position']:,.4f} → {trade_info['new_position']:,.4f} | "
                f"{pnl_info}"
            )


class AddressFilter:
    """地址过滤器 - 用于跳过特定地址"""
    
    def __init__(self, filter_file: str = "jsons/address_filters.json"):
        self.filter_file = filter_file
        self.filters = self.load_filters()
    
    def load_filters(self) -> dict:
        """加载过滤配置"""
        if not Path(self.filter_file).exists():
            logging.info(f"过滤配置文件 {self.filter_file} 不存在，不应用任何过滤")
            return {
                'blocked_addresses': [],
                'blocked_display_names': [],
                'blocked_keywords': []
            }
        
        try:
            with open(self.filter_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            filters = data.get('filters', {})
            logging.info(f"✅ 已加载地址过滤配置: {self.filter_file}")
            logging.info(f"   - 屏蔽地址: {len(filters.get('blocked_addresses', []))} 个")
            logging.info(f"   - 屏蔽显示名: {len(filters.get('blocked_display_names', []))} 个")
            logging.info(f"   - 屏蔽关键词: {len(filters.get('blocked_keywords', []))} 个")
            return filters
        except Exception as e:
            logging.error(f"加载过滤配置失败: {e}")
            return {
                'blocked_addresses': [],
                'blocked_display_names': [],
                'blocked_keywords': []
            }
    
    def is_blocked(self, address: str, display_name: str = None) -> tuple[bool, str]:
        """检查地址是否被屏蔽
        
        Args:
            address: 地址
            display_name: 显示名称
        
        Returns:
            (是否屏蔽, 屏蔽原因)
        """
        # 检查地址黑名单
        blocked_addresses = self.filters.get('blocked_addresses', [])
        if address.lower() in [addr.lower() for addr in blocked_addresses]:
            return True, "地址在黑名单中"
        
        # 如果没有显示名称，不检查名称过滤
        if not display_name:
            return False, ""
        
        # 检查显示名称完全匹配
        blocked_names = self.filters.get('blocked_display_names', [])
        if display_name in blocked_names:
            return True, f"显示名称 '{display_name}' 在黑名单中"
        
        # 检查关键词（不区分大小写）
        blocked_keywords = self.filters.get('blocked_keywords', [])
        display_name_lower = display_name.lower()
        for keyword in blocked_keywords:
            if keyword.lower() in display_name_lower:
                return True, f"显示名称包含关键词 '{keyword}'"
        
        return False, ""


def load_addresses_from_file(file_path: str = "jsons/top_traders_addresses.json", 
                             apply_filter: bool = True) -> List[Dict]:
    """从文件加载地址列表，支持过滤
    
    Args:
        file_path: 地址文件路径
        apply_filter: 是否应用过滤规则
    
    Returns:
        地址信息列表 [{'address': str, 'display_name': str, 'blocked': bool}, ...]
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        addresses = data.get('addresses', [])
        details = data.get('details', [])
        
        # 构建地址详情映射
        address_map = {}
        for detail in details:
            addr = detail.get('ethAddress')
            if addr:
                address_map[addr.lower()] = {
                    'address': addr,
                    'display_name': detail.get('displayName'),
                    'blocked': detail.get('block', False),
                    'pnl': detail.get('pnl', 0),
                    'vlm': detail.get('vlm', 0)
                }
        
        # 构建结果列表
        result = []
        for addr in addresses:
            addr_lower = addr.lower()
            if addr_lower in address_map:
                result.append(address_map[addr_lower])
            else:
                result.append({
                    'address': addr,
                    'display_name': None,
                    'blocked': False,
                    'pnl': 0,
                    'vlm': 0
                })
        
        return result
        
    except FileNotFoundError:
        logging.error(f"未找到文件: {file_path}")
        logging.error("请先运行 filter_top_traders.py 生成地址列表")
        return []
    except Exception as e:
        logging.error(f"加载地址文件失败: {e}")
        return []


if __name__ == "__main__":
    # 加载配置
    config = Config()
    
    # 设置日志（使用时间戳文件名）
    debug_mode = config.get('debug', default=False)
    
    # 生成日志文件路径
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = str(logs_dir / f"{timestamp}.log")
    
    # 如果配置中指定了日志文件，使用配置的路径
    config_log_file = config.get('notification', 'log_file')
    if config_log_file:
        # 检查是否是目录路径（以/结尾或就是"logs"）
        if config_log_file.endswith('/') or config_log_file in ['logs', 'logs/']:
            # 是目录，使用时间戳文件名
            log_file = str(logs_dir / f"{timestamp}.log")
        elif config_log_file.startswith('logs/') and not config_log_file.endswith('/'):
            # 是logs目录下的具体文件，使用配置的文件名
            log_file = config_log_file
        elif not config_log_file.startswith('logs/'):
            # 不在logs目录，仍使用时间戳
            log_file = str(logs_dir / f"{timestamp}.log")
    
    actual_log_file = setup_logging(log_file, debug=debug_mode)
    
    logging.info("=" * 80)
    logging.info("🐋 Hyperliquid 大户监控器 V2")
    logging.info("=" * 80)
    logging.info(f"📁 配置文件: jsons/config.json")
    logging.info(f"📝 日志文件: {actual_log_file}")
    logging.info(f"🔍 DEBUG模式: {'开启' if debug_mode else '关闭'}")
    logging.info("=" * 80)
    
    # 加载地址过滤器
    address_filter = AddressFilter()
    
    # 从文件加载地址信息
    address_infos = load_addresses_from_file()
    
    if not address_infos:
        logging.error("❌ 没有找到监控地址，退出...")
        exit(1)
    
    logging.info(f"📊 从文件加载了 {len(address_infos)} 个地址")
    
    # 应用过滤规则
    filtered_addresses = []
    blocked_addresses = []
    
    for addr_info in address_infos:
        address = addr_info['address']
        display_name = addr_info.get('display_name')
        blocked_in_file = addr_info.get('blocked', False)
        
        # 检查文件中的block标记
        if blocked_in_file:
            blocked_addresses.append({
                'address': address,
                'display_name': display_name,
                'reason': '在地址文件中标记为blocked'
            })
            continue
        
        # 检查过滤器规则
        is_blocked, reason = address_filter.is_blocked(address, display_name)
        if is_blocked:
            blocked_addresses.append({
                'address': address,
                'display_name': display_name,
                'reason': reason
            })
            continue
        
        # 未被屏蔽，加入监控列表
        filtered_addresses.append(address)
    
    # 输出过滤统计
    logging.info("=" * 80)
    logging.info("📋 地址过滤统计")
    logging.info("=" * 80)
    logging.info(f"✅ 有效地址: {len(filtered_addresses)} 个")
    logging.info(f"🚫 屏蔽地址: {len(blocked_addresses)} 个")
    
    if blocked_addresses:
        logging.info("\n🚫 已屏蔽的地址:")
        for idx, blocked in enumerate(blocked_addresses, 1):
            name_str = f" ({blocked['display_name']})" if blocked['display_name'] else ""
            logging.info(f"   {idx}. {blocked['address']}{name_str}")
            logging.info(f"      原因: {blocked['reason']}")
    
    logging.info("=" * 80)
    
    if not filtered_addresses:
        logging.error("❌ 没有有效的监控地址（全部被过滤），退出...")
        exit(1)
    
    logging.info(f"\n✅ 将监控 {len(filtered_addresses)} 个地址\n")
    
    # 创建并启动监控器
    monitor = WhaleMonitor(filtered_addresses, config)
    monitor.start_monitoring()

