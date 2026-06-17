#!/usr/bin/env bash
# 在 VPS 上執行：bash deploy/setup_vps.sh
# 前提：已經把這個 repo clone 到 VPS 上，且目前在 repo 根目錄
set -e

echo "=== [1/5] 安裝系統套件 ==="
sudo apt update
sudo apt install -y python3-pip python3-venv git

echo "=== [2/5] 建立 Python 虛擬環境 ==="
python3 -m venv .venv
source .venv/bin/activate

echo "=== [3/5] 安裝 Python 套件 + Playwright Chromium ==="
pip install --upgrade pip
pip install -r requirements.txt
playwright install --with-deps chromium

echo "=== [4/5] 設定 Discord Webhook 環境變數檔 ==="
sudo mkdir -p /etc/beyblade-monitor
if [ ! -f /etc/beyblade-monitor/discord.env ]; then
  echo "DISCORD_WEBHOOK=請填入你的webhook網址" | sudo tee /etc/beyblade-monitor/discord.env > /dev/null
  echo ""
  echo "⚠️  尚未設定 Webhook，請執行以下指令編輯後再啟動服務："
  echo "    sudo nano /etc/beyblade-monitor/discord.env"
  echo ""
else
  echo "/etc/beyblade-monitor/discord.env 已存在，略過建立"
fi

echo "=== [5/5] 設定 systemd 服務 ==="
sudo cp deploy/beyblade-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload

echo ""
echo "================================================"
echo " 設定完成！接下來請依序執行："
echo ""
echo " 1) 編輯 webhook（如果上面顯示尚未設定）："
echo "    sudo nano /etc/beyblade-monitor/discord.env"
echo ""
echo " 2) 啟動服務並設成開機自動啟動："
echo "    sudo systemctl enable --now beyblade-monitor"
echo ""
echo " 3) 查看執行狀態："
echo "    sudo systemctl status beyblade-monitor"
echo ""
echo " 4) 查看即時 log（Ctrl+C 離開不會停止服務）："
echo "    sudo journalctl -u beyblade-monitor -f"
echo ""
echo " 5) 之後想重啟服務（例如改完商品清單）："
echo "    sudo systemctl restart beyblade-monitor"
echo "================================================"
