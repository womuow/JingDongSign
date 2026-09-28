"""
京东自动签到 - httpx 直连版(基于浏览器会话 cookie)

数据来源与思路(已完成的分析):
  1. cookies.json 由 export_cookies.py 通过 Selenium driver.get_cookies() 导出
     (httpx 无法读取 Edge 加密 cookie 库,由浏览器导出是合规途径)。
  2. cookie 分析结论(profile 为 PC 网页登录):
     - 核心鉴权: thor (288 字节, httpOnly+secure) —— PC Web 端登录令牌
     - 辅助登录态: _pst, _tp
     - 设备指纹/风控: 3AB9D23F7A4B3C9B, 3AB9D23F7A4B3CSS, shshshfpa/b/x, sdtoken, flash
     - 统计类: __jda/b/c/u/v
     - 无 pt_key/pt_pin => 不是移动端 App 会话
  3. 因此签到请求应带完整 cookie(至少 thor + 设备指纹),并带上与浏览器一致的
     Referer / User-Agent。

⚠ 待确认项(见 TODO):
  - PC 端签到接口的 functionId 与 body 格式
  - 是否需要 h5st/_token 签名
  这两项需要用浏览器 F12 Network 抓一次真实签到请求来确认,
  或等本机可运行抓包脚本时自动完成。

用法:
  pip install httpx
  python export_cookies.py   # 先导出 cookie(登录会话过期后重跑)
  python sign_httpx.py
"""

import json
import os
import sys
import httpx

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.json")

BEAN_PAGE_URL = "https://bean.jd.com/myJingBean/list"

# 与真实浏览器一致的请求头
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0")


def load_cookie_header(path: str = COOKIES_FILE) -> str:
    """把 export_cookies.py 导出的 cookies.json 拼成 Cookie 请求头。"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"cookie 文件不存在: {path}\n请先运行 python export_cookies.py")
    with open(path, encoding="utf-8") as f:
        cookies = json.load(f)
    # 按浏览器原样拼接;thor 是核心鉴权,缺失则必然未登录
    names = [c.get("name") for c in cookies]
    if "thor" not in names:
        raise RuntimeError("cookie 中缺少 thor(PC 网页登录令牌),请重新登录并导出 cookie。")
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies)


def build_headers(cookie_header: str) -> dict:
    return {
        "User-Agent": UA,
        "Cookie": cookie_header,
        "Referer": BEAN_PAGE_URL,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Origin": "https://bean.jd.com",
        "X-Requested-With": "XMLHttpRequest",
    }


def check_login(client: httpx.Client) -> bool:
    """访问签到页,若被重定向到 passport.jd.com 则未登录/会话过期。"""
    resp = client.get(BEAN_PAGE_URL, follow_redirects=False)
    location = resp.headers.get("location", "")
    if resp.status_code in (301, 302, 303, 307) and "passport.jd.com" in location:
        return False
    return resp.status_code == 200 and "passport.jd.com" not in str(resp.url)


def do_sign(client: httpx.Client) -> dict:
    """
    执行签到并解析获得的京豆个数。

    TODO(待抓包确认后再实现):
      - 确认 PC 端真实接口:浏览器 F12 -> Network -> 点击"签到领京豆",
        记录请求 URL(functionId)、方法、body、响应 JSON。
      - 确认是否需要 h5st/_token 签名参数。
    以下为占位实现,避免误调用未知接口。
    """
    raise NotImplementedError(
        "签到接口待抓包确认:请在浏览器中 F12 打开 Network, "
        "访问 https://bean.jd.com/myJingBean/list 并点击签到按钮, "
        "把捕获到的请求(URL/functionId/body/响应JSON)提供给脚本完善。"
    )


def main() -> int:
    try:
        cookie_header = load_cookie_header()
    except Exception as e:
        print(f"[错误] {e}")
        return 1

    with httpx.Client(headers=build_headers(cookie_header), timeout=20,
                      http2=True, follow_redirects=True) as client:
        print("[信息] 检查登录状态 ...")
        if not check_login(client):
            print("[失败] 会话已过期或未登录,请重新运行 export_cookies.py 前先手动登录。")
            return 1
        print("[成功] 登录态有效(thor 鉴权)")

        print("[信息] 执行签到 ...")
        result = do_sign(client)
        print(f"[结果] {result}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
