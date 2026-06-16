#!/bin/bash
# 设置 Mac 定时唤醒 - 周一到周五 9:20 和 14:25
# 比服务器任务（9:25/14:30）早 5 分钟，确保数据先抓取完成

echo "📊 设置股票定时任务唤醒..."

# 获取当前小时和分钟
HOUR=$(date +%H)
MIN=$(date +%M)

# 根据当前时间设置下次唤醒
if [ "$HOUR" -lt 9 ] || ([ "$HOUR" -eq 9 ] && [ "$MIN" -lt 20 ]); then
    # 现在是 9:20 之前，设置 9:20 唤醒
    sudo pmset repeat wakeorpoweron MTWRFSU 09:20:00
    echo "✅ 已设置 9:20 唤醒（服务器任务 9:25 执行）"
elif [ "$HOUR" -lt 14 ] || ([ "$HOUR" -eq 14 ] && [ "$MIN" -lt 25 ]); then
    # 现在是 14:25 之前，设置 14:25 唤醒
    sudo pmset repeat wakeorpoweron MTWRFSU 14:25:00
    echo "✅ 已设置 14:25 唤醒（服务器任务 14:30 执行）"
else
    # 现在是 14:25 之后，设置明天 9:20 唤醒
    sudo pmset repeat wakeorpoweron MTWRFSU 09:20:00
    echo "✅ 已设置明天 9:20 唤醒"
fi

# 显示当前计划
echo ""
echo "📋 当前唤醒计划:"
pmset -g sched | grep wake

# 添加 crontab 任务：在每次唤醒后重新设置下次唤醒
CRON_JOB="0 9,14 * * 1-5 /Users/fyq/Desktop/workshop/stock-system/stock/scripts/setup_wake.sh"
(crontab -l 2>/dev/null | grep -v "setup_wake"; echo "$CRON_JOB") | crontab -
echo ""
echo "✅ 已添加 crontab 任务，每次运行后自动设置下次唤醒"
