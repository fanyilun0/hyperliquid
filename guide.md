

# **使用Python监控Hyperliquid大户交易的实施方案**

## **摘要**

本方案旨在提供一个清晰、可执行的技术路径，用于通过Hyperliquid官方数据源和Python语言，构建一个实时监控大户（或称“巨鲸”）交易活动的系统。方案将分为两个核心部分：首先，如何可靠地获取顶级交易者的钱包地址列表；其次，如何利用官方Python SDK实时监听这些地址的交易事件，并解析出开仓、平仓等关键行为。  
---

## **第一部分：获取大户钱包地址**

监控系统的第一步是确定监控目标。我们将采用Hyperliquid官方提供的免费API来获取顶级交易者的钱包地址，这是一种稳定且可靠的方法。

### **1.1. 数据源：Hyperliquid排行榜API**

Hyperliquid提供了一个专门用于统计和排行榜数据的API端点。虽然此端点未在其主要的API文档中突出显示，但通过分析社区开发的SDK可以确认其存在和可靠性 1。  
API端点:  
https://stats-data.hyperliquid.xyz/Mainnet/leaderboard  
通过向此URL发送一个标准的HTTP GET请求，即可获取排行榜数据。返回的JSON数据中会包含一个交易者列表，每个对象通常会包含user（用户地址）、pnl（盈利）、volume（交易量）等关键信息 1。  
这种方法的核心优势在于其**官方性**、**免费性**和**简便性**。您直接从协议方获取数据，无需支付任何订阅费用，也无需处理复杂的网页抓取或数据清洗工作。  
值得注意的是，Hyperliquid的系统架构将核心交易功能（api.hyperliquid.xyz）与分析统计功能（stats-data.hyperliquid.xyz）分开部署 1。这是一种常见的高性能架构模式，但也意味着排行榜数据的更新可能是分钟级的快照，而非逐笔实时。因此，此数据源非常适合用于**周期性地识别和更新**您的监控目标列表。

### **1.2. 实施策略**

您的Python应用程序应包含一个定时任务（例如，每小时执行一次），该任务会调用上述API端点，获取最新的顶级交易者列表，并更新您本地的监控地址池。  
---

## **第二部分：使用Python SDK进行实时监控**

在获得目标地址列表后，我们将使用官方的hyperliquid-python-sdk来连接WebSocket并实时监控交易事件。

### **2.1. 关键工具：hyperliquid-python-sdk**

强烈建议使用官方提供的Python SDK (hyperliquid-python-sdk) 2。该SDK封装了与Hyperliquid API交互的复杂细节，让开发者可以专注于业务逻辑。它能自动处理：

* WebSocket连接的建立与维护（包括心跳和自动重连） 3。  
* API请求的签名和Nonce管理 3。  
* 速率限制的处理 3。

### **2.2. 订阅用户事件 (userEvents)**

要监控特定用户的交易活动，最有效的方式是订阅userEvents数据流 4。使用SDK，您可以为从排行榜获取的每个地址发起一个订阅。  
订阅请求的底层JSON结构如下 4：

JSON

{  
  "method": "subscribe",  
  "subscription": {   
    "type": "userEvents",   
    "user": "\<目标钱包地址\>"   
  }  
}

当订阅成功后，您将收到一个包含多种事件类型的实时数据流，其中对我们最重要的是fills事件，它代表一笔已执行的交易 4。

### **2.3. 解析fills事件并重构持仓状态**

WebSocket推送的是描述变化的“增量”数据，而非完整的“状态”快照。因此，您的应用程序需要在本地内存中为每个监控地址维护其当前的仓位状态。  
当收到一个fills事件时，其数据结构（WsFill）会包含以下关键字段 4：

| 字段名 | 描述 | 作用 |
| :---- | :---- | :---- |
| coin | 资产名称 (例如 "BTC") | 识别持仓所属的资产 |
| px | 成交价格 | 计算持仓成本和盈亏 |
| sz | 成交数量 | 计算持仓规模变化的核心数据 |
| side | 交易方向 ('B' 为买, 'S' 为卖) | 判断仓位是增加还是减少 |
| startPosition | 成交前的起始仓位 | 用于验证和校准本地维护的仓位状态 |
| closedPnl | 该笔成交平仓部分实现的盈亏 | 追踪已实现的利润或亏损 |

