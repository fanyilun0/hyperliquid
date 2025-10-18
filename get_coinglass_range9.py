#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 Coinglass 获取 Hyperliquid 活跃交易地址
访问页面: https://www.coinglass.com/zh/hl/range/9
将地址保存到 jsons/evm_address.json 文件
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import json
import time


def get_coinglass_addresses():
    """
    从 Coinglass 获取活跃交易地址列表
    """
    # 设置 Chrome 浏览器选项
    chrome_options = Options()
    # chrome_options.add_argument("--headless")  # 无头模式，不打开浏览器窗口（可选）
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    # 设置用户代理，模拟真实浏览器
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # 初始化 WebDriver
    print("正在初始化浏览器...")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # 访问目标网页
        url = "https://www.coinglass.com/zh/hl/range/9"
        print(f"正在访问: {url}")
        driver.get(url)

        # 等待页面加载完成
        print("等待页面加载...")
        time.sleep(8)  # 等待页面完全加载，包括 JavaScript 渲染的内容

        # 尝试滚动页面以加载更多内容
        print("滚动页面以加载更多内容...")
        for i in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

        # 等待表格元素加载
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//table//tr/td//a[contains(@href, '/zh/hyperliquid/0x')]"))
            )
        except Exception as e:
            print(f"等待表格加载超时: {e}")

        # 查找包含地址的链接元素
        # 地址链接格式: <a target="_blank" href="/zh/hyperliquid/0x5b5d51203a0f9079f8aeb098a6523a13f298c060">
        print("正在提取地址...")
        address_elements = driver.find_elements(By.XPATH, "//table//tr/td//a[contains(@href, '/zh/hyperliquid/0x')]")

        # 提取完整的 EVM 地址
        addresses = []
        seen_addresses = set()  # 用于去重
        
        for element in address_elements:
            href = element.get_attribute("href")
            if href:
                # 从 href 中提取完整地址
                # 格式: /zh/hyperliquid/0x5b5d51203a0f9079f8aeb098a6523a13f298c060
                parts = href.split("/")
                if len(parts) > 0:
                    address = parts[-1]
                    # 验证是否为有效的 EVM 地址 (0x + 40个十六进制字符)
                    if address.startswith("0x") and len(address) == 42:
                        if address.lower() not in seen_addresses:
                            addresses.append(address.lower())
                            seen_addresses.add(address.lower())

        print(f"成功提取 {len(addresses)} 个唯一地址")

        # 显示前几个地址作为预览
        if addresses:
            print("\n前 5 个地址预览:")
            for i, addr in enumerate(addresses[:5], 1):
                print(f"  {i}. {addr}")

        # 将地址列表保存为 JSON 文件
        output_file = "jsons/evm_address.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(addresses, f, ensure_ascii=False, indent=2)

        print(f"\n✓ 地址列表已保存到 {output_file} 文件中")
        
        return addresses

    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()
        return []

    finally:
        # 关闭浏览器
        print("\n正在关闭浏览器...")
        driver.quit()


if __name__ == "__main__":
    print("=" * 60)
    print("Coinglass 活跃交易地址获取工具")
    print("=" * 60)
    
    addresses = get_coinglass_addresses()
    
    if addresses:
        print(f"\n任务完成! 共获取 {len(addresses)} 个活跃交易地址")
    else:
        print("\n未能获取到地址，请检查网络连接或页面结构是否发生变化")

