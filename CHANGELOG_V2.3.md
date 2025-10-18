# Hyperliquid 大户监控器 V2.3 更新日志

**发布日期**: 2025-10-18  
**版本**: V2.3

## 🎯 本次更新概览

本次更新主要修复了三个关键问题，并更新了文档：

1. ✅ **修复 Funding Fee 计算方向错误**
2. ✅ **添加多空持仓统计和大户多空比**
3. ✅ **修复交易监听逻辑 - 启用加仓/减仓通知**
4. ✅ **更新 README.md 文档**

---

## 📝 详细更新内容

### 1. 修复 Funding Fee 计算方向错误

**问题描述**：
- 资金费显示方向与实际盈亏相反
- 支付资金费（亏损）显示为正值
- 收到资金费（盈利）显示为负值

**修复方案**：
根据 Hyperliquid API 文档：
- API 返回的 `cumFunding` **正值** = 用户**支付**资金费（亏损）
- API 返回的 `cumFunding` **负值** = 用户**收到**资金费（盈利）

为了统一显示逻辑（正=盈利，负=亏损），对资金费进行符号反转：

```python
# position_manager.py 第79-82行
# 资金费 (cumFunding: 正值=支付/亏损, 负值=收到/盈利)
# 为了统一显示，转换为：正值=盈利，负值=亏损
cumulative_funding_raw = float(pos.get('cumFunding', {}).get('allTime', 0))
cumulative_funding = -cumulative_funding_raw  # 反转符号
```

**示例**：
- API 返回 `cumFunding: 66996.89` → 显示为 `-$66,996.89`（支付/亏损）
- API 返回 `cumFunding: -6190.81` → 显示为 `+$6,190.81`（收到/盈利）

---

### 2. 添加多空持仓统计功能

**新增功能**：
- 计算所有监控地址的做多/做空持仓总值
- 计算多空持仓数量
- 计算多空比（Long/Short Ratio）
- 在 HTML 报告顶部显示统计卡片
- 在日志中输出多空统计

**实现位置**：`position_manager.py` 第426-489行

**统计内容**：
1. **做多持仓**
   - 数量：X 个
   - 总价值：$XXX,XXX.XX
   - 占比：XX.X%

2. **做空持仓**
   - 数量：X 个
   - 总价值：$XXX,XXX.XX
   - 占比：XX.X%

3. **多空比**
   - 计算公式：`long_value / short_value`
   - 特殊情况：
     - 仅做多：显示 `∞ (仅做多)`
     - 仅做空：显示 `0 (仅做空)`
     - 正常：显示数值，如 `0.82`

**HTML 展示**：
在持仓报告顶部新增 3 个统计卡片：
```html
<div class="stat-card">
    <div class="stat-label">做多持仓</div>
    <div class="stat-value" style="color: #52c41a;">20 个 ($5,234,567) 45.2%</div>
</div>
<div class="stat-card">
    <div class="stat-label">做空持仓</div>
    <div class="stat-value" style="color: #ff4d4f;">25 个 ($6,345,678) 54.8%</div>
</div>
<div class="stat-card">
    <div class="stat-label">多空比 (Long/Short)</div>
    <div class="stat-value">0.82</div>
</div>
```

**日志输出**：
```
================================================================================
📊 多空持仓统计
================================================================================
🟢 做多: 15 个持仓, 总价值: $5,234,567.89 (42.3%)
🔴 做空: 25 个持仓, 总价值: $7,132,456.78 (57.7%)
📈 多空比: 0.73
================================================================================
```

---

### 3. 修复交易监听逻辑

**问题描述**：
从用户提供的日志可以看到：
```
2025-10-18 23:31:51,266 | DEBUG | 🔍 处理第 1/3 个fill - 币种: HYPE, 方向: 卖出(A), 数量: 2.92
2025-10-18 23:31:51,266 | DEBUG | 交易类型 '加仓' 不在通知范围内，已过滤
2025-10-18 23:31:51,266 | DEBUG | 🔇 交易不满足通知条件，已过滤
```

加仓和减仓操作被过滤，用户希望所有仓位调整都能被监听和通知。

**根本原因**：
配置文件中 `notify_on_add` 和 `notify_on_reduce` 设置为 `false`

**修复方案**：
1. 修改 `jsons/config.json`：
```json
"notify_on_add": true,     // 修改为 true
"notify_on_reduce": true,  // 修改为 true
```

2. 修改 `monitor_whales.py` 默认配置（第93-94行）：
```python
"notify_on_add": True,     # 从 False 改为 True
"notify_on_reduce": True,  # 从 False 改为 True
```

**效果**：
现在系统会通知以下所有类型的交易：
- ✅ 开仓 (notify_on_open)
- ✅ 平仓 (notify_on_close)
- ✅ 反向开仓 (notify_on_reverse)
- ✅ **加仓 (notify_on_add)** ← 新启用
- ✅ **减仓 (notify_on_reduce)** ← 新启用

---

### 4. 更新 README.md 文档

**更新内容**：

1. **版本号**：V2.2 → V2.3

2. **新特性说明**：
   - 添加 Funding Fee 修复说明
   - 添加多空持仓统计说明
   - 添加完整交易监听说明

3. **持仓报告章节**：
   - 新增总览统计卡片表格
   - 新增资金费说明和示例
   - 新增多空比说明

4. **配置章节**：
   - 更新配置示例，标注新启用的选项
   - 添加配置说明

