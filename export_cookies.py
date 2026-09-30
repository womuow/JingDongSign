"""
京东 cookie 导出助手( Selenium 桥接 )

为什么需要这个文件:
  httpx 无法直接读取 Edge 加密的 cookie 数据库;直接读 SQLite 也不合规。
  Selenium 官方提供的 driver.get_cookies() 是读取浏览器会话 cookie 的合规方式。
  所以用本脚本:用本地 profile 启动 Edge -> 读取 jd.com 域 cookie -> 写入 cookies.json。
  本脚本【不点击签到】,不会消耗当日签到次数。

用法:
  python export_cookies.py
  产物: cookies.json(供 sign_httpx.py 使用)

注意:运行时不能有其他 Edge 实例正在使用同一个 user-data-dir。
"""

import json
import os
import sys
import time
from selenium import webdriver
from selenium.webdriver.edge.options import Options

USER_DATA_DIR = r"C:\Project\JingDongSign\edge-debug-profile"
PROFILE_DIR = "Default"
COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.json")

# 访问京东首页,确保会话 cookie 被加载到浏览器上下文
WARMUP_URL = "https://www.jd.com"


def launch_edge() -> webdriver.Edge:
    options = Options()
    options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    options.add_argument(f"--profile-directory={PROFILE_DIR}")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    return webdriver.Edge(options=options)


def main() -> int:
    if not os.path.isdir(USER_DATA_DIR):
        print(f"[错误] Edge 用户数据目录不存在: {USER_DATA_DIR}")
        return 1

    try:
        print("[信息] 启动 Edge 加载 profile ...")
        driver = launch_edge()
    except Exception as e:
        print(f"[错误] 启动 Edge 失败: {e}")
        print("请确认没有其他 Edge 实例正在使用该 user-data-dir。")
        return 1

    try:
        driver.get(WARMUP_URL)
        time.sleep(2)  # 等待 cookie 落地

        # 合规方式:通过浏览器自身 API 读取 cookie
        all_cookies = driver.get_cookies()
        jd_cookies = [c for c in all_cookies if "jd.com" in c.get("domain", "")]

        # 过滤出签到鉴权最关键的 cookie,便于核对
        key_names = {"pt_key", "pt_pin", "pwdt_id", "sfstoken", "thor", "pin", "unick"}
        key_cookies = [c for c in jd_cookies if c.get("name") in key_names]

        print(f"[信息] 共读取 jd.com cookie {len(jd_cookies)} 个")
        print("[信息] 关键鉴权 cookie:")
        for c in key_cookies:
            # 只打印名称和长度,不打印值,避免泄露
            print(f"  - {c['name']:<10} (domain={c.get('domain')}, val_len={len(c.get('value', ''))})")

        missing = key_names - {c["name"] for c in key_cookies}
        if missing:
            print(f"[警告] 缺少常见关键 cookie: {sorted(missing)}(可能未登录或会话已过期)")

        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump(jd_cookies, f, ensure_ascii=False, indent=2)
        print(f"[成功] 已写入 {COOKIES_FILE}")

        return 0 if key_cookies else 2
    finally:
        driver.quit()


if __name__ == "__main__":
    sys.exit(main())
