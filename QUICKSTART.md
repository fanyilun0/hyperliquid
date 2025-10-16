# 快速开始指南

## 🚀 一键启动

### 方法一：使用脚本（推荐）

```bash
# 1. 安装依赖
./install.sh

# 2. 启动监控（会自动筛选地址）
./start_monitor.sh
```

### 方法二：手动执行

```bash
# 1. 安装依赖
pip3 install -r requirements.txt

# 2. 筛选大户地址
python3 filter_top_traders.py

# 3. 启动监控
python3 monitor_whales.py
```

## 📊 输出示例

### 第一步：筛选大户

运行 `python3 filter_top_traders.py` 后，会看到：

```
================================================================================
正收益前10名交易者 (时间窗口: allTime)
================================================================================

排名 #1
  地址: 0x77c3ea550d2da44b120e55071f57a108f8dd5e45
  账户价值: $71,676,909.60
  盈亏 (PnL): $298,525,708.14
  收益率 (ROI): 126.61%
  交易量: $193.33

排名 #2
  地址: 0xfae95f601f3a25ace60d19dbb929f2a5c57e3571
  账户价值: $126,378,478.74
  盈亏 (PnL): $152,487,197.63
  收益率 (ROI): 3546.59%
  交易量: $4,655,922.47
  显示名: thank you jefef

...
```

### 第二步：实时监控

运行 `python3 monitor_whales.py` 后，会看到：

```
🚀 监控器初始化完成
📍 API端点: https://api.hyperliquid.xyz/info
👥 监控地址数: 10

================================================================================
开始监控 10 个大户地址
================================================================================

1. 0x77c3ea550d2da44b120e55071f57a108f8dd5e45
2. 0xfae95f601f3a25ace60d19dbb929f2a5c57e3571
...

================================================================================
🎯 监控中... (按Ctrl+C停止)
================================================================================

🟢 开仓 | 2025-10-15T14:30:25.123456
   用户: 0x77c3ea55...8dd5e45
   币种: BTC
   方向: 买入
   数量: 1.5
   价格: $67,890.00
   仓位: 0.0000 → 1.5000

🔴 平仓 | 2025-10-15T14:35:12.654321
   用户: 0xfae95f60...c57e3571
   币种: ETH
   方向: 卖出
   数量: 10.0
   价格: $3,456.78
   仓位: 10.0000 → 0.0000
   💰 已实现盈亏: $12,345.67
```

## 🎯 自定义筛选条件

编辑 `filter_top_traders.py`，修改最后几行：

### 选择不同时间窗口

```python
# 可选: 'day' (日), 'week' (周), 'month' (月), 'allTime' (全时)
addresses = get_top_traders(top_n=10, time_window="month")
```

### 更改监控数量

```python
# 最多10个（受API限制）
addresses = get_top_traders(top_n=5, time_window="allTime")
```

## ⚙️ 高级配置

### 后台运行

使用 `screen` 或 `nohup` 保持监控程序运行：

```bash
# 使用 screen
screen -S whale_monitor
python3 monitor_whales.py
# 按 Ctrl+A 然后按 D 退出，程序继续运行
# 重新连接: screen -r whale_monitor

# 使用 nohup
nohup python3 monitor_whales.py > monitor.log 2>&1 &
# 查看日志: tail -f monitor.log
```

### 定时更新排行榜

创建 cron 任务每小时更新一次：

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每小时第0分钟执行）
0 * * * * cd /Users/zou-macmini-m4/Desktop/github-repos/hyperliquid && curl -s -o leaderboard.json https://stats-data.hyperliquid.xyz/Mainnet/leaderboard && python3 filter_top_traders.py
```

## 🔍 故障排查

### 问题1：找不到 hyperliquid-python-sdk

```bash
pip3 install hyperliquid-python-sdk
```

### 问题2：WebSocket连接失败

检查网络连接，确保可以访问 `api.hyperliquid.xyz`

### 问题3：监控超过10个地址

由于API限制，单个IP最多监控10个地址。如需更多：
- 使用代理池分散IP
- 部署到多台服务器
- 修改代码，批次轮换监控

## 📝 文件说明

| 文件 | 自动生成 | 说明 |
|------|---------|------|
| `leaderboard.json` | ✅ | 排行榜数据（需手动更新） |
| `top_traders_addresses.json` | ✅ | 筛选后的地址列表 |
| `filter_top_traders.py` | ❌ | 筛选脚本 |
| `monitor_whales.py` | ❌ | 监控脚本 |
| `requirements.txt` | ❌ | 依赖列表 |

## 🎨 扩展功能建议

1. **通知集成**
   - Telegram Bot
   - Discord Webhook
   - 邮件通知

2. **数据持久化**
   - SQLite 数据库
   - CSV 导出
   - 交易历史记录

3. **分析功能**
   - 跟单收益计算
   - 胜率统计
   - 持仓时长分析

4. **可视化**
   - Web 仪表盘
   - 实时图表
   - 交易热力图

## ❓ 常见问题

**Q: 可以监控更多地址吗？**  
A: 受API限制，单IP最多10个。需要更多请使用多IP部署。

**Q: 数据多久更新一次？**  
A: 排行榜是快照数据（分钟级），交易事件是实时推送。

**Q: 如何停止监控？**  
A: 按 `Ctrl+C` 停止程序。

**Q: 会错过交易吗？**  
A: WebSocket会自动重连，但网络断开期间可能错过事件。

**Q: 消耗多少资源？**  
A: 非常轻量，CPU和内存占用都很小，主要是网络带宽。

## 📚 参考文档

- [技术方案详解](guide.md)
- [完整 README](README.md)
- [Hyperliquid 官方文档](https://hyperliquid.gitbook.io/hyperliquid-docs/)

