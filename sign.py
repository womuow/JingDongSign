"""
京东自动签到脚本(Linux / Windows 通用)

使用 Selenium 4.49 + Python 3.11,加载本地 Edge 用户数据目录(edge-debug-profile),
复用已保存的京东登录会话实现【自动登录】,然后自动点击签到并读取获得的京豆个数。

=== 使用方式 ===
1. 安装依赖:
    pip install selenium==4.49.0

2. 首次准备登录会话(只需一次):
    用本脚本使用的同一个 user-data-dir 启动 Edge,手动登录京东,然后关闭 Edge。
    - Linux(有桌面环境):
        microsoft-edge --user-data-dir="$PWD/edge-debug-profile"
      无显示器的服务器:先在有桌面的机器上完成登录,再把整个 edge-debug-profile
      目录原样拷贝到服务器上本脚本同级目录即可(Edge 关闭后再拷贝)。
    - Windows:
        "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --user-data-dir="C:\Project\JingDongSign\edge-debug-profile"
    登录后关闭 Edge,登录会话(cookie)会保存到该 profile 中。

3. 日常运行(全自动):
    python3 sign.py        # 使用 edge-debug-profile
    python3 sign.py 2      # 使用 edge-debug-profile2
    脚本会用该 profile 启动 Edge(自动登录)-> 签到 -> 读取京豆个数 -> 关闭浏览器。

    Linux 定时任务示例(crontab -e,每天 08:05 签到):
        5 8 * * * cd /path/to/JingDongSign && /usr/bin/python3 sign.py >> sign.log 2>&1

注意:
- 运行脚本时,不能有其他 Edge 实例正在使用同一个 user-data-dir,否则启动会失败。
- 京东登录会话过期后需要重做第 2 步。
- 默认 HEADLESS=True 后台(无头)运行,不弹出浏览器窗口;调试时可改为 False 观察页面。
- Linux 下 Edge 不在标准路径时,可用环境变量指定浏览器位置:
    JD_EDGE_BINARY=/opt/microsoft/msedge/msedge python3 sign.py
"""

import os
import shutil
import sys
import time
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from SendMail import send_mail


theme = "JingDong签到"
Tomail = "womuow@139.com"  


# ===== 配置 =====
# 脚本所在目录(跨平台:不再硬编码 Windows 路径,Windows/Linux 均以脚本位置为基准)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

IS_WINDOWS = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")

# Edge 用户数据目录(含已保存的京东登录会话)
USER_DATA_DIR = os.path.join(BASE_DIR, "edge-debug-profile")
USER_DATA_DIR_PATH = ""
PROFILE_DIR = "Default"

# 京东京豆签到页 / 登录页标识
BEAN_SIGN_URL = "https://bean.jd.com/myJingBean/list"
PASSPORT_HOST = "passport.jd.com"

# "签到领京豆" 按钮 XPath
SIGN_BTN_XPATH = '//*[@id="bean-sign-component"]/div[3]/img'

# 签到成功弹窗 XPath
#   <div class="title">签到成功，恭喜获得京豆</div>
#   <div class="num">2</div>
SUCCESS_TITLE_XPATH = '//div[contains(@class,"title") and contains(text(),"签到成功")]'
# 京豆个数:取"签到成功"标题之后的兄弟 num 节点(作用域更精确,避免误匹配)
SUCCESS_NUM_XPATH = '//div[contains(@class,"title") and contains(text(),"签到成功")]/following-sibling::div[contains(@class,"num")]'
# 兜底:结构变化时用全局 num 节点
SUCCESS_NUM_FALLBACK_XPATH = '//div[@class="num"]'

# 签到结束后是否自动关闭浏览器(True=自动关闭,便于定时任务;False=保留,便于查看)
AUTO_CLOSE = True

# 是否后台(无头)运行 Edge(True=不弹出浏览器窗口,适合定时任务;False=弹出窗口,便于调试)
HEADLESS = True


