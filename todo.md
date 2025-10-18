项目目录

├── docs
├── filter_top_traders.py
├── get_coinglass_range9.py
├── install.sh
├── jsons
│   ├── address_filters.json
│   ├── config.json
│   ├── evm_address.json
│   ├── leaderboard.json
│   └── top_traders_addresses.json
├── logs
│   ├── 20251018_231709.log
│   └── 20251018_232617.log
├── monitor_whales.py
├── position_manager.py
├── positions
│   └── positions_20251018_232617.html
├── README.md
├── requirements.txt
└── start_monitor.sh

需求： 
1. 现在计算funding fee得方向错误了，盈利被计算为亏损； 根据文档，并正确展示持仓信息中的funding fee
2. 持仓信息中统计监听数据中的多空持仓总值， 并输出大户多空比
3. 2025-10-18 23:31:51,266 | DEBUG | 📨 收到用户事件 - 用户: 0x856c35038594767646266bc7fd68dc26480e910d
2025-10-18 23:31:51,266 | DEBUG | 📋 事件数据结构: ['channel', 'data']
2025-10-18 23:31:51,266 | DEBUG | 📦 数据内容类型: ['fills']
2025-10-18 23:31:51,266 | DEBUG | ✅ 收到 3 个fill事件
2025-10-18 23:31:51,266 | DEBUG | 🔍 处理第 1/3 个fill - 币种: HYPE, 方向: 卖出(A), 数量: 2.92
2025-10-18 23:31:51,266 | DEBUG | 交易类型 '加仓' 不在通知范围内，已过滤
2025-10-18 23:31:51,266 | DEBUG | 🔇 交易不满足通知条件，已过滤
2025-10-18 23:31:51,267 | DEBUG | 🔍 处理第 2/3 个fill - 币种: HYPE, 方向: 卖出(A), 数量: 16.69
2025-10-18 23:31:51,267 | DEBUG | 交易类型 '加仓' 不在通知范围内，已过滤
2025-10-18 23:31:51,267 | DEBUG | 🔇 交易不满足通知条件，已过滤
2025-10-18 23:31:51,267 | DEBUG | 🔍 处理第 3/3 个fill - 币种: HYPE, 方向: 卖出(A), 数量: 8.66
2025-10-18 23:31:51,267 | DEBUG | 交易类型 '加仓' 不在通知范围内，已过滤
2025-10-18 23:31:51,267 | DEBUG | 🔇 交易不满足通知条件，已过滤


这个监听中逻辑中为什么不满足通知范围？ 如何调整？
希望仓位调整操作都正确被监听并通知。
4. 更新后调整文档readme.md
