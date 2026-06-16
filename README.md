# 陀螺搶貨監控 — 雲端版（GitHub Actions）

不需要自己的電腦開機，GitHub 會每 10 分鐘自動跑一次檢查：
- **Funbox**：有新陀螺上架就通知
- **誠品**：清單裡的商品補貨就通知（通知後從待監控清單移除）

通知會送到 Discord。

---

## 設定步驟（只要做一次）

### 1. 建立 GitHub Repository
1. 到 [github.com/new](https://github.com/new) 建一個新的 repository（Public 或 Private 都可以，Private 也有每月免費額度）
2. 名稱隨意，例如 `beyblade-monitor`

### 2. 把這個資料夾上傳上去
在這個資料夾（`beyblade-monitor-cloud`）裡開終端機，依序執行：

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<你的帳號>/<repo名稱>.git
git push -u origin main
```

### 3. 設定 Discord Webhook（重要！不要把網址寫進程式碼裡）
1. 進入剛建立的 repo 頁面
2. 上方選單 → **Settings** → 左側 **Secrets and variables** → **Actions**
3. 點 **New repository secret**
   - Name: `DISCORD_WEBHOOK`
   - Secret: 貼上你的 Discord Webhook URL
4. 點 **Add secret**

### 4. 確認排程已啟動
1. 進入 repo 頁面 → 上方 **Actions** 分頁
2. 應該會看到 `Beyblade Monitor` 這個 workflow
3. 如果想立刻測試一次：點進 workflow → 右上角 **Run workflow** → **Run workflow**（綠色按鈕）
4. 等個 1~2 分鐘，檢查 Discord 頻道有沒有收到測試訊息（如果剛好有新品/補貨才會收到通知；沒收到代表「目前沒有新東西」，是正常的）

---

## 運作細節

- 預設每 **10 分鐘**檢查一次（GitHub 的排程是「最佳努力」，實際間隔可能略晚，正常現象）
- 想改檢查頻率：編輯 `.github/workflows/monitor.yml` 裡的 `cron: "*/10 * * * *"`
  - 最快只能設到 5 分鐘一次（GitHub 限制）：`*/5 * * * *`
- 狀態（哪些商品已通知過）存在 `state.json`，程式執行完會自動 commit 回 repo，不需要手動處理
- 誠品商品補貨通知後會自動從待監控清單移除；如果之後又缺貨想繼續監控，要手動把該商品網址加回 `state.json` 的 `eslite_pending_urls`

---

## 之後想新增/修改監控商品

直接編輯 `monitor.py` 裡的 `ESLITE_ITEMS` 清單，加完後：

```bash
git add monitor.py
git commit -m "新增商品"
git push
```

新加的商品網址記得同時加進 `state.json` 的 `eslite_pending_urls`，否則要等下次程式判斷成「待監控」才會檢查（其實第一次執行如果該網址不在 state.json 裡會被忽略，所以一定要手動補上）。

---

## 免費額度夠用嗎？

GitHub Actions 免費帳號（含 Private repo）每月有 2000 分鐘額度。
這個監控每次跑約 1~3 分鐘，每 10 分鐘跑一次 = 每天約 144~432 分鐘，每月約 4,300~13,000 分鐘 — **可能會超過免費額度**，建議：
- 改用 **Public repo**（Public repo 的 GitHub Actions 完全免費，無限制）
- 或拉長檢查間隔（例如 15~20 分鐘一次）
