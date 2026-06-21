# 雪球数据抓取工具

通过 CDP (Chrome DevTools Protocol) 从雪球网页抓取资金数据，解决 API 数据源不稳定的问题。

## 方案说明

使用 **手动登录 + Cookies 复用** 方案：
1. 本地打开浏览器，手动完成登录和滑块验证
2. 保存登录状态（Cookies）到本地
3. 上传到服务器，自动使用 Cookies 抓取数据
4. 定时任务自动执行，Cookies 过期时提醒重新登录

## 使用步骤

### 步骤1：本地登录雪球

```bash
# 安装依赖（如果还没安装）
pip install playwright
playwright install chromium

# 运行登录脚本
python3 step1_login_xueqiu.py
```

**操作说明**：
1. 脚本会打开一个浏览器窗口
2. 在浏览器中输入手机号和密码
3. 完成滑块验证
4. 点击登录
5. 登录成功后，回到终端按 Enter 继续

**输出文件**：
- `xueqiu_data/cookies.json` - 登录凭证
- `xueqiu_data/account_data.json` - 账户数据

### 步骤2：上传到服务器

```bash
python3 step2_upload_to_server.py
```

**说明**：
- 自动上传 Cookies 和账户数据到服务器
- 安装服务器端依赖
- 创建服务器端抓取脚本

### 步骤3：设置定时任务

```bash
python3 step3_setup_cron.py
```

**说明**：
- 设置每6小时自动抓取数据
- 每天检查 Cookies 是否过期
- 过期前会提醒重新登录

## 文件结构

```
scripts/
├── step1_login_xueqiu.py      # 步骤1：本地登录
├── step2_upload_to_server.py  # 步骤2：上传数据
├── step3_setup_cron.py        # 步骤3：设置定时任务
├── README.md                  # 本文档
└── xueqiu_data/               # 本地数据目录
    ├── cookies.json           # 登录凭证
    ├── account_data.json      # 账户数据
    └── check_cookies.py       # 检查脚本（自动生成）
```

## 服务器端文件

```
/root/stock_data/
├── cookies.json               # 登录凭证
├── account_data.json          # 账户数据
├── fetch_xueqiu.py            # 抓取脚本
├── check_cookies.py           # 检查脚本
├── latest_data.json           # 最新抓取数据
├── fetch.log                  # 抓取日志
└── check.log                  # 检查日志
```

## 常见问题

### Q: Cookies 多久过期？
A: 雪球的 Cookies 通常有效期为 30 天。脚本会在过期前 5 天提醒。

### Q: 如何重新登录？
A: 重新运行 `step1_login_xueqiu.py`，完成登录后运行 `step2_upload_to_server.py` 更新服务器数据。

### Q: 服务器上的数据如何使用？
A: 服务器上的 `/root/stock_data/latest_data.json` 包含最新的账户数据，可以被其他系统读取。

### Q: 如何手动触发抓取？
A: 登录服务器后运行：
```bash
cd /root/stock_data
python3 fetch_xueqiu.py
```

### Q: 如何查看日志？
A: 
```bash
# 查看抓取日志
cat /root/stock_data/fetch.log

# 查看检查日志
cat /root/stock_data/check.log
```

## 注意事项

1. **安全性**：Cookies 文件包含登录凭证，请妥善保管
2. **有效期**：定期检查 Cookies 是否过期
3. **频率**：不要过于频繁抓取，避免被封 IP
4. **合规**：仅用于个人数据获取，请遵守雪球使用条款

## 故障排除

### 登录失败
- 确认网络连接正常
- 检查账号密码是否正确
- 尝试手动在浏览器登录

### 上传失败
- 检查 SSH 密码是否正确
- 确认服务器 IP 可访问
- 检查磁盘空间

### 抓取失败
- 查看服务器日志：`cat /root/stock_data/fetch.log`
- 检查 Cookies 是否过期
- 手动登录更新 Cookies
