# Changelog V2.5.0

## 🎯 版本概览

**版本号**: V2.5.0  
**发布日期**: 2025-10-21  
**主题**: 智能缓存机制 + 账户数据汇总 + 模块化重构

---

## ✨ 新增功能

### 1. 智能缓存机制

**文件**: `position_manager.py`

新增缓存管理功能，避免频繁API调用：

- ✅ **5分钟自动刷新**: 缓存时间为300秒，过期自动更新
- ✅ **异步并发**: 支持多地址并发获取数据
- ✅ **锁机制**: 使用 `asyncio.Lock` 防止并发更新同一地址
- ✅ **强制刷新**: 支持 `force_refresh` 参数强制更新

**核心方法**:
```python
async def get_account_data_async(address, force_refresh=False)
    → 返回账户数据（带缓存）
```

**数据结构**:
```python
{
    'user_state': {...},           # 用户状态
    'address': str,                 # 用户地址
    'account_value': float,         # 账户总价值
    'total_position_value': float,  # 持仓总价值
    'positions': [...],             # 持仓列表
    'pnl_summary': {                # PnL汇总
        'total_pnl': float,
        'unrealized_pnl': float,
        'pnl_24h': float,           # 24小时PnL
        'pnl_48h': float,           # 48小时PnL
        'pnl_7d': float,            # 7天PnL
        'pnl_30d': float,           # 30天PnL
    },
    'open_orders': [...],           # 挂单列表
    'timestamp': str                # 数据时间戳
}
```

---

### 2. 账户数据汇总显示

**文件**: `monitor_whales.py` - `_notify_trade()` 方法

交易通知现在包含丰富的账户信息：

#### 📊 账户汇总
- 💼 账户总价值
- 📈 持仓总价值
- 💰 Total PnL
- 📅 阶段性PnL（24h/48h/7d/30d）

#### 🏆 持仓前三（按价值）
```
1. 🔴 BTC | $124,680,000.00 | PnL: +$3,580,000.00
2. 🟢 ETH | $2,340,000.00 | PnL: +$120,000.00
3. 🔴 HYPE | $890,000.00 | PnL: -$45,000.00
```

#### 📋 挂单前三（按价值）
```
1. 🟢 BTC | 买入 @ $65,000.0000 | 价值: $650,000.00
2. 🔴 ETH | 卖出 @ $3,500.0000 | 价值: $350,000.00
```

---

### 3. 定期数据更新

**文件**: `monitor_whales.py`

新增后台定期更新任务：

- ✅ **5分钟自动更新**: 后台异步任务定期刷新数据
- ✅ **自动生成报告**: 每次更新后重新生成HTML报告
- ✅ **优雅退出**: 支持取消任务，避免资源泄漏

**核心方法**:
```python
async def _periodic_data_update():
    while running:
        await asyncio.sleep(300)  # 5分钟
        await position_manager.update_and_generate_report_async(...)
```

---

### 4. 模块化重构

**新文件**: `create_html.py`

将HTML生成逻辑从 `position_manager.py` 中分离：

- ✅ **职责分离**: PositionManager只负责数据获取，HTML生成独立
- ✅ **更易维护**: HTML样式和逻辑集中管理
- ✅ **可扩展**: 方便添加新的显示组件

**核心函数**:
```python
def generate_position_table_html(address, account_data) → str
def generate_html_report(all_account_data, output_file) → None
```

---

### 5. 增强的HTML报告

**文件**: `create_html.py`

HTML报告新增以下内容：

#### 地址级别统计
- 账户总价值
- 持仓总价值
- 持仓数量
- 挂单数量

#### PnL卡片组
```html
[Total PnL] [24-Hour PnL] [48-Hour PnL] [7-Day PnL] [30-Day PnL]
```

#### 持仓前三 & 挂单前三
- 按价值排序的Top 3持仓
- 按价值排序的Top 3挂单
- 迷你表格展示，一目了然

---

## 🔧 修改内容

### position_manager.py

**新增**:
- `cache_ttl` - 缓存时间（300秒）
- `account_data_cache` - 数据缓存字典
- `update_locks` - 异步锁字典
- `get_account_data_async()` - 带缓存的数据获取
- `get_top_positions()` - 获取持仓前N
- `get_top_open_orders()` - 获取挂单前N
- `update_and_generate_report_async()` - 更新并生成报告