def find_edge_binary() -> str:
    """定位 Edge 可执行文件。

    - 优先读取环境变量 JD_EDGE_BINARY(强制指定);
    - Windows:返回空串,使用系统默认 Edge(Selenium Manager 自动处理);
    - Linux:按常见安装路径依次探测;均未命中时返回空串,交由 Selenium
      Manager 报出更明确的错误。
    """
    env_bin = os.environ.get("JD_EDGE_BINARY", "")
    if env_bin:
        return env_bin
    if not IS_LINUX:
        return ""
    candidates = [
        "/usr/bin/microsoft-edge",
        "/usr/bin/microsoft-edge-stable",
        "/usr/bin/microsoft-edge-beta",
        "/opt/microsoft/msedge/msedge",
        shutil.which("microsoft-edge") or "",
        shutil.which("microsoft-edge-stable") or "",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return ""


def launch_edge(profile: int = 0) -> webdriver.Edge:
    """用本地 user-data-dir 启动 Edge,复用已保存的登录会话(自动登录)。"""
    global USER_DATA_DIR_PATH
    if profile != 0:
        USER_DATA_DIR_PATH = USER_DATA_DIR+f"{profile}"
    else:
        USER_DATA_DIR_PATH =USER_DATA_DIR
    if not os.path.isdir(USER_DATA_DIR_PATH):
        raise FileNotFoundError(f"Edge 用户数据目录不存在: {USER_DATA_DIR_PATH}")

    options = Options()
    binary = find_edge_binary()
    if binary:
        options.binary_location = binary
    options.add_argument(f"--user-data-dir={USER_DATA_DIR_PATH}")
    options.add_argument(f"--profile-directory={PROFILE_DIR}")
    # 抑制首次启动向导
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    # 降低自动化检测
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    # 后台(无头)运行,不弹出浏览器窗口
    if HEADLESS:
        # 新版无头模式(Edge 112+),渲染行为与有头浏览器基本一致
        options.add_argument("--headless=new")
        # 无头模式默认窗口只有 800x600,显式指定尺寸,避免页面元素因视口过小而不可见/无法点击
        options.add_argument("--window-size=1920,1080")
    if IS_LINUX:
        # Linux 服务器(尤其 Docker / root 用户)下常见的兼容参数
        options.add_argument("--no-sandbox")
        # 容器内 /dev/shm 往往过小,改用 /tmp 存放共享内存,避免标签页崩溃
        options.add_argument("--disable-dev-shm-usage")
        # 服务器通常无 GPU,禁用以避免告警与初始化失败
        options.add_argument("--disable-gpu")

    return webdriver.Edge(options=options)


def ensure_login(driver: webdriver.Edge, settle: float = 2.0) -> bool:
    """
    打开京豆签到页,判断是否已登录。
    未登录时京东会重定向到 passport.jd.com;同时用 driver.get_cookies() 二次确认。
    """
    driver.get(BEAN_SIGN_URL)
    time.sleep(settle)  # 给重定向一点时间

    if PASSPORT_HOST in driver.current_url:
        return False  # 被重定向到登录页 => 未登录

    # 通过浏览器自身 API(Selenium get_cookies)确认存在 jd.com 会话 cookie
    jd_cookies = [c for c in driver.get_cookies() if "jd.com" in c.get("domain", "")]
    return len(jd_cookies) > 0


def click_sign_in_button(driver: webdriver.Edge, timeout: int = 15) -> bool:
    """
    点击"签到领京豆"按钮。

    1. 若当前不在京豆签到页,先跳转过去;
    2. 等待按钮元素出现并可点击;
    3. 点击按钮。

    返回 True 表示点击成功,False 表示失败。
    """
    if "bean.jd.com" not in driver.current_url:
        print(f"[信息] 跳转到京豆签到页 {BEAN_SIGN_URL}")
        driver.get(BEAN_SIGN_URL)

    try:
        # 等待"签到领京豆"按钮出现并可点击
        print(f"[信息] 等待签到按钮出现 (XPath: {SIGN_BTN_XPATH}) ...")
        button = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, SIGN_BTN_XPATH))
        )
        # 滚动到按钮可见区域,避免被遮挡导致点击失败
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)

        # 优先用 JS 点击,绕过"元素被遮挡 / 不可见"等常见拦截
        driver.execute_script("arguments[0].click();", button)
        print("[成功] 已点击签到领京豆按钮")
        return True
    except Exception as e:
        print(f"[失败] 点击签到按钮失败: {e}")
        # 回退:尝试 Selenium 原生 click()
        try:
            driver.find_element(By.XPATH, SIGN_BTN_XPATH).click()
            print("[成功] 已通过原生 click() 点击签到领京豆按钮")
            return True
        except Exception as e2:
            print(f"[失败] 原生 click() 也失败: {e2}")
            return False


