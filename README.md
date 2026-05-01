# 人气股综合分析流水线

这个项目现在包含三段能力：

1. `get_popularity.py`
   用 `pywencai` 抓取同花顺人气前 200，并识别新进入榜单的股票。
2. `data_fetcher.py`
   自动生成真实的 `news_data.csv` 和 `market_data.csv`。
2. `main.py`
   对 `新增股票.csv` 做新闻事件分析、情绪分析、价量和资金行为分析，最后输出综合判断结果。

## 一、当前整体流程

你的目标可以拆成一条标准流水线：

1. 榜单层：每天抓取同花顺人气前 200，得到新增股票名单。
2. 文本层：给新增股票收集新闻、公告、互动易、研报摘要、社媒热帖。
3. 量化层：收集涨跌幅、量比、换手率、振幅、主力净流入、相对指数强弱。
4. 决策层：把文本和资金行为合并成一条综合判断。

当前代码已经把第 1 步和第 4 步的骨架串起来了。

## 二、如何运行

你现在有两种运行方式。

### 方式 A：自动抓真实数据再分析

```bash
python3 main.py --stocks 新增股票.csv --news news_data.csv --market market_data.csv --output analysis_result.csv --fetch-real-data
```

### 方式 B：只分析已有输入文件

先准备三份文件：

1. `新增股票.csv`
   你已经有这份文件，至少需要股票代码和股票简称。
2. `news_data.csv`
   每条新闻或公告一行。
3. `market_data.csv`
   每只股票一行，放量价和资金信号。

运行：

```bash
python3 main.py --stocks 新增股票.csv --news news_data.csv --market market_data.csv --output analysis_result.csv
```

输出文件：

```text
analysis_result.csv
```

## 三、输入格式

### 1. 新闻数据 `news_data.csv`

建议列名如下：

```csv
stock_code,title,content,published_at,source,url
688353.SH,公司公告中标某项目,公司披露获得储能项目订单...,2026-05-01 09:30:00,公告,https://example.com/a
603693.SH,高管被立案调查,公司实际控制人收到立案通知...,2026-05-01 12:00:00,新闻,https://example.com/b
```

当前版本会自动做这些事情：

- 事件识别与分类
- 细粒度情绪强弱判断
- 短期/长期标签
- 事实支撑强弱判断
- 多空逻辑提取

目前这部分先用规则引擎实现，后续可以直接替换成大模型接口。

### 2. 量化数据 `market_data.csv`

建议列名如下：

```csv
stock_code,pct_change,volume_ratio,turnover_rate,amplitude,main_net_inflow,relative_strength_vs_index
688353.SH,5.3,2.1,18.4,9.7,8200000,2.3
603693.SH,-4.1,1.8,23.6,11.2,-5600000,-1.4
```

字段解释：

- `pct_change`: 当日涨跌幅
- `volume_ratio`: 量比
- `turnover_rate`: 换手率
- `amplitude`: 振幅
- `main_net_inflow`: 主力净流入金额，可正可负
- `relative_strength_vs_index`: 相对大盘或板块的超额强度

## 四、当前真实取数实现说明

### 1. `news_data.csv`

这部分已经是自动抓取的真实数据，来源是东方财富个股新闻。

### 2. `market_data.csv`

这部分当前采用“稳定优先”的真实取数策略：

- `latest_price` 和 `pct_change`：直接使用你的人气榜新增股票文件里的实时数据
- `main_net_inflow` 和 `main_net_inflow_ratio`：通过东方财富资金流接口抓取真实数据
- `turnover_rate`、`amplitude`、`volume_ratio`、`relative_strength_vs_index`：
  这些字段对应的实时行情接口在你当前网络环境下不稳定，所以暂时可能为空

这意味着当前版本的量化判断，最依赖的是：

- 当日真实涨跌幅
- 主力净流入/净流出
- 文本事件分析

如果后面你本机网络对东方财富实时 quote 接口更稳定，我可以继续把 `market_data.csv` 的这些扩展字段补全。

## 五、当前输出内容

`analysis_result.csv` 会输出这些关键字段：

- `event_types`: 识别到的事件类型
- `text_event_label`: 文本整体偏利好/利空/中性
- `text_score`: 文本评分
- `sentiment_strength`: 情绪强弱
- `duration_tag`: 短期或长期
- `fact_support`: 事实支撑强弱
- `bullish_logic`: 看多逻辑
- `bearish_logic`: 看空逻辑
- `price_volume_signal`: 主动性上涨、被动性跟涨、高位巨量滞涨等
- `fund_flow_signal`: 主力净流入或净流出
- `behavior_label`: 做多主导、获利回吐、做空主导、空头回补
- `integrated_score`: 综合评分
- `decision`: 最终判断

## 六、你要怎么把它升级成真正可用的策略

### 1. 文本数据源扩展

建议至少接这几类数据：

- 公司公告
- 财报和业绩预告
- 新闻快讯
- 互动易问答
- 行业政策
- 社媒高热帖子

做法上不要把所有文本混在一起，建议保留 `source` 字段，后面可以给不同来源分配不同权重。

### 2. 把规则引擎替换成大模型

当前 `stock_analyzer.py` 里的 `analyze_text_event()` 是规则版占位实现。后面你可以把它替换成真正的 LLM 调用，返回结构化 JSON，比如：

```json
{
  "event_type": "major_order",
  "event_label": "利好",
  "event_score": 2.1,
  "sentiment_strength": "强",
  "duration_tag": "长期",
  "fact_support": "较强",
  "bullish_logic": "订单落地验证需求",
  "bearish_logic": "兑现周期长，短期利润释放有限"
}
```

推荐做法：

1. 一条新闻一次调用模型，输出结构化 JSON。
2. 对同一只股票多条新闻做聚合。
3. 将公告类文本权重调高，社媒类文本权重调低。

### 3. 量化层更进一步

你现在可以先用日频数据，后面升级为分钟级数据：

- 开盘后 30 分钟资金净流入强度
- 分时量价背离
- 大单成交占比
- 板块联动强度
- 龙虎榜/席位特征

这样才能更好区分：

- 真正主动做多
- 跟风拉升
- 利好兑现出货
- 恐慌杀跌后的空头回补

### 4. 综合决策最好做成分层输出

不要只给一个“买/不买”。建议拆成三层：

- 事实层：发生了什么事件
- 资金层：市场资金怎么反应
- 结论层：是强化、分歧、兑现还是反转

## 七、下一步最值得先做什么

如果你想尽快落地，建议按这个顺序推进：

1. 先固定 `news_data.csv` 和 `market_data.csv` 的字段标准。
2. 先跑通规则版综合分析，验证整条链路和输出表格是否顺手。
3. 再把 `analyze_text_event()` 替换成大模型接口。
4. 最后再补分钟级资金行为和更复杂的评分体系。

## 八、当前代码文件

- [main.py](/Users/fyq/Desktop/workshop/stock/main.py)
- [data_fetcher.py](/Users/fyq/Desktop/workshop/stock/data_fetcher.py)
- [stock_analyzer.py](/Users/fyq/Desktop/workshop/stock/stock_analyzer.py)
- [get_popularity.py](/Users/fyq/Desktop/workshop/stock/get_popularity.py)

如果你下一步想要，我可以继续直接帮你做两件事中的一种：

1. 接入真实大模型接口，把规则引擎改成模型分析。
2. 继续增强 `market_data.csv`，把换手率、振幅、量比、相对强弱也补成稳定的真实数据。
