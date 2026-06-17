"""
陀螺搶貨監控系統 — VPS 常駐版（24 小時不間斷）
  • Funbox : 每 FUNBOX_INTERVAL 秒檢查搜尋頁，有新品上架就通知
  • 誠品   : 每 ESLITE_INTERVAL 秒掃描搜尋頁，出現「加入購物車」就通知（跟 Funbox 同邏輯）
兩個監控同時在背景 thread 執行，用 systemd 常駐，斷線/當機會自動重啟。

注意：DISCORD_WEBHOOK 從環境變數讀取，不要寫死在程式碼裡
      （這個 repo 是 Public，寫死等於把 webhook 公開給全世界）
"""

import requests
import time
import os
import threading
from datetime import datetime
from bs4 import BeautifulSoup

# ============================================================
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")

FUNBOX_URL = (
    "https://shop.funbox.com.tw/search"
    "?q=%E6%88%B0%E9%AC%A5%E9%99%80%E8%9E%BA"
    "&sort_by=sell_from-desc"
)
FUNBOX_INTERVAL = 20   # 每幾秒檢查一次（VPS 不怕被中斷，可以設快一點）

ESLITE_SEARCH_URL = "https://www.eslite.com/Search?keyword=beyblade+x&final_price=0,&publishDate=0&sort=_weight_+desc&size=20&display=list&start=0&exp=c"
ESLITE_INTERVAL   = 60  # 每幾秒掃一次（Playwright 開頁面較重，60 秒就夠快）
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

_print_lock = threading.Lock()


def log(prefix, msg):
    with _print_lock:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}][{prefix}] {msg}", flush=True)


