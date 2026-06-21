#!/bin/bash
# 本地资金流向同步脚本
# 1. 本地抓取资金流向数据
# 2. 推送到服务器

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/fund_flow_data"
LOG_FILE="$LOG_DIR/sync_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$LOG_DIR"

echo "$(date): 开始同步资金流向数据..." >> "$LOG_FILE"

# 运行同步脚本
cd "$SCRIPT_DIR/.."
python3 scripts/sync_fund_flow.py >> "$LOG_FILE" 2>&1

# 上传到服务器
if [ -f "scripts/fund_flow_data/latest_data.json" ]; then
    echo "$(date): 上传数据到服务器..." >> "$LOG_FILE"
    sshpass -p "469833happy#" scp -o StrictHostKeyChecking=no \
        scripts/fund_flow_data/latest_data.json \
        root@101.35.255.200:/root/stock_data/fund_flow_data/ >> "$LOG_FILE" 2>&1
fi

echo "$(date): 同步完成" >> "$LOG_FILE"

# 清理30天前的日志
find "$LOG_DIR" -name "*.log" -mtime +30 -delete 2>/dev/null
