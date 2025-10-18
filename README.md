# Hyperliquid 大户监控器 V2.2

> 监控 Hyperliquid 交易所大户交易活动，自动生成 HTML 持仓报告

## 🎯 V2.2 新特性 (2025-10-18)

✅ **修复日志文件生成错误** - 解决 `IsADirectoryError`  
✅ **独立持仓管理模块** - 拆离 `position_manager.py`  
✅ **HTML 持仓报告** - 自动生成美观的 `logs/positions.log`  

## 🚀 快速开始

```bash
# 1. 运行监控
python3 monitor_whales_v2.py

# 2. 查看持仓报告
open logs/positions.log

# 3. 查看交易日志
tail -f logs/20251018_*.log
```

## 📊 HTML 持仓报告

### 表格字段

| 字段 | 说明 | 示例 |
|------|------|------|
| 代币 | 币种 | HYPE, BTC |
| 方向 | Long/Short | 🟢 Long, 🔴 Short |
| 杠杆 | 倍数 | 10x |
| 价值 | 美元 | $3,571.77 |
| 数量 | 仓位 | 100.5000 |
| 开仓价格 | 入场价 | $35.5450 |
| 盈亏(PnL) | 未实现 | 🟢 +$125.50 |
| 资金费 | 累计 | 🔴 -$12.34 |
| 爆仓价格 | 清算价 | $32.0000 |

### 颜色标识

- 🟢 **绿色** = 做多 / 盈利
- 🔴 **红色** = 做空 / 亏损
- ⚪ **灰色** = 中性

## 📁 项目结构

```
hyperliquid/
├── monitor_whales_v2.py          # 主程序
├── position_manager.py           # 持仓管理器（新）
├── config.json                   # 配置文件
├── top_traders_addresses.json    # 监控地址
├── logs/
│   ├── positions.log            # HTML 持仓报告（自动生成）
│   └── YYYYMMDD_HHMMSS.log     # 交易日志
└── 文档/
    ├── 快速使用指南_V2.2.md      # ⭐ 推荐阅读
    ├── POSITION_MANAGER_README.md # API 文档
    └── 改进总结_V2.2.md          # 改进详情
```

## ⚙️ 配置

`config.json` - 无需修改，开箱即用：

```json
{
  "monitor": {
    "max_addresses": 20,
    "notify_on_open": true,
    "notify_on_close": true,
    "min_position_size": 0
  },
  "notification": {
    "log_file": "logs/"  // 自动生成时间戳日志
  },
  "debug": true
}
```

## 🧪 测试验证

```bash
# 运行验证脚本
python3 verify_fixes.py

# 预期输出
🎉 所有检查通过！系统已就绪。
```

## 📚 文档

| 文档 | 说明 |
|------|------|
| **快速使用指南_V2.2.md** | ⭐ 快速开始 |
| **POSITION_MANAGER_README.md** | API 详细说明 |
| **改进总结_V2.2.md** | 技术实现 |
| **FINAL_SUMMARY.md** | 完成总结 |

## 🔧 常见问题

### Q: 日志文件错误？
```bash
# 确认 logs 是目录
ls -ld logs/
```

### Q: positions.log 是空的？
```bash
# 查看日志
grep "持仓信息已保存" logs/20251018_*.log
```

### Q: 如何验证系统？
```bash
python3 verify_fixes.py
```

## 📈 功能特性

- ✅ 实时监控大户交易
- ✅ 自动获取持仓信息
- ✅ 生成 HTML 持仓报告
- ✅ 暗色主题 + 颜色标识
- ✅ 完整的 9 个字段
- ✅ 响应式布局设计
- ✅ 模块化代码结构

## ⚠️ 注意事项

1. **持仓数据** - 启动时的快照，不自动刷新
2. **HTML 文件** - 每次运行覆盖 `positions.log`
3. **API 限制** - 建议监控 ≤ 20 个地址
4. **浏览器** - 使用现代浏览器打开 HTML

## 🎯 下一步

```bash
# 1. 运行程序
python3 monitor_whales_v2.py

# 2. 查看报告
open logs/positions.log

# 3. 实时监控
tail -f logs/*.log
```

## 📞 获取帮助

1. 查看 **快速使用指南_V2.2.md**
2. 运行 `python3 verify_fixes.py`
3. 查看日志 `tail -50 logs/*.log`
4. 参考 [Hyperliquid API 文档](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint)

---

**版本**: V2.2  
**日期**: 2025-10-18  
**状态**: ✅ 生产就绪

**祝交易监控顺利！** 🚀

