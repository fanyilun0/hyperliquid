#!/usr/bin/env python3
"""
HTML报告生成模块
负责生成持仓监控的HTML报告
"""
import logging
from typing import Dict, List
from datetime import datetime
from pathlib import Path


def generate_position_table_html(address: str, account_data: Dict) -> str:
    """生成单个地址的持仓表格HTML
    
    Args:
        address: 用户地址
        account_data: 账户数据
    
    Returns:
        HTML 表格字符串
    """
    positions = account_data.get('positions', [])
    pnl_summary = account_data.get('pnl_summary', {})
    account_value = account_data.get('account_value', 0)
    
    # 获取持仓前三
    top_positions = sorted(positions, key=lambda x: x['position_value'], reverse=True)[:3]
    
    # 获取挂单前三
    open_orders = account_data.get('open_orders', [])
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
                'size': sz,
                'price': limit_px,
                'order_value': order_value,
            })
        except:
            continue
    
    top_orders = sorted(orders_with_value, key=lambda x: x['order_value'], reverse=True)[:3]
    
    if not positions:
        return f"""
<!-- 地址: {address} -->
<div class="address-section">
    <div class="address-header">
        <h3>地址: {address}</h3>
        <div class="address-stats">
            <div class="stat-item">
                <span class="stat-label">账户价值</span>
                <span class="stat-value">${account_value:,.2f}</span>
            </div>
        </div>
    </div>
    <div class="no-positions">
        <p>该地址暂无持仓</p>
    </div>
</div>
"""
    
    # 计算总计
    total_value = sum(p['position_value'] for p in positions)
    total_pnl = sum(p['unrealized_pnl'] for p in positions)
    total_funding = sum(p['cumulative_funding'] for p in positions)
    
    # PnL 卡片
    pnl_cards = f"""
    <div class="pnl-cards">
        <div class="pnl-card">
            <div class="pnl-label">Total PnL</div>
            <div class="pnl-value {'profit' if pnl_summary['total_pnl'] > 0 else 'loss'}">
                ${pnl_summary['total_pnl']:,.2f}
            </div>
        </div>
        <div class="pnl-card">
            <div class="pnl-label">24-Hour PnL</div>
            <div class="pnl-value {'profit' if pnl_summary['pnl_24h'] > 0 else 'loss' if pnl_summary['pnl_24h'] < 0 else 'neutral'}">
                ${pnl_summary['pnl_24h']:,.2f}
            </div>
        </div>
        <div class="pnl-card">
            <div class="pnl-label">48-Hour PnL</div>
            <div class="pnl-value {'profit' if pnl_summary['pnl_48h'] > 0 else 'loss' if pnl_summary['pnl_48h'] < 0 else 'neutral'}">
                ${pnl_summary['pnl_48h']:,.2f}
            </div>
        </div>
        <div class="pnl-card">
            <div class="pnl-label">7-Day PnL</div>
            <div class="pnl-value {'profit' if pnl_summary['pnl_7d'] > 0 else 'loss' if pnl_summary['pnl_7d'] < 0 else 'neutral'}">
                ${pnl_summary['pnl_7d']:,.2f}
            </div>
        </div>
        <div class="pnl-card">
            <div class="pnl-label">30-Day PnL</div>
            <div class="pnl-value {'profit' if pnl_summary['pnl_30d'] > 0 else 'loss' if pnl_summary['pnl_30d'] < 0 else 'neutral'}">
                ${pnl_summary['pnl_30d']:,.2f}
            </div>
        </div>
    </div>
    """
    
    # 持仓前三
    top_positions_html = ""
    if top_positions:
        top_positions_rows = ""
        for pos in top_positions:
            pnl_class = "profit" if pos['unrealized_pnl'] > 0 else "loss" if pos['unrealized_pnl'] < 0 else "neutral"
            pnl_sign = "+" if pos['unrealized_pnl'] > 0 else ""
            top_positions_rows += f"""
            <tr>
                <td>{pos['coin']}</td>
                <td class="direction-{pos['direction_short'].lower()}">{pos['direction_short']}</td>
                <td>${pos['position_value']:,.2f}</td>
                <td class="pnl-{pnl_class}">{pnl_sign}${pos['unrealized_pnl']:,.2f}</td>
            </tr>
            """
        
        top_positions_html = f"""
        <div class="top-items">
            <h4>📊 持仓前三（按价值）</h4>
            <table class="mini-table">
                <thead>
                    <tr>
                        <th>币种</th>
                        <th>方向</th>
                        <th>价值</th>
                        <th>盈亏</th>
                    </tr>
                </thead>
                <tbody>
                    {top_positions_rows}
                </tbody>
            </table>
        </div>
        """
    
    # 挂单前三
    top_orders_html = ""
    if top_orders:
        top_orders_rows = ""
        for order in top_orders:
            top_orders_rows += f"""
            <tr>
                <td>{order['coin']}</td>
                <td>{order['side']}</td>
                <td>${order['price']:,.4f}</td>
                <td>${order['order_value']:,.2f}</td>
            </tr>
            """
        
        top_orders_html = f"""
        <div class="top-items">
            <h4>📋 挂单前三（按价值）</h4>
            <table class="mini-table">
                <thead>
                    <tr>
                        <th>币种</th>
                        <th>方向</th>
                        <th>价格</th>
                        <th>价值</th>
                    </tr>
                </thead>
                <tbody>
                    {top_orders_rows}
                </tbody>
            </table>
        </div>
        """
    
    # 生成完整持仓表格
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
    
    # 完整HTML
    html = f"""
<!-- 地址: {address} -->
<div class="address-section">
    <div class="address-header">
        <h3>地址: {address}</h3>
        <div class="address-stats">
            <div class="stat-item">
                <span class="stat-label">账户价值</span>
                <span class="stat-value">${account_value:,.2f}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">持仓价值</span>
                <span class="stat-value">${total_value:,.2f}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">持仓数</span>
                <span class="stat-value">{len(positions)}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">挂单数</span>
                <span class="stat-value">{len(open_orders)}</span>
            </div>
        </div>
    </div>
    
    {pnl_cards}
    
    <div class="top-items-container">
        {top_positions_html}
        {top_orders_html}
    </div>
    
    <div class="position-table">
        <h4>📈 完整持仓列表</h4>
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
</div>
"""
    return html


