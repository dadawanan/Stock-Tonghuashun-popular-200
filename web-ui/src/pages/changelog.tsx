import { Timeline, Typography } from "antd";

const { Title, Paragraph, Text } = Typography;

type LogEntry = {
  date: string;
  added: string[];
  fixed: string[];
};

/** 按时间倒序：最新的在上面 */
const CHANGELOG: LogEntry[] = [
  {
    date: "2026-05-24",
    added: [
      "量化交易模块全面上线：策略管理、回测系统、模拟盘、参数优化",
      "策略管理：4种内置策略（人气榜、情绪驱动、技术面、多因子），参数可配置",
      "回测系统：含交易成本、T+1规则、滑点，支持多策略批量对比",
      "回测图表：净值曲线、收益率曲线、回撤曲线，与沪深300基准对比",
      "模拟盘：市价单/限价单、T+1规则、止损止盈（固定+移动）、账户回撤限制",
      "模拟盘实时价格：持仓显示现价、市值、盈亏（数据源：新浪财经）",
      "挂单系统：限价单，交易时间内每60秒检查价格自动成交",
      "定时任务：9:25/14:30自动采集人气榜，15:05自动每日结算",
      "参数优化：网格搜索最优策略参数，支持夏普比率/收益率/胜率优化",
      "交易分析：胜率、盈亏比、平均持仓天数、最大连续亏损统计",
      "数据导出：持仓、交易记录、回测结果导出CSV",
      "闭环反馈：回测结果分析 → 策略权重调整建议",
      "沪市数据：新增50只上海股票日线数据和技术指标",
    ],
    fixed: [
      "修复Decimal类型在回测引擎中的类型转换问题",
      "修复模拟盘创建时策略选择功能",
      "修复策略管理页面缺少Select导入",
      "修复回测页面toFixed类型错误",
      "修复每日结算重复执行的主键冲突",
    ],
  },
  {
    date: "2026-05-07",
    added: [
      "首页「分析单只股票」：弹窗输入代码，调用 POST /api/analyze 并刷新列表",
      "导航「更新日志」模块，集中记录功能迭代与修复",
      "「新闻数量」列点击弹窗，接入 GET /api/news/{stock_code} 展示新闻明细",
      "POST /api/analyze 支持可选参数 stock_code，单股抓取与分析不影响原「新增股」流程",
    ],
    fixed: ["复制股票名称在非 Chrome 下失败：增加 execCommand 降级方案"],
  },
];

export default function ChangelogPage() {
  return (
    <div>
      <Title level={2}>更新日志</Title>
      <Paragraph type="secondary">
        记录各版本新增能力与问题修复，便于对照环境与排查。
      </Paragraph>

      <Timeline
        items={CHANGELOG.map((entry) => ({
          color: "blue",
          children: (
            <div style={{ paddingBottom: 16 }}>
              <Text strong style={{ fontSize: 16 }}>
                {entry.date}
              </Text>

              {entry.added.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <Text type="success">新增</Text>
                  <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
                    {entry.added.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                </div>
              )}

              {entry.fixed.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <Text type="warning">修复</Text>
                  <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
                    {entry.fixed.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ),
        }))}
      />
    </div>
  );
}