5. **常见问题章节**：
   - 添加资金费问题解答
   - 添加加仓/减仓通知问题解答
   - 添加多空比查看问题解答

6. **功能特性章节**：
   - 重构为三个子分类：核心功能/报告功能/技术特性
   - 突出多空分析功能

7. **注意事项章节**：
   - 添加资金费理解说明
   - 更新持仓数据说明

8. **输出示例章节**：
   - 添加控制台输出示例
   - 展示多空统计输出

9. **版本历史章节**：
   - 添加 V2.3 版本记录

---

## 🔧 技术实现细节

### Funding Fee 反转逻辑

```python
# 原始 API 数据
cumFunding = {
    "allTime": "66996.89",  # 正值 = 用户支付了资金费（亏损）
    "sinceOpen": "1234.56"
}

# 处理逻辑
cumulative_funding_raw = float(pos.get('cumFunding', {}).get('allTime', 0))
# cumulative_funding_raw = 66996.89

cumulative_funding = -cumulative_funding_raw  # 反转符号
# cumulative_funding = -66996.89

# 显示时会自动格式化为 -$66,996.89
```

### 多空比计算逻辑

```python
# 遍历所有持仓
for pos_list in all_positions.values():
    for pos in pos_list:
        if pos['raw_szi'] > 0:  # szi 为正 = 做多
            long_value += pos['position_value']
            long_count += 1
        elif pos['raw_szi'] < 0:  # szi 为负 = 做空
            short_value += pos['position_value']
            short_count += 1

# 计算多空比
if short_value > 0:
    long_short_ratio = long_value / short_value
elif long_value > 0:
    long_short_ratio = float('inf')  # 仅做多
else:
    long_short_ratio = 0  # 仅做空或无持仓

# 计算百分比
total_value = long_value + short_value
long_percentage = (long_value / total_value * 100) if total_value > 0 else 0
short_percentage = (short_value / total_value * 100) if total_value > 0 else 0
```

---

## 📊 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `position_manager.py` | 修改 | 修复资金费计算，添加多空统计 |
| `monitor_whales.py` | 修改 | 更新默认配置，启用加仓/减仓通知 |
| `jsons/config.json` | 修改 | 启用加仓/减仓通知 |
| `README.md` | 修改 | 全面更新文档 |
| `CHANGELOG_V2.3.md` | 新增 | 本更新日志 |

---

## ✅ 测试验证

### 1. 资金费显示测试

**测试步骤**：
```bash
# 运行监控
python3 monitor_whales.py

# 查看生成的 positions/*.html
open positions/positions_*.html
```

**预期结果**：
- 做空 FARTCOIN，支付资金费 → 显示为红色负值 `-$66,996.89`
- 做空 2Z，收到资金费 → 显示为绿色正值 `+$6,190.81`

### 2. 多空统计测试

**测试步骤**：
```bash
# 查看日志输出
tail -f logs/*.log | grep "多空持仓统计"

# 查看 HTML 报告顶部统计卡片
open positions/positions_*.html
```

**预期结果**：
```
📊 多空持仓统计
🟢 做多: X 个持仓, 总价值: $XXX
🔴 做空: X 个持仓, 总价值: $XXX
📈 多空比: X.XX
```

### 3. 交易监听测试

**测试步骤**：
```bash
# 运行监控，等待交易发生
python3 monitor_whales.py

# 观察控制台输出
```

**预期结果**：
- 开仓 → 显示通知 ✅
- 平仓 → 显示通知 ✅
- 加仓 → 显示通知 ✅（之前被过滤）
- 减仓 → 显示通知 ✅（之前被过滤）
- 反向开仓 → 显示通知 ✅

---

## 🎯 使用建议

### 1. 理解资金费

- **正值（绿色）**：表示收到资金费，净盈利
- **负值（红色）**：表示支付资金费，净亏损
- 资金费与持仓方向和市场资金费率有关
- 长期支付资金费会降低整体收益

### 2. 解读多空比

- **多空比 > 1**：做多价值大于做空，偏多头
- **多空比 < 1**：做空价值大于做多，偏空头
- **多空比 = 0.5**：做空价值是做多的2倍
- **多空比 = 2.0**：做多价值是做空的2倍

### 3. 配置过滤

如果交易通知太多，可以：

```json
// jsons/config.json
{
  "monitor": {
    "notify_on_add": false,      // 关闭加仓通知
    "notify_on_reduce": false,   // 关闭减仓通知
    "min_position_size": 1000    // 只通知 ≥ $1000 的交易
  }
}
```

---

## 🚀 升级指南

### 从 V2.2 升级到 V2.3

1. **拉取最新代码**：
```bash
git pull origin main
```

2. **无需修改配置** - 配置文件已自动更新

3. **重启监控**：
```bash
python3 monitor_whales.py
```

4. **验证功能**：
- 查看日志是否显示多空统计
- 打开 HTML 报告查看统计卡片
- 确认资金费显示正确（正=盈利，负=亏损）
- 观察是否收到加仓/减仓通知

---

## 📞 问题反馈

如果遇到问题：

1. **查看日志**：`tail -50 logs/*.log`
2. **检查配置**：`cat jsons/config.json`
3. **验证数据**：对比 API 原始数据和显示值

---

**发布者**: AI Assistant  
**审核**: 用户  
**状态**: ✅ 已发布


