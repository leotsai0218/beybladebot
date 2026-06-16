"""
陀螺搶貨監控系統 — GitHub Actions 雲端版（一次性檢查）
每次執行只做「一輪」檢查就結束：
  1. Funbox 搜尋頁：跟上次記錄比對，有新商品就通知
  2. 誠品清單：逐一檢查庫存，補貨就通知並從待監控清單移除
狀態（已知商品 / 待監控清單）存在 state.json，執行完會由 workflow 自動 commit 回 repo。
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

ESLITE_ITEMS = [
    {"name": "BX-29 X發射器改造型握把/ 白藍",       "url": "https://www.eslite.com/product/10042014802683132123007"},
    {"name": "CX-01 蒼龍勇氣",                       "url": "https://www.eslite.com/product/10042014802682961097008"},
    {"name": "BX-29 X發射器改造型握把/ 黑紅",       "url": "https://www.eslite.com/product/10042014802683132122000"},
    {"name": "BX-00 X旋風發射器/ 限定三色版",        "url": "https://www.eslite.com/product/10042014802683118314009"},
    {"name": "BX-04 騎士重盾",                       "url": "https://www.eslite.com/product/10042014802682851909008"},
    {"name": "BX-01 蒼龍神劍",                       "url": "https://www.eslite.com/product/10042014802682851924001"},
    {"name": "CX-14 騎士堡壘",                       "url": "https://www.eslite.com/product/10042014802683118312005"},
    {"name": "UX-05 忍者闇影",                       "url": "https://www.eslite.com/product/10042014802682851916006"},
    {"name": "BX-13 騎士長槍",                       "url": "https://www.eslite.com/product/10042014802682851912008"},
    {"name": "BX-29 X發射器改造型握把/ 藍+透明",    "url": "https://www.eslite.com/product/10042014802683132121003"},
    {"name": "CX-02 魔導至尊",                       "url": "https://www.eslite.com/product/10042014802683004331004"},
    {"name": "BXG-20 巨岩雄獅",                      "url": "https://www.eslite.com/product/10042014802683134638004"},
    {"name": "CX-12 鳳凰閃焰",                       "url": "https://www.eslite.com/product/10042014802683109723001"},
    {"name": "UX-14 天蠍長矛0-70Z",                  "url": "https://www.eslite.com/product/10042014802683132117006"},
    {"name": "BX-16 王蛇鞭尾",                       "url": "https://www.eslite.com/product/10042014802682851915009"},
    {"name": "CX-15 邪神狂怒",                       "url": "https://www.eslite.com/product/10042014802683118311008"},
    {"name": "UX-09 武士星劍",                       "url": "https://www.eslite.com/product/10042014802683109721007"},
    {"name": "BX-36 巨鯨怒濤",                       "url": "https://www.eslite.com/product/10042014802683004337006"},
    {"name": "CX-10 銀狼狩獵",                       "url": "https://www.eslite.com/product/10042014802683066241006"},
    {"name": "UX-08 霜輝銀狼",                       "url": "https://www.eslite.com/product/10042014802683066232004"},
    {"name": "UX-01 蒼龍爆刃",                       "url": "https://www.eslite.com/product/10042014802682851917003"},
    {"name": "BX-21 惡魔鎖鏈改造組",                "url": "https://www.eslite.com/product/10042014802682851914002"},
    {"name": "UX-18 Vol.8 隨機強化組",               "url": "https://www.eslite.com/product/10042014802683069573005"},
    {"name": "CX-08 隨機強化組 Vol.7",               "url": "https://www.eslite.com/product/10042014802682961082004"},
    {"name": "BX-20 蒼龍利刃改造組",                "url": "https://www.eslite.com/product/10042014802682851910004"},
    {"name": "BX-23 鳳凰飛翼 豪華組",               "url": "https://www.eslite.com/product/10042014802683004336009"},
    {"name": "UX-16 時鐘幻象 隨機強化組",            "url": "https://www.eslite.com/product/10042014802683031789007"},
    {"name": "BX-08 三合一對戰組",                   "url": "https://www.eslite.com/product/10042014802682851911001"},
    {"name": "UX-17 隕星龍騎士",                     "url": "https://www.eslite.com/product/10042014802683069571001"},
    {"name": "CX-05 隨機強化組 Vol. 6",              "url": "https://www.eslite.com/product/10042014802683004332001"},
    {"name": "CX-11 帝王威能",                       "url": "https://www.eslite.com/product/10042014802683066244007"},
    {"name": "BX-48 Vol. 09 隨機強化組",             "url": "https://www.eslite.com/product/10042014802683105252000"},
    {"name": "BX-09 通行證",                         "url": "https://www.eslite.com/product/10042014802683066233001"},
    {"name": "BX-44 三角強襲",                       "url": "https://www.eslite.com/product/10042014802683109722004"},
    {"name": "CX-16 極限衝擊對戰組/ C",              "url": "https://www.eslite.com/product/10042014802683118316003"},
    {"name": "UX-03 魔導神杖",                       "url": "https://www.eslite.com/product/10042014802682851922007"},
    {"name": "CX-17 隨機強化組 Vol. 10",             "url": "https://www.eslite.com/product/10042014802683132897007"},
    {"name": "CX-13 龍王閃擊",                       "url": "https://www.eslite.com/product/10042014802683118315006"},
    {"name": "UX-19 子彈獅鷲H",                      "url": "https://www.eslite.com/product/10042014802683135549002"},
    {"name": "BX-49 蒼龍突擊",                       "url": "https://www.eslite.com/product/10042014802683157348003"},
    {"name": "CX-18 腕龍鞭打 隨機強化組",            "url": "https://www.eslite.com/product/10042014802683165873009"},
    {"name": "CX-07 天馬爆擊",                       "url": "https://www.eslite.com/product/10042014802682961081007"},
    {"name": "CX-06 極狐九尾 隨機強化組",            "url": "https://www.eslite.com/product/10042014802683066235005"},
    {"name": "BX-45 武士魂斬",                       "url": "https://www.eslite.com/product/10042014802683157345002"},
    {"name": "CX-03 英仙幽冥",                       "url": "https://www.eslite.com/product/10042014802682961080000"},
    {"name": "BX-34 蒼穹龍騎士 豪華組",              "url": "https://www.eslite.com/product/10042014802683154581007"},
    {"name": "BXG-13 神力聖劍",                      "url": "https://www.eslite.com/product/10042014802683109724008"},
    {"name": "BXG-06 鮫鯊鋒鰭深海藍 限定版",         "url": "https://www.eslite.com/product/10042014802683066236002"},
]

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
        "eslite_pending_urls": [item["url"] for item in ESLITE_ITEMS],
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
        # 第一次執行：記錄現有商品，不通知
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
#  誠品檢查
# ─────────────────────────────────────────────────────────────

def _check_eslite_stock(page, item):
    try:
        page.goto(item["url"], wait_until="networkidle", timeout=30000)
        content = page.content()
        if ("加入購物車" in content or "立即購買" in content) and \
           "補貨中" not in content and "已售完" not in content:
            return True
        return False
    except Exception as exc:
        log("誠品", f"抓取出錯 {item['name']}: {exc}")
        return False


def check_eslite(state):
    pending_urls = set(state.get("eslite_pending_urls", [item["url"] for item in ESLITE_ITEMS]))
    items = [i for i in ESLITE_ITEMS if i["url"] in pending_urls]

    if not items:
        log("誠品", "清單已全部補貨並通知過，略過檢查")
        return

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("誠品", "未安裝 playwright，略過檢查")
        return

    log("誠品", f"開始檢查，共 {len(items)} 項待補貨商品")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=HEADERS["User-Agent"],
        )
        page = ctx.new_page()
        try:
            for item in items:
                if _check_eslite_stock(page, item):
                    title = f"🚨 誠品補貨：{item['name']}"
                    lines = [f"• [{item['name']}]({item['url']})"]
                    log("誠品", title)
                    send_discord(title, lines, item["url"], 0x2ECC71)
                    pending_urls.discard(item["url"])
                else:
                    log("誠品", f"無庫存: {item['name']}")
                time.sleep(1.5)
        finally:
            browser.close()

    state["eslite_pending_urls"] = list(pending_urls)


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
