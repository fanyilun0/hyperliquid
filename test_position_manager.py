#!/usr/bin/env python3
"""
测试持仓管理器的缓存和数据获取功能
"""
import asyncio
import logging
from position_manager import PositionManager

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def test_position_manager():
    """测试持仓管理器"""
    try:
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
    except ImportError:
        print("❌ 未找到 hyperliquid-python-sdk")
        return
    
    # 测试地址（示例）
    test_address = "0x5d2f4460ac3514ada79f5d9838916e508ab39bb7"
    
    # 创建持仓管理器
    manager = PositionManager(Info, constants)
    
    print("\n" + "=" * 80)
    print("测试1: 首次获取账户数据（应该从API获取）")
    print("=" * 80)
    
    account_data_1 = await manager.get_account_data_async(test_address)
    
    if account_data_1:
        print(f"✅ 账户价值: ${account_data_1['account_value']:,.2f}")
        print(f"✅ 持仓价值: ${account_data_1['total_position_value']:,.2f}")
        print(f"✅ 持仓数量: {len(account_data_1['positions'])}")
        print(f"✅ 挂单数量: {len(account_data_1.get('open_orders', []))}")
        
        # 显示PnL
        pnl_summary = account_data_1.get('pnl_summary', {})
        print(f"✅ Total PnL: ${pnl_summary.get('total_pnl', 0):,.2f}")
    
    print("\n" + "=" * 80)
    print("测试2: 再次获取（应该使用缓存）")
    print("=" * 80)
    
    account_data_2 = await manager.get_account_data_async(test_address)
    
    if account_data_2:
        print(f"✅ 使用缓存数据")
        print(f"   账户价值: ${account_data_2['account_value']:,.2f}")
    
    print("\n" + "=" * 80)
    print("测试3: 获取持仓前三")
    print("=" * 80)
    
    top_positions = await manager.get_top_positions(test_address, top_n=3)
    
    if top_positions:
        for idx, pos in enumerate(top_positions, 1):
            print(f"{idx}. {pos['coin']} | ${pos['position_value']:,.2f} | PnL: ${pos['unrealized_pnl']:,.2f}")
    else:
        print("无持仓")
    
    print("\n" + "=" * 80)
    print("测试4: 获取挂单前三")
    print("=" * 80)
    
    top_orders = await manager.get_top_open_orders(test_address, top_n=3)
    
    if top_orders:
        for idx, order in enumerate(top_orders, 1):
            print(f"{idx}. {order['coin']} | {order['side']} @ ${order['price']:,.4f} | 价值: ${order['order_value']:,.2f}")
    else:
        print("无挂单")
    
    print("\n" + "=" * 80)
    print("测试5: 强制刷新")
    print("=" * 80)
    
    account_data_3 = await manager.get_account_data_async(test_address, force_refresh=True)
    
    if account_data_3:
        print(f"✅ 强制刷新完成")
        print(f"   账户价值: ${account_data_3['account_value']:,.2f}")

if __name__ == "__main__":
    asyncio.run(test_position_manager())

