# 地址过滤功能 - 快速开始

## 🎯 功能简介

屏蔽不想监控的地址，比如高频交易机器人，让监控更专注于有价值的交易信号。

## ⚡ 快速使用

### 1. 创建配置文件

创建 `address_filters.json`:

```json
{
  "filters": {
    "blocked_addresses": [
      "0xecb63caa47c7c4e77f60f1ce858cf28dc2b82b00"
    ],
    "blocked_keywords": [
      "bot",
      "robot"
    ]
  }
}
```

### 2. 运行监控器

```bash
python3 monitor_whales_v2.py
```

### 3. 查看过滤结果

启动时会显示：

```
================================================================================
📋 地址过滤统计
================================================================================
✅ 有效地址: 9 个
🚫 屏蔽地址: 1 个

🚫 已屏蔽的地址:
   1. 0xecb63caa47c7c4e77f60f1ce858cf28dc2b82b00 (Bot)
      原因: 在地址文件中标记为blocked
================================================================================
```

## 📋 三种过滤方式

### 1️⃣ 屏蔽特定地址

```json
{
  "filters": {
    "blocked_addresses": [
      "0xecb63caa47c7c4e77f60f1ce858cf28dc2b82b00",
      "0x另一个地址..."
    ]
  }
}
```

### 2️⃣ 屏蔽包含关键词的账户

```json
{
  "filters": {
    "blocked_keywords": [
      "bot",      // 匹配 "Trading Bot", "My bot" 等
      "robot",    // 匹配 "Robot Trader" 等
      "机器人"     // 匹配中文
    ]
  }
}
```

### 3️⃣ 屏蔽特定显示名称

```json
{
  "filters": {
    "blocked_display_names": [
      "Bot",           // 完全匹配 "Bot"
      "Test Account"   // 完全匹配 "Test Account"
    ]
  }
}
```

## 🔧 在地址文件中标记

编辑 `top_traders_addresses.json`:

```json
{
  "details": [
    {
      "ethAddress": "0xecb63caa47c7c4e77f60f1ce858cf28dc2b82b00",
      "displayName": "Bot",
      "block": true    // 添加这一行
    }
  ]
}
```

## 💡 常用配置

### 配置1: 屏蔽所有机器人

```json
{
  "filters": {
    "blocked_keywords": ["bot", "robot", "quant", "algo", "机器人", "量化"]
  }
}
```

### 配置2: 仅屏蔽特定地址

```json
{
  "filters": {
    "blocked_addresses": [
      "0xecb63caa47c7c4e77f60f1ce858cf28dc2b82b00"
    ]
  }
}
```

### 配置3: 组合使用

```json
{
  "filters": {
    "blocked_addresses": ["0xecb63caa47c7c4e77f60f1ce858cf28dc2b82b00"],
    "blocked_keywords": ["bot", "machine"],
    "blocked_display_names": ["Test Account"]
  }
}
```

## 📊 匹配规则对比

| 方式 | 匹配规则 | 大小写 | 示例 |
|------|---------|--------|------|
| `blocked_addresses` | 完全匹配 | 不敏感 | `0xabc...` |
| `blocked_display_names` | 完全匹配 | 敏感 | `"Bot"` ≠ `"bot"` |
| `blocked_keywords` | 包含匹配 | 不敏感 | `"bot"` 匹配 `"Trading Bot"` |

## 🚀 使用流程

```
1. 运行监控一段时间
   ↓
2. 观察哪些地址产生太多噪音
   ↓
3. 记录地址或显示名称
   ↓
4. 添加到 address_filters.json
   ↓
5. 重启监控器
   ↓
6. 享受清爽的监控！
```

## ⚠️ 注意事项

- ✅ 修改配置后需要**重启**监控器
- ✅ 关键词匹配**不区分大小写**
- ✅ 显示名称完全匹配**区分大小写**
- ✅ 被屏蔽的地址**不会创建WebSocket连接**
- ✅ 不创建 `address_filters.json` 也能正常运行

## 📖 详细文档

查看完整使用说明: [`地址过滤使用说明.md`](./地址过滤使用说明.md)

## 🆘 常见问题

**Q: 如何临时禁用所有过滤？**
```bash
# 重命名配置文件
mv address_filters.json address_filters.json.bak
```

**Q: 如何查看哪些地址被屏蔽了？**
```bash
# 启动监控器，会自动显示
python3 monitor_whales_v2.py
```

**Q: 可以同时使用多种过滤方式吗？**
```
可以！所有过滤规则会同时生效，任何一个匹配就会屏蔽。
```

## 🎁 推荐配置

对于大多数用户，推荐使用关键词过滤：

```json
{
  "description": "推荐配置 - 屏蔽常见机器人关键词",
  "filters": {
    "blocked_keywords": [
      "bot",
      "robot",
      "quant",
      "algo",
      "automated",
      "机器人",
      "量化",
      "自动化"
    ]
  }
}
```

这样可以自动屏蔽大部分机器人账户，无需手动维护地址列表！

---

**版本**: 1.0  
**更新**: 2025-10-16  
**作者**: Hyperliquid Monitor Team

