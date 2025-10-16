# 更新日志

## 2025-10-16 (晚) - 美化日志输出和修复币种显示

### 改进内容

#### 1. 美化日志输出
- ✅ 使用更多emoji使日志更易读
- ✅ 显示完整的用户地址（不再截断）
- ✅ 使用分隔线和结构化格式
- ✅ 增强调试日志的可读性

#### 2. 修复币种显示问题
- ✅ 支持解析 `@107` 格式的资产ID
- ✅ 自动从API获取资产名称
- ✅ 实现资产名称缓存机制
- ✅ 同时支持perps和spot资产

#### 3. 修正交易方向显示
- ✅ 根据官方文档，正确处理side字段:
  - `'B'` = Bid (买入/做多)
  - `'A'` = Ask (卖出/做空)
- ✅ 显示中英文对照: "买入 (Bid)" / "卖出 (Ask)"

### 新增功能

**资产名称解析**
```python
def _get_coin_name(self, coin_id: str) -> str:
    """将 @107 这样的资产ID转换为实际币种名称"""
```

### 日志输出示例

**之前**:
```
🔄 反向开仓 | 2025-10-16T20:53:44.139912
   用户: 0xecb63caa...c2b82b00
   币种: MELANIA
   方向: 卖出
   数量: 343.3
   价格: $0.12
   仓位: 150.7000 → -192.6000
   📉 已实现盈亏: $-2.37
```

**现在**:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄  反向开仓  🔄
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ 时间: 2025-10-16 20:53:44.139912
👤 用户: 0xecb63caa47c7c4e77f60f1ce858cf28dc2b82b00
────────────────────────────────────────────────────────────────────────────────
💎 币种: MELANIA
📊 方向: 卖出 (Ask)
📈 数量: 343.3000
💵 价格: $0.1200
📉 仓位: 150.7000 → -192.6000 (变化: -343.4000)
💸 已实现盈亏: $-2.37 (亏损)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 调试日志改进

**之前**:
```
2025-10-16 20:53:46,016 | DEBUG | 收到用户事件 - 用户: 0xecb63caa...c2b82b00
2025-10-16 20:53:46,016 | DEBUG | 处理第 1/2 个fill - 币种: @107, 方向: A, 数量: 49.7
```

**现在**:
```
2025-10-16 20:53:46,016 | DEBUG | 📨 收到用户事件 - 用户: 0xecb63caa47c7c4e77f60f1ce858cf28dc2b82b00
2025-10-16 20:53:46,016 | DEBUG | 🔍 处理第 1/2 个fill - 币种: @107, 方向: 卖出(A), 数量: 49.7
```

### 日志文件格式

**之前**:
```
反向开仓 | 0xecb63caa...c2b82b00 | MELANIA | 卖出 343.3 @ $0.12 | PnL: $-2.37
```

**现在**:
```
反向开仓 | 0xecb63caa47c7c4e77f60f1ce858cf28dc2b82b00 | MELANIA | 卖出 (Ask) 343.3000 @ $0.1200 | 仓位: 150.7000 → -192.6000 | PnL: $-2.37
```

### 参考文档
- [Hyperliquid WebSocket Subscriptions](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket/subscriptions)
- [Hyperliquid Info Endpoint](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint)

---

## 2025-10-16 (早) - 修复多用户订阅问题

### 问题描述
运行 `monitor_whales_v2.py` 时,第一个地址订阅成功,但后续地址都报错:
```
Cannot subscribe to userEvents multiple times
```

### 根本原因
Hyperliquid的WebSocket API对于 `userEvents` 类型的订阅有限制:
- 单个WebSocket连接不能多次订阅 `userEvents`
- 需要为每个用户创建独立的 `Info` 实例(即独立的WebSocket连接)

### 解决方案

#### 1. 修改订阅策略
**之前**: 使用单个 `Info` 实例,循环订阅多个用户
```python
self.info = Info(constants.MAINNET_API_URL, skip_ws=False)
for address in self.addresses:
    self.info.subscribe(...)  # ❌ 第二次订阅会失败
```

**现在**: 为每个用户创建独立的 `Info` 实例
```python
self.info_instances = {}
for address in self.addresses:
    info = Info(constants.MAINNET_API_URL, skip_ws=False)
    self.info_instances[address] = info
    info.subscribe(...)  # ✅ 每个连接只订阅一次
```

#### 2. 增强调试日志
- 添加 `debug` 配置选项到 `config.json`
- 在订阅前后输出详细的调试信息
- 在事件处理函数中添加详细日志
- 支持通过配置文件控制DEBUG模式

### 修改的文件

1. **monitor_whales_v2.py**
   - 修改 `setup_logging()` 函数,支持debug参数
   - 修改 `WhaleMonitor.__init__()`,存储SDK类而非实例
   - 修改 `WhaleMonitor.start_monitoring()`,为每个用户创建独立连接
   - 增强 `_handle_user_event()` 的调试日志
   - 更新主函数,支持从配置文件读取debug设置

2. **config.json**
   - 添加 `"debug": true` 配置项,启用详细日志

### 使用方法

#### 启用DEBUG模式
编辑 `config.json`:
```json
{
  ...
  "debug": true
}
```

#### 关闭DEBUG模式
编辑 `config.json`:
```json
{
  ...
  "debug": false
}
```

### 注意事项

1. **资源消耗**: 每个用户都会创建独立的WebSocket连接,会增加系统资源消耗
2. **连接数限制**: Hyperliquid限制每个IP最多监控10个用户
3. **延迟控制**: 代码中添加了0.2秒延迟,避免连接创建过快
4. **日志输出**: DEBUG模式会产生大量日志,建议只在调试时启用

### 验证步骤

1. 确保 `config.json` 中 `debug` 设置为 `true`
2. 运行: `python3 monitor_whales_v2.py`
3. 观察日志输出,应该看到:
   - 每个地址的详细订阅过程
   - WebSocket连接创建信息
   - 订阅成功/失败的详细状态

### 预期输出
```
2025-10-16 20:XX:XX,XXX | INFO | ================================================================================
2025-10-16 20:XX:XX,XXX | INFO | Hyperliquid 大户监控器 V2
2025-10-16 20:XX:XX,XXX | INFO | ================================================================================
2025-10-16 20:XX:XX,XXX | INFO | 配置文件: config.json
2025-10-16 20:XX:XX,XXX | INFO | 日志文件: trades.log
2025-10-16 20:XX:XX,XXX | INFO | DEBUG模式: 开启
2025-10-16 20:XX:XX,XXX | INFO | ================================================================================
2025-10-16 20:XX:XX,XXX | INFO | DEBUG模式已启用
2025-10-16 20:XX:XX,XXX | DEBUG | SDK导入成功
2025-10-16 20:XX:XX,XXX | INFO | 监控器初始化完成，监控 10 个地址
...
2025-10-16 20:XX:XX,XXX | INFO | ✅ 已订阅 [1/10]: 0x77c3ea550d2da44b120e55071f57a108f8dd5e45
2025-10-16 20:XX:XX,XXX | INFO | ✅ 已订阅 [2/10]: 0xfae95f601f3a25ace60d19dbb929f2a5c57e3571
...
```

### 相关文档
- [Hyperliquid API文档](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api)
- [hyperliquid-python-sdk](https://github.com/hyperliquid-dex/hyperliquid-python-sdk)