**删除**:
- `_save_html_report()` - 移至 `create_html.py`
- `generate_position_table_html()` - 移至 `create_html.py`

---

### monitor_whales.py

**新增**:
- `position_manager` - 持仓管理器实例（带缓存）
- `update_task` - 定期更新任务
- `_periodic_data_update()` - 定期更新方法
- 交易通知中的账户汇总、持仓前三、挂单前三显示

**修改**:
- `start_monitoring()` - 使用新的 `update_and_generate_report_async()`
- 启动定期更新任务
- 停止时取消定期更新任务

---

## 📈 性能优化

### 缓存效果
- ❌ **之前**: 每次交易通知都调用API获取数据（延迟高）
- ✅ **现在**: 使用5分钟缓存，交易通知秒级响应

### API调用优化
- ❌ **之前**: 每次事件都重新获取数据
- ✅ **现在**: 
  - 初始化时获取一次
  - 每5分钟后台刷新
  - 交易通知直接读缓存

### 并发控制
- ✅ 使用 `asyncio.Semaphore` 控制并发数（默认10）
- ✅ 使用 `asyncio.Lock` 防止重复更新

---

## 🧪 测试

新增测试脚本: `test_position_manager.py`

测试内容:
1. ✅ 首次获取数据（从API）
2. ✅ 再次获取（使用缓存）
3. ✅ 获取持仓前三
4. ✅ 获取挂单前三
5. ✅ 强制刷新

**运行测试**:
```bash
python3 test_position_manager.py
```

---

## 📝 API限制说明

### PnL数据获取

⚠️ **重要提示**: 

目前Hyperliquid API的 `user_state` 接口只提供：
- ✅ `unrealizedPnl` - 未实现盈亏（当前持仓）
- ❌ 不直接提供历史PnL（24h/7d/30d）

**当前实现**:
- `total_pnl` = 所有持仓的未实现盈亏总和
- `pnl_24h`, `pnl_7d`, `pnl_30d` = 0（占位）

**未来改进方向**:
1. 使用 `/info` 的其他接口（如果有）
2. 本地记录历史数据，计算差值
3. 集成Coinglass等第三方数据源

---

## 🔄 向后兼容性

### 保留的旧接口

为确保兼容性，保留了以下方法：

```python
# position_manager.py
async def fetch_and_log_positions_async(addresses, max_concurrent=10)
    → 返回 {address: [positions]} 字典（旧格式）
```

这个方法内部调用新的 `update_and_generate_report_async()`，并转换为旧格式。

---

## 🚀 使用示例

### 基本用法（自动缓存）

```python
from position_manager import PositionManager
from hyperliquid.info import Info
from hyperliquid.utils import constants

manager = PositionManager(Info, constants)

# 获取账户数据（自动使用缓存）
account_data = await manager.get_account_data_async(address)

# 获取持仓前3
top_positions = await manager.get_top_positions(address, top_n=3)

# 获取挂单前3
top_orders = await manager.get_top_open_orders(address, top_n=3)
```

### 批量更新并生成报告

```python
# 更新所有地址并生成HTML报告
all_data = await manager.update_and_generate_report_async(
    addresses=['0x...', '0x...'],
    max_concurrent=10,
    force_refresh=True  # 强制刷新
)
```

---

## 📚 相关文件

- ✅ `position_manager.py` - 核心逻辑
- ✅ `create_html.py` - HTML生成
- ✅ `monitor_whales.py` - 主程序
- ✅ `test_position_manager.py` - 测试脚本
- ✅ `README.md` - 更新文档
- ✅ `CHANGELOG_V2.5.0.md` - 本文件

---

## 🎯 下一步计划

1. **PnL历史数据** - 本地存储历史数据，计算24h/7d/30d PnL
2. **地址标签** - 从配置文件读取地址标签（昵称）
3. **通知优化** - 添加Telegram/Discord通知
4. **数据可视化** - 生成PnL曲线图、持仓分布图

---

## 🙏 致谢

感谢Hyperliquid团队提供的优秀API和SDK！