def generate_html_report(all_account_data: Dict[str, Dict], output_file: Path):
    """生成完整的HTML报告
    
    Args:
        all_account_data: 所有地址的账户数据
        output_file: 输出文件路径
    """
    # 计算汇总统计
    total_addresses = len(all_account_data)
    addresses_with_positions = sum(1 for data in all_account_data.values() if data.get('positions'))
    total_positions = sum(len(data.get('positions', [])) for data in all_account_data.values())
    generation_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 计算多空统计
    long_value = 0
    short_value = 0
    long_count = 0
    short_count = 0
    
    for data in all_account_data.values():
        for pos in data.get('positions', []):
            if pos['raw_szi'] > 0:  # 做多
                long_value += pos['position_value']
                long_count += 1
            elif pos['raw_szi'] < 0:  # 做空
                short_value += pos['position_value']
                short_count += 1
    
    # 计算多空比
    long_short_ratio = long_value / short_value if short_value > 0 else float('inf')
    long_percentage = (long_value / (long_value + short_value) * 100) if (long_value + short_value) > 0 else 0
    short_percentage = (short_value / (long_value + short_value) * 100) if (long_value + short_value) > 0 else 0
    
    # 格式化多空比显示
    if long_short_ratio == float('inf'):
        long_short_ratio_display = "∞ (仅做多)"
    elif long_short_ratio == 0:
        long_short_ratio_display = "0 (仅做空)"
    else:
        long_short_ratio_display = f"{long_short_ratio:.2f}"
    
    # 日志输出
    logging.info("=" * 80)
    logging.info("📊 多空持仓统计")
    logging.info("=" * 80)
    logging.info(f"🟢 做多: {long_count} 个持仓, 总价值: ${long_value:,.2f} ({long_percentage:.1f}%)")
    logging.info(f"🔴 做空: {short_count} 个持仓, 总价值: ${short_value:,.2f} ({short_percentage:.1f}%)")
    logging.info(f"📈 多空比: {long_short_ratio_display}")
    logging.info("=" * 80)
    
    # HTML头部
    html_header = f"""<!DOCTYPE html>
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
        
        /* 地址区域样式 */
        .address-section {{
            margin-bottom: 40px;
            background: #1a1f3a;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }}
        .address-header {{
            margin-bottom: 20px;
        }}
        .address-header h3 {{
            color: #fff;
            margin: 0 0 15px 0;
            font-size: 14px;
            word-break: break-all;
            border-bottom: 2px solid #2d3455;
            padding-bottom: 10px;
        }}
        .address-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
        }}
        .stat-item {{
            background: #252b4a;
            padding: 10px;
            border-radius: 4px;
            display: flex;
            flex-direction: column;
        }}
        .stat-item .stat-label {{
            font-size: 11px;
            color: #a8b3cf;
            margin-bottom: 5px;
        }}
        .stat-item .stat-value {{
            font-size: 18px;
            color: #fff;
            font-weight: 600;
        }}
        
        /* PnL卡片样式 */
        .pnl-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .pnl-card {{
            background: #252b4a;
            padding: 15px;
            border-radius: 4px;
            text-align: center;
        }}
        .pnl-label {{
            font-size: 11px;
            color: #a8b3cf;
            text-transform: uppercase;
            margin-bottom: 8px;
        }}
        .pnl-value {{
            font-size: 20px;
            font-weight: 700;
        }}
        .pnl-value.profit {{
            color: #52c41a;
        }}
        .pnl-value.loss {{
            color: #ff4d4f;
        }}
        .pnl-value.neutral {{
            color: #8c8c8c;
        }}
        
        /* 持仓前三和挂单前三 */
        .top-items-container {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .top-items {{
            background: #252b4a;
            padding: 15px;
            border-radius: 4px;
        }}
        .top-items h4 {{
            margin: 0 0 15px 0;
            color: #fff;
            font-size: 14px;
        }}
        .mini-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .mini-table th,
        .mini-table td {{
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid #2d3455;
            font-size: 13px;
        }}
        .mini-table th {{
            color: #a8b3cf;
            font-weight: 600;
            font-size: 11px;
            text-transform: uppercase;
        }}
        .mini-table td {{
            color: #e8e8e8;
        }}
        
        /* 完整持仓表格 */
        .position-table {{
            margin-top: 20px;
        }}
        .position-table h4 {{
            color: #fff;
            margin-bottom: 15px;
        }}
        .ant-table {{
            width: 100%;
            border-collapse: collapse;
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
            <div class="stat-card">
                <div class="stat-label">做多持仓</div>
                <div class="stat-value" style="color: #52c41a;">{long_count} 个 (${long_value:,.0f})</div>
                <div style="color: #a8b3cf; font-size: 12px; margin-top: 5px;">{long_percentage:.1f}%</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">做空持仓</div>
                <div class="stat-value" style="color: #ff4d4f;">{short_count} 个 (${short_value:,.0f})</div>
                <div style="color: #a8b3cf; font-size: 12px; margin-top: 5px;">{short_percentage:.1f}%</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">多空比 (Long/Short)</div>
                <div class="stat-value">{long_short_ratio_display}</div>
            </div>
        </div>
    </div>
"""
    
    # 生成每个地址的HTML
    address_htmls = []
    for address, data in all_account_data.items():
        address_html = generate_position_table_html(address, data)
        address_htmls.append(address_html)
    
    # 完整HTML
    html_content = html_header + '\n'.join(address_htmls) + "\n</body>\n</html>"
    
    # 写入文件
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logging.info(f"✅ 持仓信息已保存到: {output_file}")
    except Exception as e:
        logging.error(f"保存持仓信息失败: {e}")

