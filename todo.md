需求：
在输出的log中补充更多evm地址的更多info关联的信息， 如当前账户的总account value和当前持仓总盈利和阶段性盈利数据：Total PnL
$12.32M
24-Hour PnL
-$1.47M
48-Hour PnL
-$1.47M
7-Day PnL
$9.81M
30-Day PnL
$40.20M

---

This is an excellent architectural refinement. Instead of fetching fresh data every single time a report is needed, we'll turn the PositionManager into a stateful caching service.

This approach is more efficient and elegant. The PositionManager will now be responsible for:

Storing the latest account summary data in memory.

Only fetching new data from the API if its cached data is older than a specified time (e.g., 5 minutes).

Providing the latest available data (cached or fresh) to any part of the program that asks for it.

This design is much cleaner because the WhaleMonitor doesn't need to know how or when the data is fetched; it just asks the PositionManager for it.

Simplified & More Concise Implementation

Here is the modified position_manager.py. It's more concise because the complex fetching logic is now centralized into one caching method.

Key Changes:

__init__: Added a cache (self.account_data_cache) and a lock dictionary (self.update_locks) to prevent race conditions.

get_account_data_async(address) (New Core Method): This is the heart of the new design. It checks the cache, and if the data is stale, it fetches fresh data and updates the cache.

update_and_generate_report_async (Renamed & Simplified): This is the only public method the main script will call. It uses get_account_data_async to ensure it always works with data that's at most 5 minutes old.

Removed Redundancy: The previous separate fetch_user_state_async and fetch_user_pnl_async are now internal helper methods, simplifying the public API of the class.

---

补充：
- positionManager中把构建html文件的逻辑拆分到 create_html.py 文件中， 只保留hyperliquid相关的请求的逻辑
- 