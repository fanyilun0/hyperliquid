#!/usr/bin/env python3
"""
监控工具模块 - 共享的工具类和函数
包含配置管理、地址过滤等功能
"""
import json
import logging
from typing import List, Dict
from pathlib import Path
from datetime import datetime


def setup_logging(log_file: str = None, debug: bool = False, log_suffix: str = ""):
    """设置日志
    
    Args:
        log_file: 日志文件路径（如果为空，自动生成到logs目录）
        debug: 是否启用DEBUG级别日志
        log_suffix: 日志文件名后缀（如 "_polling", "_websocket"）
    
    Returns:
        实际使用的日志文件路径
    """
    handlers = [logging.StreamHandler()]
    
    # 如果没有指定日志文件，使用时间戳生成
    if not log_file:
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = str(logs_dir / f"{timestamp}{log_suffix}.log")
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
            "websocket": {
                "reconnect_delay": 5,
                "max_reconnect_delay": 60
            },
            "polling": {
                "interval": 30,
                "enable_html_report": True
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


def filter_addresses(address_infos: List[Dict], address_filter: AddressFilter) -> tuple[List[str], List[Dict]]:
    """过滤地址列表
    
    Args:
        address_infos: 地址信息列表
        address_filter: 地址过滤器实例
    
    Returns:
        (有效地址列表, 被屏蔽地址信息列表)
    """
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
    
    return filtered_addresses, blocked_addresses