def send_discord(title, lines, link, color):
    if not DISCORD_WEBHOOK:
        log("Discord", "未設定 DISCORD_WEBHOOK 環境變數，略過通知！")
        return
    try:
        embed = {
            "title": title,
            "description": "\n".join(lines),
            "url": link,
            "color": color,
            "footer": {"text": "陀螺搶貨監控 · VPS"},
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        resp = requests.post(DISCORD_WEBHOOK, json={"embeds": [embed]}, timeout=10)
        if resp.status_code in (200, 204):
            log("Discord", "通知已送出")
        else:
            log("Discord", f"送出失敗 HTTP {resp.status_code}")
    except Exception as exc:
        log("Discord", f"錯誤: {exc}")


def notify_all(title, lines, link, color):
    with _print_lock:
        print(f"\n{'★'*55}")
        print(f"  {title}")
        for l in lines:
            print(f"  {l}")
        print(f"{'★'*55}\n", flush=True)
    send_discord(title, lines, link, color)


# ─────────────────────────────────────────────────────────────
#  Funbox 監控
# ─────────────────────────────────────────────────────────────

def _fetch_funbox():
    try:
        resp = requests.get(FUNBOX_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        log("Funbox", "網路連線失敗")
        return None
    except requests.exceptions.Timeout:
        log("Funbox", "連線逾時")
        return None
    except Exception as exc:
        log("Funbox", f"抓取錯誤: {exc}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    products, seen = [], set()
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if "/products/" not in href:
            continue
        clean = href.split("?")[0].split("#")[0]
        pid = clean.rstrip("/").split("/")[-1]
        if not pid or pid in seen:
            continue
        name = tag.get_text(separator=" ", strip=True)
        if not name:
            continue
        seen.add(pid)
        full_url = ("https://shop.funbox.com.tw" + clean) if clean.startswith("/") else clean
        products.append({"id": pid, "name": name, "url": full_url})
    return products


def monitor_funbox():
    log("Funbox", f"啟動，每 {FUNBOX_INTERVAL} 秒檢查一次")
    known_ids: set = set()
    first_run = True

    while True:
        products = _fetch_funbox()

        if products is not None:
            current_ids = {p["id"] for p in products}

            if first_run:
                known_ids = current_ids
                if products:
                    log("Funbox", f"初始掃描：{len(products)} 件既有商品（已記錄，不重複通知）")
                else:
                    log("Funbox", "初始掃描：目前無商品，開始監控...")
                first_run = False
            else:
                new_ids = current_ids - known_ids
                if new_ids:
                    new_p = [p for p in products if p["id"] in new_ids]
                    title = f"🔔 Funbox 陀螺上架！共 {len(new_p)} 件新品"
                    lines = [f"• [{p['name']}]({p['url']})" for p in new_p]
                    notify_all(title, lines, FUNBOX_URL, 0xE74C3C)
                    known_ids = current_ids
                else:
                    status = f"{len(products)} 件商品" if products else "無商品"
                    log("Funbox", f"{status} — 無新上架")

        time.sleep(FUNBOX_INTERVAL)


# ─────────────────────────────────────────────────────────────
#  誠品監控（搜尋頁模式）
# ─────────────────────────────────────────────────────────────

def _get_eslite_available(page) -> list:
    """載入誠品搜尋頁，回傳目前顯示「加入購物車」的商品 [{id, name, url}]"""
    try:
        page.goto("https://www.eslite.com/", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1000)
        page.goto(ESLITE_SEARCH_URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
    except Exception as exc:
        log("誠品", f"頁面載入失敗: {exc}")
        return []

    soup = BeautifulSoup(page.content(), "html.parser")
    available, seen_ids = [], set()

    for cart_text in soup.find_all(string=lambda s: s and "加入購物車" in s):
        node = cart_text.parent
        for _ in range(10):
            if node is None:
                break
            link = node.find("a", href=lambda h: h and "/product/" in h)
            if link:
                href = link["href"].split("?")[0].rstrip("/")
                pid = href.split("/")[-1]
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    name = link.get_text(strip=True)
                    full_url = "https://www.eslite.com" + href if href.startswith("/") else href
                    available.append({"id": pid, "name": name, "url": full_url})
                break
            node = node.parent

    return available


def monitor_eslite():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("誠品", "未安裝 playwright，請執行: pip install playwright && playwright install --with-deps chromium")
        return

    log("誠品", f"啟動（搜尋頁模式），每 {ESLITE_INTERVAL} 秒檢查一次")
    last_available_ids: set = set()
    first_run = True

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=HEADERS["User-Agent"],
        )
        page = ctx.new_page()
        try:
            while True:
                available = _get_eslite_available(page)
                current_ids = {a["id"] for a in available}

                if first_run:
                    last_available_ids = current_ids
                    if available:
                        log("誠品", f"初始掃描：{len(available)} 件可購買商品（已記錄）")
                        for a in available:
                            log("誠品", f"  • {a['name']}")
                    else:
                        log("誠品", "初始掃描：目前無可購買商品，開始監控...")
                    first_run = False
                else:
                    new_ids = current_ids - last_available_ids
                    if new_ids:
                        new_items = [a for a in available if a["id"] in new_ids]
                        title = f"🚨 誠品可以買了！共 {len(new_items)} 件"
                        lines = [f"• [{a['name']}]({a['url']})" for a in new_items]
                        notify_all(title, lines, ESLITE_SEARCH_URL, 0x2ECC71)
                    elif available:
                        log("誠品", f"{len(available)} 件可購買（已通知過，無新增）")
                    else:
                        log("誠品", "目前無可購買商品")

                    last_available_ids = current_ids

                time.sleep(ESLITE_INTERVAL)
        finally:
            browser.close()


# ─────────────────────────────────────────────────────────────
#  主程式
# ─────────────────────────────────────────────────────────────

def main():
    log("System", "=" * 50)
    log("System", "陀螺搶貨監控系統 — VPS 常駐版啟動")
    log("System", f"Funbox 間隔: {FUNBOX_INTERVAL} 秒 | 誠品間隔: {ESLITE_INTERVAL} 秒（搜尋頁模式）")
    log("System", "=" * 50)

    if not DISCORD_WEBHOOK:
        log("System", "⚠️  警告: 環境變數 DISCORD_WEBHOOK 未設定，將不會發送任何通知！")

    t_funbox = threading.Thread(target=monitor_funbox, name="Funbox", daemon=True)
    t_eslite = threading.Thread(target=monitor_eslite, name="誠品",   daemon=True)

    t_funbox.start()
    t_eslite.start()

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
