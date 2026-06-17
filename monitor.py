"""
陀螺搶貨監控系統 — GitHub Actions 雲端版（一次性檢查）
每次執行只做「一輪」檢查就結束：
  1. Funbox 搜尋頁：跟上次記錄比對，有新商品就通知
  2. 誠品搜尋頁：掃描「加入購物車」商品，跟上次比對，有新增就通知
狀態存在 state.json，執行完會由 workflow 自動 commit 回 repo。
"""

import requests
import time
import os
import json
from datetime import datetime
from bs4 import BeautifulSoup

# ============================================================
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")

FUNBOX_URL = (
    "https://shop.funbox.com.tw/search"
    "?q=%E6%88%B0%E9%AC%A5%E9%99%80%E8%9E%BA"
    "&sort_by=sell_from-desc"
)

ESLITE_SEARCH_URL = "https://www.eslite.com/Search?keyword=beyblade+x&final_price=0,&publishDate=0&sort=_weight_+desc&size=20&display=list&start=0&exp=c"

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}
# ============================================================


def log(prefix, msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}][{prefix}] {msg}", flush=True)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {
        "funbox_known_ids": [],
        "funbox_initialized": False,
        "eslite_last_available_ids": [],
    }


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def send_discord(title, lines, link, color):
    if not DISCORD_WEBHOOK:
        log("Discord", "未設定 DISCORD_WEBHOOK，略過通知")
        return
    try:
        embed = {
            "title": title,
            "description": "\n".join(lines),
            "url": link,
            "color": color,
            "footer": {"text": "陀螺搶貨監控 · GitHub Actions"},
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        resp = requests.post(DISCORD_WEBHOOK, json={"embeds": [embed]}, timeout=10)
        if resp.status_code in (200, 204):
            log("Discord", "通知已送出")
        else:
            log("Discord", f"送出失敗 HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as exc:
        log("Discord", f"錯誤: {exc}")


# ─────────────────────────────────────────────────────────────
#  Funbox 檢查
# ─────────────────────────────────────────────────────────────

def fetch_funbox_products():
    try:
        resp = requests.get(FUNBOX_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
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


def check_funbox(state):
    products = fetch_funbox_products()
    if products is None:
        return

    known_ids = set(state.get("funbox_known_ids", []))
    current_ids = {p["id"] for p in products}

    if not state.get("funbox_initialized"):
        state["funbox_known_ids"] = list(current_ids)
        state["funbox_initialized"] = True
        log("Funbox", f"初始化：記錄 {len(current_ids)} 件既有商品")
        return

    new_ids = current_ids - known_ids
    if new_ids:
        new_p = [p for p in products if p["id"] in new_ids]
        title = f"🔔 Funbox 陀螺上架！共 {len(new_p)} 件新品"
        lines = [f"• [{p['name']}]({p['url']})" for p in new_p]
        log("Funbox", title)
        send_discord(title, lines, FUNBOX_URL, 0xE74C3C)
    else:
        log("Funbox", f"{len(products)} 件商品 — 無新上架")

    state["funbox_known_ids"] = list(current_ids)


# ─────────────────────────────────────────────────────────────
#  誠品檢查（搜尋頁模式）
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


def check_eslite(state):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("誠品", "未安裝 playwright，略過檢查")
        return

    last_ids = set(state.get("eslite_last_available_ids", []))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=HEADERS["User-Agent"],
        )
        page = ctx.new_page()
        try:
            available = _get_eslite_available(page)
        finally:
            browser.close()

    current_ids = {a["id"] for a in available}

    if not last_ids and not state.get("eslite_initialized"):
        # 第一次執行：記錄現況，不通知
        state["eslite_last_available_ids"] = list(current_ids)
        state["eslite_initialized"] = True
        if available:
            log("誠品", f"初始化：{len(available)} 件可購買商品（已記錄）")
            for a in available:
                log("誠品", f"  • {a['name']}")
        else:
            log("誠品", "初始化：目前無可購買商品")
        return

    new_ids = current_ids - last_ids
    if new_ids:
        new_items = [a for a in available if a["id"] in new_ids]
        title = f"🚨 誠品可以買了！共 {len(new_items)} 件"
        lines = [f"• [{a['name']}]({a['url']})" for a in new_items]
        log("誠品", title)
        send_discord(title, lines, ESLITE_SEARCH_URL, 0x2ECC71)
    elif available:
        log("誠品", f"{len(available)} 件可購買（已通知過，無新增）")
    else:
        log("誠品", "目前無可購買商品")

    state["eslite_last_available_ids"] = list(current_ids)


# ─────────────────────────────────────────────────────────────
#  主程式
# ─────────────────────────────────────────────────────────────

def main():
    log("System", "=== 開始本輪檢查 ===")
    state = load_state()

    check_funbox(state)
    check_eslite(state)

    save_state(state)
    log("System", "=== 本輪檢查結束 ===")


if __name__ == "__main__":
    main()