def read_sign_in_result(driver: webdriver.Edge, timeout: int = 15) -> dict:
    """
    读取签到结果弹窗,返回签到是否成功及获得的京豆个数。

    弹窗结构:
        <div class="title">签到成功，恭喜获得京豆</div>
        <div class="num">2</div>

    返回 dict: {"success": bool, "title": str|None, "beans": str|None}
    """
    print("[信息] 等待签到结果弹窗 ...")
    try:
        # 等待"签到成功"标题可见(弹窗已弹出)
        title_el = WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((By.XPATH, SUCCESS_TITLE_XPATH))
        )
    except Exception:
        # 未出现"签到成功":可能今日已签到,或弹窗在 iframe 内、结构有变
        print("[警告] 未检测到「签到成功」弹窗(可能今日已签到,或弹窗在 iframe 中)。")
        return {"success": False, "title": None, "beans": None}

    title_text = title_el.text.strip()
    print(f"[成功] {title_text}")

    # 读取获得的京豆个数
    num_text = None
    for xpath in (SUCCESS_NUM_XPATH, SUCCESS_NUM_FALLBACK_XPATH):
        try:
            num_el = driver.find_element(By.XPATH, xpath)
            num_text = num_el.text.strip()
            if num_text:
                break
        except Exception:
            continue

    if num_text is not None:
        print(f"[结果] 本次签到获得京豆: {num_text} 个")
    else:
        print("[警告] 已检测到成功提示,但未能读取京豆个数。")

    return {"success": True, "title": title_text, "beans": num_text}


def main(profile: int = 0) -> int:
    try:
        print("[信息] 启动 Edge(加载本地 profile)...")
        driver = launch_edge(profile)
    except Exception as e:
        print(f"[错误] 启动 Edge 失败: {e}")
        print("请确认没有其他 Edge 实例正在使用该 user-data-dir:")
        print(f"  {USER_DATA_DIR_PATH}")
        return 1

    try:
        # 1. 自动登录检查
        print("\n=== 检查登录状态 ===")
        if not ensure_login(driver):
            print("[失败] 未登录或京东会话已过期。")
            print("请用同一 profile 手动登录一次京东,然后关闭 Edge 再运行本脚本:")
            if IS_WINDOWS:
                print(f'  msedge.exe --user-data-dir="{USER_DATA_DIR_PATH}"')
            else:
                print(f'  microsoft-edge --user-data-dir="{USER_DATA_DIR_PATH}"')
            return 1
        print(f"[成功] 已自动登录(当前页: {driver.current_url})")

        # 2. 签到
        print("\n=== 开始签到 ===")
        if not click_sign_in_button(driver):
            return 1

        # 3. 读取结果
        result = read_sign_in_result(driver)
        print("\n=== 签到结果 ===")
        print(f"成功  : {'是' if result.get('success') else '否'}")
        print(f"提示  : {result.get('title') or '无'}")
        beans = result.get("beans")
        print(f"京豆  : {beans if beans is not None else '未知'}")

        if beans is not None:
            send_mail(theme, f"本次签到获得京豆: {beans} 个","",Tomail)
        else:
            send_mail(theme, "本次签到失败","",Tomail)
        

        # 留 2 秒便于肉眼确认
        time.sleep(2)
        return 0
    finally:
        if AUTO_CLOSE:
            driver.quit()
            print("[信息] 已关闭浏览器。")


if __name__ == "__main__":
    # 依次为两个 profile 签到(目录 edge-debug-profile / edge-debug-profile2)
    rc1 = main()
    rc2 = main(2)
    # 任一 profile 失败则以非 0 退出,便于 cron / systemd 感知失败
    sys.exit(rc1 or rc2)
