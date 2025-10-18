#!/usr/bin/env python3
"""
持仓管理器 - 获取和记录用户持仓信息
"""
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path


class PositionManager:
    """持仓信息管理器"""
    
    def __init__(self, info_class, constants):
        """初始化持仓管理器
        
        Args:
            info_class: Hyperliquid Info 类
            constants: Hyperliquid 常量
        """
        self.Info = info_class
        self.constants = constants
        
        # 使用positions目录，文件名使用时间戳
        positions_dir = Path("positions")
        positions_dir.mkdir(exist_ok=True)
        
        # 生成带时间戳的文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.positions_log = positions_dir / f"positions_{timestamp}.html"
    
    def fetch_user_state(self, address: str) -> Optional[Dict]:
        """获取用户当前状态
        
        Args:
            address: 用户地址
        
        Returns:
            用户状态数据或None
        """
        try:
            # 创建临时Info实例用于API调用
            info = self.Info(self.constants.MAINNET_API_URL, skip_ws=True)
            
            # 调用 userState 接口
            user_state = info.user_state(address)
            
            return user_state
        except Exception as e:
            logging.warning(f"获取用户状态失败 {address}: {e}")
            return None
    
    def parse_position(self, position_data: Dict) -> Dict:
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
            
            # 资金费
            cumulative_funding = float(pos.get('cumFunding', {}).get('allTime', 0))
            
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
    
    def generate_position_table_html(self, address: str, positions: List[Dict]) -> str:
        """生成持仓表格的HTML
        
        Args:
            address: 用户地址
            positions: 持仓列表
        
        Returns:
            HTML 表格字符串
        """
        if not positions:
            return f"""
<!-- 地址: {address} -->
<div class="no-positions">
    <p>该地址暂无持仓</p>
</div>
"""
        
        # 计算总计
        total_value = sum(p['position_value'] for p in positions)
        total_pnl = sum(p['unrealized_pnl'] for p in positions)
        total_funding = sum(p['cumulative_funding'] for p in positions)
        
        # 生成表格行
        rows = []
        for pos in positions:
            # PnL 样式
            pnl_class = "profit" if pos['unrealized_pnl'] > 0 else "loss" if pos['unrealized_pnl'] < 0 else "neutral"
            pnl_sign = "+" if pos['unrealized_pnl'] > 0 else ""
            
            # 资金费样式
            funding_class = "profit" if pos['cumulative_funding'] > 0 else "loss" if pos['cumulative_funding'] < 0 else "neutral"
            funding_sign = "+" if pos['cumulative_funding'] > 0 else ""
            
            # 爆仓价格显示
            liq_px_display = f"${pos['liquidation_px']:,.4f}" if pos['liquidation_px'] > 0 else "∞"
            
            row = f"""<tr>
    <td class="ant-table-cell">{pos['coin']}</td>
    <td class="ant-table-cell direction-{pos['direction_short'].lower()}">{pos['direction']}</td>
    <td class="ant-table-cell">{pos['leverage']:.1f}x</td>
    <td class="ant-table-cell">${pos['position_value']:,.2f}</td>
    <td class="ant-table-cell">{pos['size']:,.4f}</td>
    <td class="ant-table-cell">${pos['entry_px']:,.4f}</td>
    <td class="ant-table-cell pnl-{pnl_class}">{pnl_sign}${pos['unrealized_pnl']:,.2f}</td>
    <td class="ant-table-cell funding-{funding_class}">{funding_sign}${pos['cumulative_funding']:,.2f}</td>
    <td class="ant-table-cell">{liq_px_display}</td>
</tr>"""
            rows.append(row)
        
        # 总计行
        total_pnl_class = "profit" if total_pnl > 0 else "loss" if total_pnl < 0 else "neutral"
        total_pnl_sign = "+" if total_pnl > 0 else ""
        total_funding_class = "profit" if total_funding > 0 else "loss" if total_funding < 0 else "neutral"
        total_funding_sign = "+" if total_funding > 0 else ""
        
        total_row = f"""<tr class="total-row">
    <td class="ant-table-cell"><strong>总计</strong></td>
    <td class="ant-table-cell" colspan="2">{len(positions)} 个持仓</td>
    <td class="ant-table-cell"><strong>${total_value:,.2f}</strong></td>
    <td class="ant-table-cell">-</td>
    <td class="ant-table-cell">-</td>
    <td class="ant-table-cell pnl-{total_pnl_class}"><strong>{total_pnl_sign}${total_pnl:,.2f}</strong></td>
    <td class="ant-table-cell funding-{total_funding_class}"><strong>{total_funding_sign}${total_funding:,.2f}</strong></td>
    <td class="ant-table-cell">-</td>
</tr>"""
        
        # 完整表格
        table = f"""
<!-- 地址: {address} -->
<div class="position-table">
    <h3>地址: {address}</h3>
    <table class="ant-table">
        <thead>
            <tr>
                <th class="ant-table-cell">代币</th>
                <th class="ant-table-cell">方向</th>
                <th class="ant-table-cell">杠杆</th>
                <th class="ant-table-cell">价值</th>
                <th class="ant-table-cell">数量</th>
                <th class="ant-table-cell">开仓价格</th>
                <th class="ant-table-cell">盈亏 (PnL)</th>
                <th class="ant-table-cell">资金费</th>
                <th class="ant-table-cell">爆仓价格</th>
            </tr>
        </thead>
        <tbody>
{chr(10).join(rows)}
{total_row}
        </tbody>
    </table>
    <p class="update-time">更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
</div>
"""
        return table
    
    def fetch_and_log_positions(self, addresses: List[str]) -> Dict[str, List[Dict]]:
        """获取并记录所有地址的持仓信息
        
        Args:
            addresses: 地址列表
        
        Returns:
            {address: [positions]} 字典
        """
        all_positions = {}
        html_tables = []
        
        # 添加 HTML 头部和样式
        html_header = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>持仓监控 - Hyperliquid</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #0a0e27;
            color: #e8e8e8;
            padding: 20px;
            margin: 0;
        }}
        .position-table {{
            margin-bottom: 40px;
            background: #1a1f3a;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }}
        h3 {{
            color: #fff;
            margin-top: 0;
            padding-bottom: 10px;
            border-bottom: 2px solid #2d3455;
            font-size: 14px;
            word-break: break-all;
        }}
        .ant-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: #1e2442;
            border-radius: 4px;
            overflow: hidden;
        }}
        .ant-table-cell {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid #2d3455;
        }}
        thead .ant-table-cell {{
            background: #252b4a;
            font-weight: 600;
            color: #a8b3cf;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        tbody .ant-table-cell {{
            color: #e8e8e8;
            font-size: 14px;
        }}
        .direction-long {{
            color: #52c41a;
            font-weight: 600;
        }}
        .direction-short {{
            color: #ff4d4f;
            font-weight: 600;
        }}
        .pnl-profit {{
            color: #52c41a;
            font-weight: 600;
        }}
        .pnl-loss {{
            color: #ff4d4f;
            font-weight: 600;
        }}
        .pnl-neutral {{
            color: #8c8c8c;
        }}
        .funding-profit {{
            color: #52c41a;
        }}
        .funding-loss {{
            color: #ff4d4f;
        }}
        .funding-neutral {{
            color: #8c8c8c;
        }}
        .total-row {{
            background: #252b4a;
            font-weight: 600;
        }}
        .total-row .ant-table-cell {{
            border-top: 2px solid #3d4567;
        }}
        .update-time {{
            color: #8c8c8c;
            font-size: 12px;
            margin: 10px 0 0 0;
            text-align: right;
        }}
        .no-positions {{
            text-align: center;
            padding: 40px;
            color: #8c8c8c;
        }}
        .summary {{
            background: #252b4a;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
        }}
        .summary h2 {{
            margin-top: 0;
            color: #fff;
        }}
        .summary-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .stat-card {{
            background: #1e2442;
            padding: 15px;
            border-radius: 4px;
        }}
        .stat-label {{
            color: #a8b3cf;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 5px;
        }}
        .stat-value {{
            color: #fff;
            font-size: 24px;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <div class="summary">
        <h2>📊 持仓监控总览</h2>
        <p>生成时间: {generation_time}</p>
        <div class="summary-stats">
            <div class="stat-card">
                <div class="stat-label">监控地址数</div>
                <div class="stat-value">{total_addresses}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">持仓地址数</div>
                <div class="stat-value">{addresses_with_positions}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">总持仓数</div>
                <div class="stat-value">{total_positions}</div>
            </div>
        </div>
    </div>
"""
        
        logging.info(f"开始获取 {len(addresses)} 个地址的持仓信息...")
        
        for idx, address in enumerate(addresses, 1):
            logging.info(f"[{idx}/{len(addresses)}] 获取地址持仓: {address}")
            
            user_state = self.fetch_user_state(address)
            if not user_state:
                all_positions[address] = []
                html_tables.append(self.generate_position_table_html(address, []))
                continue
            
            # 解析持仓
            asset_positions = user_state.get('assetPositions', [])
            positions = []
            
            for pos_data in asset_positions:
                parsed_pos = self.parse_position(pos_data)
                if parsed_pos:
                    positions.append(parsed_pos)
            
            all_positions[address] = positions
            
            # 生成HTML表格
            html_table = self.generate_position_table_html(address, positions)
            html_tables.append(html_table)
            
            # 日志输出
            if positions:
                logging.info(f"   ✅ 发现 {len(positions)} 个持仓")
                for pos in positions[:3]:
                    logging.info(
                        f"      • {pos['coin']}: {pos['direction']} {pos['size']:.4f} | "
                        f"价值: ${pos['position_value']:,.2f} | "
                        f"PnL: ${pos['unrealized_pnl']:,.2f}"
                    )
                if len(positions) > 3:
                    logging.info(f"      ... 还有 {len(positions) - 3} 个持仓")
            else:
                logging.info(f"   ℹ️  无持仓")
        
        # 计算统计数据
        total_addresses = len(addresses)
        addresses_with_positions = sum(1 for pos_list in all_positions.values() if pos_list)
        total_positions = sum(len(pos_list) for pos_list in all_positions.values())
        generation_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 替换占位符
        html_header = html_header.format(
            generation_time=generation_time,
            total_addresses=total_addresses,
            addresses_with_positions=addresses_with_positions,
            total_positions=total_positions
        )
        
        # 写入HTML文件
        html_content = html_header + '\n'.join(html_tables) + "\n</body>\n</html>"
        
        try:
            with open(self.positions_log, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logging.info(f"✅ 持仓信息已保存到: {self.positions_log}")
        except Exception as e:
            logging.error(f"保存持仓信息失败: {e}")
        
        return all_positions

