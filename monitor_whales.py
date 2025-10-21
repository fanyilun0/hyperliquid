#!/usr/bin/env python3
"""
监控Hyperliquid大户交易活动 V2 (WebSocket模式)
支持配置文件、日志记录、自动重连等高级功能
"""
import json
import time
import logging
import os
import asyncio
import random
from typing import Dict, List, Optional
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# 导入共享工具模块
from monitor_utils import Config, AddressFilter, load_addresses_from_file, filter_addresses, setup_logging
# 导入持仓管理器
from position_manager import PositionManager


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
        
        # 计算单笔交易的名义价值 (Notional Value = 价格 × 数量)
        trade_value = price * size
        
        # 检查是否需要通知（传入交易价值而不是仓位大小）
        if not self._should_notify(action_type, size, trade_value):
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
            'trade_value': trade_value,  # 新增：单笔交易价值
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
    
    def _should_notify(self, action: str, size: float, trade_value: float) -> bool:
        """检查是否应该通知此事件
        
        Args:
            action: 交易类型（开仓、平仓等）
            size: 交易数量
            trade_value: 交易价值（价格 × 数量）
        
        Returns:
            是否应该通知
        """
        monitor_config = self.config.get('monitor', default={})
        
        # 优先检查交易价值阈值（推荐使用）
        min_trade_value = monitor_config.get('min_trade_value', 0)
        if min_trade_value > 0:
            if trade_value < min_trade_value:
                logging.debug(
                    f"交易价值 ${trade_value:,.2f} 小于最小阈值 ${min_trade_value:,.2f}，已过滤"
                )
                return False
        else:
            # 如果没有设置 min_trade_value，则使用传统的 min_position_size（向后兼容）
            min_size = monitor_config.get('min_position_size', 0)
            if min_size > 0 and size < min_size:
                logging.debug(f"交易数量 {size:,.4f} 小于最小阈值 {min_size:,.4f}，已过滤")
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
    """大户监控器 V2 (WebSocket模式)"""
    
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
        
        # 创建持仓管理器（带缓存）
        if self.sdk_available:
            self.position_manager = PositionManager(self.Info, self.constants)
        else:
            self.position_manager = None
        
        # 为每个用户创建独立的Info实例（解决多用户订阅问题）
        self.info_instances = {}
        
        # 资产名称缓存 {asset_id: coin_name}
        self.asset_name_cache = {}
        
        # WebSocket 重连配置
        self.reconnect_delay = config.get('websocket', 'reconnect_delay', default=5)
        self.max_reconnect_delay = config.get('websocket', 'max_reconnect_delay', default=60)
        self.reconnect_attempts = {}  # {address: attempt_count}
        self.running = False  # 监控运行状态
        
        logging.info(f"监控器初始化完成，监控 {len(self.addresses)} 个地址")
    
    def _get_pnl_fire_emoji(self, total_pnl: float) -> str:
        """根据Total PnL返回对应的fire emoji
        
        Args:
            total_pnl: 总盈亏
        
        Returns:
            fire emoji字符串
        """
        if total_pnl >= 10_000_000:  # >= $10M
            return "🔥🔥🔥🔥🔥"
        elif total_pnl >= 5_000_000:  # >= $5M
            return "🔥🔥🔥🔥"
        elif total_pnl >= 1_000_000:  # >= $1M
            return "🔥🔥🔥"
        elif total_pnl >= 500_000:    # >= $500K
            return "🔥🔥"
        elif total_pnl >= 100_000:    # >= $100K
            return "🔥"
        elif total_pnl > 0:           # > $0
            return "✨"
        elif total_pnl == 0:
            return "➖"
        elif total_pnl > -100_000:    # > -$100K
            return "❄️"
        elif total_pnl > -500_000:    # > -$500K
            return "❄️❄️"
        elif total_pnl > -1_000_000:  # > -$1M
            return "❄️❄️❄️"
        elif total_pnl > -5_000_000:  # > -$5M
            return "❄️❄️❄️❄️"
        else:                         # <= -$5M
            return "❄️❄️❄️❄️❄️"
    
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
    
    def _subscribe_address(self, address: str, max_retries: int = 5) -> bool:
        """订阅单个地址的事件 (带指数退避重试逻辑)
        
        Args:
            address: 用户地址
            max_retries: 最大重试次数
        
        Returns:
            是否订阅成功
        """
        base_delay = 4  # 基础延迟时间（秒）
        max_delay = 60  # 最大延迟时间（秒）
        
        for attempt in range(max_retries):
            try:
                # 如果已存在连接，先关闭
                if address in self.info_instances:
                    try:
                        old_info = self.info_instances[address]
                        if hasattr(old_info, 'ws') and old_info.ws:
                            old_info.ws.close()
                    except:
                        pass
                
                # 创建新的WebSocket连接
                logging.debug(f"为 {address} 创建独立的Info实例...")
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
                
                # 重置重连计数
                self.reconnect_attempts[address] = 0
                
                logging.info(f"✅ 订阅成功: {address}")
                return True  # 成功后立即返回
                
            except Exception as e:
                if attempt == max_retries - 1:
                    # 达到最大重试次数，放弃
                    logging.error(f"❌ 订阅失败 {address} 在尝试 {max_retries} 次后放弃。错误: {e}")
                    logging.debug(f"详细错误信息: ", exc_info=True)
                    return False
                
                # 计算下一次重试的延迟时间（指数增长: 4s, 8s, 16s...）
                delay = base_delay * (2 ** attempt)
                # 增加一点随机性 (jitter) 来防止所有失败的连接在同一时间重试
                jitter = random.uniform(0, 1)
                # 确保延迟时间不超过设定的最大值
                sleep_time = min(delay + jitter, max_delay)
                
                logging.warning(
                    f"⚠️  订阅失败 {address[:10]}... (尝试 {attempt + 1}/{max_retries})。"
                    f"将在 {sleep_time:.2f} 秒后重试... 错误: {e}"
                )
                time.sleep(sleep_time)
    
    def _reconnect_address(self, address: str, max_reconnect_attempts: int = 10):
        """重连单个地址 (带指数退避和最大重试限制)
        
        Args:
            address: 用户地址
            max_reconnect_attempts: 最大重连尝试次数（0表示无限重试）
        """
        if not self.running:
            return
        
        attempt = self.reconnect_attempts.get(address, 0)
        
        # 检查是否超过最大重连次数
        if max_reconnect_attempts > 0 and attempt >= max_reconnect_attempts:
            logging.error(
                f"❌ {address[:10]}... 已达到最大重连次数 ({max_reconnect_attempts})，停止重连"
            )
            return
        
        self.reconnect_attempts[address] = attempt + 1
        
        # 计算延迟（指数退避）
        base_delay = self.reconnect_delay
        delay = min(base_delay * (2 ** attempt), self.max_reconnect_delay)
        # 添加随机抖动
        jitter = random.uniform(0, 2)
        sleep_time = min(delay + jitter, self.max_reconnect_delay)
        
        logging.warning(
            f"⚠️  {address[:10]}... 连接断开，将在 {sleep_time:.2f} 秒后尝试重连 "
            f"(第 {attempt + 1} 次)..."
        )
        time.sleep(sleep_time)
        
        # 使用带重试逻辑的订阅方法
        if self._subscribe_address(address, max_retries=3):
            logging.info(f"✅ {address[:10]}... 重连成功")
        else:
            # 递归重连
            self._reconnect_address(address, max_reconnect_attempts)
    
    async def _periodic_data_update(self):
        """定期更新账户数据（5分钟一次）"""
        while self.running:
            try:
                # 等待5分钟
                await asyncio.sleep(300)  # 300秒 = 5分钟
                
                if not self.running:
                    break
                
                logging.info("🔄 定期更新账户数据（5分钟）...")
                
                # 更新所有地址的数据并生成报告
                await self.position_manager.update_and_generate_report_async(
                    self.addresses,
                    max_concurrent=10,
                    force_refresh=True
                )
                
                logging.info("✅ 定期更新完成")
                
            except asyncio.CancelledError:
                logging.info("定期更新任务已取消")
                break
            except Exception as e:
                logging.error(f"定期更新失败: {e}")
    
    def start_monitoring(self):
        """开始监控"""
        if not self.sdk_available:
            logging.error("SDK不可用，无法启动监控")
            return
        
        self.running = True
        
        print(f"\n{'='*80}")
        print(f"开始监控 {len(self.addresses)} 个大户地址 (WebSocket模式)")
        print(f"{'='*80}\n")
        
        for i, addr in enumerate(self.addresses, 1):
            print(f"{i}. {addr}")
        
        # 获取初始仓位信息并生成positions.log
        print(f"\n{'='*80}")
        print("正在获取用户初始仓位信息...")
        print(f"{'='*80}\n")
        
        # 获取所有地址的持仓并生成HTML报告（使用异步版本以提升性能）
        # 使用 asyncio.run() 来运行异步任务，避免 DeprecationWarning
        all_account_data = asyncio.run(
            self.position_manager.update_and_generate_report_async(
                self.addresses, 
                max_concurrent=10,
                force_refresh=True
            )
        )
        
        # 初始化追踪器的仓位数据
        for address, data in all_account_data.items():
            positions = data.get('positions', [])
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
        
        # 启动定期更新任务（在新线程中运行）
        import threading
        def run_periodic_update():
            asyncio.run(self._periodic_data_update())
        
        update_thread = threading.Thread(target=run_periodic_update, daemon=True)
        update_thread.start()
        logging.info("✅ 定期更新任务已启动（后台线程）")
        
        print(f"\n{'='*80}")
        print("正在订阅用户事件...")
        print(f"{'='*80}\n")
        
        # 为每个地址创建独立的Info实例并订阅
        success_count = 0
        failed_addresses = []
        
        for idx, address in enumerate(self.addresses, 1):
            logging.debug(f"[{idx}/{len(self.addresses)}] 准备订阅地址: {address}")
            
            if self._subscribe_address(address):
                success_count += 1
            else:
                failed_addresses.append(address)
            
            # 添加短暂延迟，避免连接创建过快
            time.sleep(0.2)
        
        print(f"📊 订阅✅ 成功: {success_count}/{len(self.addresses)}")
        if failed_addresses:
            print(f"❌ 失败: {len(failed_addresses)}/{len(self.addresses)}")
            logging.warning(f"失败地址列表: {failed_addresses}")
        print(f"{'='*80}\n")
        
        if success_count == 0:
            logging.error("没有成功订阅任何地址，退出...")
            self.running = False
            return
        
        print(f"🎯 监控中... (按Ctrl+C停止)\n")
        
        # 保持运行并监控连接状态
        try:
            while self.running:
                time.sleep(10)  # 每10秒检查一次连接状态
                
                # 检查WebSocket连接状态
                for address in self.addresses:
                    if address not in self.info_instances:
                        continue
                    
                    info = self.info_instances[address]
                    # 检查WebSocket是否仍然连接
                    if hasattr(info, 'ws') and info.ws:
                        if not info.ws.connected:
                            logging.warning(f"⚠️  检测到 {address} 连接断开")
                            # 在新线程中重连，避免阻塞主循环
                            import threading
                            threading.Thread(
                                target=self._reconnect_address, 
                                args=(address,),
                                daemon=True
                            ).start()
                        
        except KeyboardInterrupt:
            logging.info("\n收到停止信号，正在关闭...")
            self.running = False
            
            # 关闭所有WebSocket连接
            for address, info in self.info_instances.items():
                try:
                    if hasattr(info, 'ws') and info.ws:
                        info.ws.close()
                        logging.debug(f"已关闭 {address} 的WebSocket连接")
                except:
                    pass
            
            logging.info("监控已停止")
    
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
        user_addr = trade_info['user']
        
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
            print(f"👤 用户: {user_addr}")
            
            # 交易详情
            print(f"💎 币种: {coin_name}")
            print(f"📊 方向: {trade_info['side']}")
            print(f"📈 数量: {trade_info['size']:,.4f}")
            print(f"💵 价格: ${trade_info['price']:,.4f}")
            print(f"💰 交易价值: ${trade_info['trade_value']:,.2f}")
            
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
            
            # 从缓存获取账户汇总信息
            try:
                # 使用 asyncio.create_task 在当前事件循环中运行
                account_data = None
                try:
                    # 尝试在现有事件循环中运行
                    loop = asyncio.get_running_loop()
                    # 创建任务并等待
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            self.position_manager.get_account_data_async(user_addr, force_refresh=False)
                        )
                        account_data = future.result(timeout=5)
                except RuntimeError:
                    # 没有运行中的事件循环，直接运行
                    account_data = asyncio.run(
                        self.position_manager.get_account_data_async(user_addr, force_refresh=False)
                    )
                
                if account_data:
                    account_value = account_data.get('account_value', 0)
                    total_position_value = account_data.get('total_position_value', 0)
                    pnl_summary = account_data.get('pnl_summary', {})
                    total_pnl = pnl_summary.get('total_pnl', 0)
                    
                    # 根据Total PnL选择fire emoji
                    fire_emoji = self._get_pnl_fire_emoji(total_pnl)
                    
                    # 显示账户价值和PnL汇总
                    print(f"\n{'─' * 80}")
                    print(f"📊 账户汇总信息 {fire_emoji}")
                    print(f"{'─' * 80}")
                    
                    print(f"💼 账户总价值: ${account_value:,.2f}")
                    print(f"📈 持仓总价值: ${total_position_value:,.2f}")
                    
                    # PnL数据
                    pnl_symbol = '💰' if total_pnl > 0 else '💸' if total_pnl < 0 else '📊'
                    print(f"{pnl_symbol} Total PnL: ${total_pnl:,.2f}")
                    
                    # 阶段性PnL（如果可用）
                    pnl_24h = pnl_summary.get('pnl_24h', 0)
                    pnl_7d = pnl_summary.get('pnl_7d', 0)
                    pnl_30d = pnl_summary.get('pnl_30d', 0)
                    
                    if pnl_24h != 0:
                        print(f"   24-Hour PnL: ${pnl_24h:,.2f}")
                    if pnl_7d != 0:
                        print(f"   7-Day PnL: ${pnl_7d:,.2f}")
                    if pnl_30d != 0:
                        print(f"   30-Day PnL: ${pnl_30d:,.2f}")
                    
                    # 持仓前三
                    top_positions = sorted(
                        account_data.get('positions', []),
                        key=lambda x: x['position_value'],
                        reverse=True
                    )[:3]
                    
                    if top_positions:
                        print(f"\n📊 持仓前三（按价值）:")
                        for idx, pos in enumerate(top_positions, 1):
                            direction_emoji = "🟢" if pos['direction_short'] == 'Long' else "🔴"
                            pnl_display = f"+${pos['unrealized_pnl']:,.2f}" if pos['unrealized_pnl'] > 0 else f"${pos['unrealized_pnl']:,.2f}"
                            print(
                                f"   {idx}. {direction_emoji} {pos['coin']} | "
                                f"${pos['position_value']:,.2f} | "
                                f"PnL: {pnl_display}"
                            )
                    
                    # 挂单前三
                    open_orders = account_data.get('open_orders', [])
                    if open_orders:
                        orders_with_value = []
                        for order in open_orders:
                            try:
                                order_info = order.get('order', {})
                                limit_px = float(order_info.get('limitPx', 0))
                                sz = float(order_info.get('sz', 0))
                                order_value = limit_px * sz
                                
                                orders_with_value.append({
                                    'coin': order_info.get('coin', 'N/A'),
                                    'side': '买入' if order_info.get('side') == 'B' else '卖出',
                                    'price': limit_px,
                                    'order_value': order_value,
                                })
                            except:
                                continue
                        
                        top_orders = sorted(orders_with_value, key=lambda x: x['order_value'], reverse=True)[:3]
                        
                        if top_orders:
                            print(f"\n📋 挂单前三（按价值）:")
                            for idx, order in enumerate(top_orders, 1):
                                side_emoji = "🟢" if order['side'] == '买入' else "🔴"
                                print(
                                    f"   {idx}. {side_emoji} {order['coin']} | "
                                    f"{order['side']} @ ${order['price']:,.4f} | "
                                    f"价值: ${order['order_value']:,.2f}"
                                )
                    
            except Exception as e:
                logging.debug(f"获取账户汇总信息失败: {e}")
            
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
                f"价值: ${trade_info['trade_value']:,.2f} | "
                f"仓位: {trade_info['old_position']:,.4f} → {trade_info['new_position']:,.4f} | "
                f"{pnl_info}"
            )




if __name__ == "__main__":
    # 加载配置
    config = Config()
    
    # 设置日志（使用时间戳文件名）
    debug_mode = config.get('debug', default=False)
    actual_log_file = setup_logging(log_suffix="_websocket", debug=debug_mode)
    
    logging.info("=" * 80)
    logging.info("🐋 Hyperliquid 大户监控器 V2 (WebSocket模式)")
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
    filtered_addresses, blocked_addresses = filter_addresses(address_infos, address_filter)
    
    # 输出过滤统计
    logging.info("=" * 80)
    logging.info("📋 地址过滤统计")
    logging.info("=" * 80)
    logging.info(f"✅ 有效地址: {len(filtered_addresses)} 个")
    logging.info(f"🚫 屏蔽地址: {len(blocked_addresses)} 个")
    
    if not filtered_addresses:
        logging.error("❌ 没有有效的监控地址（全部被过滤），退出...")
        exit(1)
    
    logging.info(f"\n✅ 将监控 {len(filtered_addresses)} 个地址\n")
    
    # 创建并启动监控器
    monitor = WhaleMonitor(filtered_addresses, config)
    monitor.start_monitoring()

