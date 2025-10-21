#!/usr/bin/env python3
"""
持仓管理器 - 获取和记录用户持仓信息
支持异步并发模式，缓存机制（5分钟自动刷新）
"""
import json
import logging
import asyncio
import time
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
from collections import defaultdict


class PositionManager:
    """持仓信息管理器（带缓存）"""
    
    def __init__(self, info_class, constants):
        """初始化持仓管理器
        
        Args:
            info_class: Hyperliquid Info 类
            constants: Hyperliquid 常量
        """
        self.Info = info_class
        self.constants = constants
        
        # 缓存配置
        self.cache_ttl = 300  # 缓存时间：5分钟（300秒）
        
        # 数据缓存: {address: {'data': {...}, 'timestamp': float}}
        self.account_data_cache: Dict[str, Dict] = {}
        
        # 更新锁，防止并发更新同一地址
        self.update_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        
        # 使用positions目录，文件名使用时间戳
        positions_dir = Path("positions")
        positions_dir.mkdir(exist_ok=True)
        
        # 生成带时间戳的文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.positions_log = positions_dir / f"positions_{timestamp}.html"
    
    async def get_account_data_async(self, address: str, force_refresh: bool = False, retry_count: int = 3) -> Optional[Dict]:
        """异步获取账户数据（带缓存和重试机制）
        
        Args:
            address: 用户地址
            force_refresh: 是否强制刷新缓存
            retry_count: 失败重试次数
        
        Returns:
            账户数据字典，包含：
            - user_state: 用户状态（持仓等）
            - account_value: 账户总价值
            - pnl_summary: PnL汇总数据
            - open_orders: 挂单信息
            - timestamp: 数据时间戳
        """
        async with self.update_locks[address]:
            # 检查缓存
            if not force_refresh and address in self.account_data_cache:
                cache_entry = self.account_data_cache[address]
                cache_age = time.time() - cache_entry['timestamp']
                
                if cache_age < self.cache_ttl:
                    logging.debug(f"使用缓存数据: {address[:10]}... (缓存年龄: {cache_age:.1f}秒)")
                    return cache_entry['data']
            
            # 缓存过期或不存在，获取新数据（带重试）
            for attempt in range(retry_count):
                try:
                    if attempt > 0:
                        logging.info(f"🔄 重试获取账户数据 ({attempt + 1}/{retry_count}): {address[:10]}...")
                        await asyncio.sleep(2 ** attempt)  # 指数退避: 1s, 2s, 4s
                    else:
                        logging.info(f"🔄 刷新账户数据: {address[:10]}...")
                    
                    # 获取当前事件循环
                    loop = asyncio.get_running_loop()
                    
                    # 创建临时Info实例用于API调用
                    info = self.Info(self.constants.MAINNET_API_URL, skip_ws=True)
                    
                    # 并发调用多个API
                    user_state_task = loop.run_in_executor(None, info.user_state, address)
                    
                    # 获取用户状态
                    user_state = await user_state_task
                    
                    if not user_state:
                        logging.warning(f"无法获取用户状态: {address[:10]}...")
                        if attempt < retry_count - 1:
                            continue
                        return None
                    
                    # 解析账户数据
                    account_data = self._parse_account_data(user_state, address)
                    
                    # 获取挂单信息
                    try:
                        open_orders = await loop.run_in_executor(None, info.open_orders, address)
                        account_data['open_orders'] = open_orders or []
                    except Exception as e:
                        logging.debug(f"获取挂单信息失败 {address[:10]}...: {e}")
                        account_data['open_orders'] = []
                    
                    # 更新缓存
                    self.account_data_cache[address] = {
                        'data': account_data,
                        'timestamp': time.time()
                    }
                    
                    logging.info(f"✅ 账户数据已更新: {address[:10]}...")
                    return account_data
                    
                except Exception as e:
                    if attempt < retry_count - 1:
                        logging.warning(f"获取账户数据失败 {address[:10]}... (尝试 {attempt + 1}/{retry_count}): {e}")
                    else:
                        logging.error(f"获取账户数据失败 {address[:10]}... (已重试{retry_count}次): {e}")
                    
                    # 最后一次尝试失败，返回None
                    if attempt == retry_count - 1:
                        return None
    
    def _parse_account_data(self, user_state: Dict, address: str) -> Dict:
        """解析账户数据
        
        Args:
            user_state: 用户状态数据
            address: 用户地址
        
        Returns:
            解析后的账户数据
        """
        # 基础数据
        account_value = float(user_state.get('marginSummary', {}).get('accountValue', 0))
        
        # 解析持仓
        asset_positions = user_state.get('assetPositions', [])
        positions = []
        total_unrealized_pnl = 0
        
        for pos_data in asset_positions:
            parsed_pos = self.parse_position(pos_data)
            if parsed_pos:
                positions.append(parsed_pos)
                total_unrealized_pnl += parsed_pos['unrealized_pnl']
        
        # 计算总持仓价值
        total_position_value = sum(p['position_value'] for p in positions)
        
        # PnL汇总（注意：Hyperliquid API可能不直接提供24h/7d/30d PnL）
        # 我们这里只能获取未实现盈亏，历史PnL需要通过其他接口
        pnl_summary = {
            'total_pnl': total_unrealized_pnl,  # 当前未实现盈亏
            'unrealized_pnl': total_unrealized_pnl,
            # 这些数据需要从其他API获取或计算
            'pnl_24h': 0,
            'pnl_48h': 0,
            'pnl_7d': 0,
            'pnl_30d': 0,
        }
        
        return {
            'user_state': user_state,
            'address': address,
            'account_value': account_value,
            'total_position_value': total_position_value,
            'positions': positions,
            'pnl_summary': pnl_summary,
            'open_orders': [],  # 将在外部填充
            'timestamp': datetime.now().isoformat()
        }
    
    def parse_position(self, position_data: Dict) -> Optional[Dict]:
        """解析单个持仓数据
        
        Args:
            position_data: 持仓数据
        
        Returns:
            解析后的持仓信息
        """
        try:
            pos = position_data.get('position', {})
            
            # 基础信息
            coin = pos.get('coin', 'N/A')
            szi = float(pos.get('szi', 0))  # 有符号仓位大小
            
            # 价格和盈亏
            entry_px = float(pos.get('entryPx', 0))
            position_value = float(pos.get('positionValue', 0))
            unrealized_pnl = float(pos.get('unrealizedPnl', 0))
            
            # 杠杆和保证金
            leverage = pos.get('leverage', {})
            leverage_value = float(leverage.get('value', 0)) if isinstance(leverage, dict) else 0
            
            # 资金费 (cumFunding: 正值=支付/亏损, 负值=收到/盈利)
            # 为了统一显示，转换为：正值=盈利，负值=亏损
            cumulative_funding_raw = float(pos.get('cumFunding', {}).get('allTime', 0))
            cumulative_funding = -cumulative_funding_raw  # 反转符号
            
            # 爆仓价格
            liquidation_px = float(pos.get('liquidationPx', 0)) if pos.get('liquidationPx') else 0
            
            # 确定方向
            if szi > 0:
                direction = "做多 (Long)"
                direction_short = "Long"
            elif szi < 0:
                direction = "做空 (Short)"
                direction_short = "Short"
            else:
                direction = "无持仓"
                direction_short = "None"
            
            return {
                'coin': coin,
                'direction': direction,
                'direction_short': direction_short,
                'size': abs(szi),
                'leverage': leverage_value,
                'position_value': position_value,
                'entry_px': entry_px,
                'unrealized_pnl': unrealized_pnl,
                'cumulative_funding': cumulative_funding,
                'liquidation_px': liquidation_px,
                'raw_szi': szi
            }
        except Exception as e:
            logging.error(f"解析持仓数据失败: {e}")
            return None
    
    async def get_top_positions(self, address: str, top_n: int = 3) -> List[Dict]:
        """获取持仓价值前N的持仓
        
        Args:
            address: 用户地址
            top_n: 返回前N个
        
        Returns:
            持仓列表
        """
        account_data = await self.get_account_data_async(address)
        if not account_data or not account_data['positions']:
            return []
        
        # 按持仓价值排序
        sorted_positions = sorted(
            account_data['positions'],
            key=lambda x: x['position_value'],
            reverse=True
        )
        
        return sorted_positions[:top_n]
    
    async def get_top_open_orders(self, address: str, top_n: int = 3) -> List[Dict]:
        """获取挂单价值前N的挂单
        
        Args:
            address: 用户地址
            top_n: 返回前N个
        
        Returns:
            挂单列表
        """
        account_data = await self.get_account_data_async(address)
        if not account_data or not account_data.get('open_orders'):
            return []
        
        # 解析并计算挂单价值
        orders_with_value = []
        for order in account_data['open_orders']:
            try:
                order_info = order.get('order', {})
                limit_px = float(order_info.get('limitPx', 0))
                sz = float(order_info.get('sz', 0))
                order_value = limit_px * sz
                
                orders_with_value.append({
                    'coin': order_info.get('coin', 'N/A'),
                    'side': '买入' if order_info.get('side') == 'B' else '卖出',
                    'size': sz,
                    'price': limit_px,
                    'order_value': order_value,
                    'order_type': order_info.get('orderType', 'Limit')
                })
            except Exception as e:
                logging.debug(f"解析挂单失败: {e}")
                continue
        
        # 按挂单价值排序
        sorted_orders = sorted(
            orders_with_value,
            key=lambda x: x['order_value'],
            reverse=True
        )
        
        return sorted_orders[:top_n]
    
    async def update_and_generate_report_async(
        self, 
        addresses: List[str], 
        max_concurrent: int = 10,
        force_refresh: bool = False
    ) -> Dict[str, Dict]:
        """更新所有地址数据并生成HTML报告
        
        Args:
            addresses: 地址列表
            max_concurrent: 最大并发数
            force_refresh: 是否强制刷新缓存
        
        Returns:
            {address: account_data} 字典
        """
        logging.info(f"🚀 开始更新 {len(addresses)} 个地址的数据...")
        
        # 创建信号量控制并发数
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_with_semaphore(addr):
            async with semaphore:
                return await self.get_account_data_async(addr, force_refresh)
        
        # 并发获取所有地址数据
        start_time = time.time()
        tasks = [fetch_with_semaphore(addr) for addr in addresses]
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time
        
        # 统计成功和失败的数量
        success_count = sum(1 for result in results if result is not None)
        fail_count = sum(1 for result in results if result is None)
        
        logging.info(f"✅ 数据更新完毕，耗时: {elapsed:.2f}秒")
        logging.info(f"📊 统计: 成功 {success_count} 个, 失败 {fail_count} 个 (总计 {len(addresses)} 个)")
        
        # 构建结果字典
        all_account_data = {}
        failed_addresses = []
        for addr, data in zip(addresses, results):
            if data:
                all_account_data[addr] = data
            else:
                failed_addresses.append(addr)
        
        # 如果有失败的地址，记录日志
        if failed_addresses:
            logging.warning(f"⚠️  获取失败的地址:")
            for addr in failed_addresses:
                logging.warning(f"   - {addr[:10]}...")
        
        # 生成HTML报告
        from create_html import generate_html_report
        generate_html_report(all_account_data, self.positions_log)
        
        return all_account_data
    
    # ============== 向后兼容的旧接口 ==============
    
    async def fetch_and_log_positions_async(
        self, 
        addresses: List[str], 
        max_concurrent: int = 10
    ) -> Dict[str, List[Dict]]:
        """异步获取并记录所有地址的持仓信息（向后兼容接口）
        
        Args:
            addresses: 地址列表
            max_concurrent: 最大并发数
        
        Returns:
            {address: [positions]} 字典
        """
        all_account_data = await self.update_and_generate_report_async(
            addresses, 
            max_concurrent, 
            force_refresh=True
        )
        
        # 转换为旧格式
        all_positions = {}
        for addr, data in all_account_data.items():
            all_positions[addr] = data.get('positions', [])
        
        return all_positions
