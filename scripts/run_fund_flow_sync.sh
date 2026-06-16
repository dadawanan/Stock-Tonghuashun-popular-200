#!/bin/bash
# 资金流向同步定时任务

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/fund_flow_data"
LOG_FILE="$LOG_DIR/sync_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$LOG_DIR"

echo "$(date): 开始同步资金流向数据..." >> "$LOG_FILE"
cd "$SCRIPT_DIR/.."
python3 scripts/sync_fund_flow.py >> "$LOG_FILE" 2>&1
echo "$(date): 同步完成" >> "$LOG_FILE"

# 清理30天前的日志
find "$LOG_DIR" -name "*.log" -mtime +30 -delete 2>/dev/null