核心逻辑：  
要准确判断一次成交是“开仓”还是“平仓”，必须结合成交前的仓位状态。

1. **初始化**：为每个监控的用户-资产对维护一个仓位变量，初始为0。例如：positions \= {'0x...': {'BTC': 0.0}}。  
2. **处理事件**：收到WsFill事件后，根据side和sz计算仓位变化量 (delta)。  
3. **更新状态**：new\_position \= old\_position \+ delta。  
4. **识别行为**：  
   * 若old\_position为0，new\_position不为0，则为**开仓**。  
   * 若old\_position不为0，new\_position为0，则为**平仓**。  
   * 若old\_position和new\_position符号相反，则为**仓位翻转**。  
   * 其他情况为**仓位调整**。

通过实现这个状态机，您的程序就能将底层的成交数据流转换成具有明确业务含义的高级事件。  
---

## **第三部分：架构与关键注意事项**

### **3.1. 简化架构**

对于一个基于Python的实现，可以采用一个简单的单体应用架构：

1. **地址收集器 (Collector)**：一个独立的线程或定时函数，负责周期性调用排行榜API并更新目标地址列表。  
2. **监控管理器 (Monitor)**：主工作线程，负责管理与Hyperliquid的WebSocket连接。它会根据地址列表的变化，动态地添加或取消userEvents订阅。  
3. **事件处理器 (Processor)**：在WebSocket的回调函数中实现，负责处理接收到的fills事件，并根据2.3节的逻辑更新仓位状态、识别交易行为。  
4. **输出/警报 (Alerter)**：当处理器识别出“开仓”或“平仓”等关键事件后，触发相应动作，如打印到控制台、写入日志文件或通过其他服务发送通知。

### **3.2. 重要的协议限制**

在实施过程中，必须注意Hyperliquid的一项关键WebSocket订阅限制：**“每个IP地址最多只能订阅10个唯一用户的用户特定事件”** 5。  
这意味着，如果您从单个服务器或IP地址运行您的程序，您最多只能同时监控10个大户。如果您的目标是监控超过10个地址，您的架构**必须**支持分布式部署，例如通过使用代理服务器池将WebSocket连接分散到多个IP地址上，或者将程序部署到多个不同的服务器实例上。这是一个决定系统扩展能力的核心技术约束。  
---

## **结论与实施路径**

结合以上分析，推荐的实施路径如下：

1. **环境准备**：安装Python并使用pip安装hyperliquid-python-sdk。  
2. **开发地址获取模块**：编写一个函数，通过HTTP请求访问https://stats-data.hyperliquid.xyz/Mainnet/leaderboard，解析返回的JSON并提取用户地址列表。  
3. **开发监控模块**：  
   * 使用hyperliquid-python-sdk建立WebSocket连接。  
   * 为获取到的地址列表订阅userEvents。  
   * 在WebSocket消息回调中，实现持仓状态机逻辑，以区分开仓、平仓等事件。  
4. **注意扩展性**：在设计时就要考虑到每个IP最多监控10个用户的限制，为未来可能的扩展预留架构上的灵活性。

遵循此路径，您将能够构建一个功能强大且数据来源可靠的Hyperliquid大户交易监控工具。

#### **引用的著作**

1. hyperliquid-go command \- github.com/cordilleradev/hyperliquid-go \- Go Packages, 访问时间为 十月 15, 2025， [https://pkg.go.dev/github.com/cordilleradev/hyperliquid-go](https://pkg.go.dev/github.com/cordilleradev/hyperliquid-go)  
2. API \- Hyperliquid Docs \- GitBook, 访问时间为 十月 15, 2025， [https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api)  
3. Simple and easy way to access the Hyperliquid API using Javascript/Typescript \- GitHub, 访问时间为 十月 15, 2025， [https://github.com/nomeida/hyperliquid](https://github.com/nomeida/hyperliquid)  
4. Subscriptions | Hyperliquid Docs, 访问时间为 十月 15, 2025， [https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket/subscriptions](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket/subscriptions)  
5. Rate limits and user limits \- Hyperliquid Docs \- GitBook, 访问时间为 十月 15, 2025， [https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits)