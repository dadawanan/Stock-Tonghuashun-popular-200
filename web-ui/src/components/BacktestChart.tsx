import { useEffect, useState } from "react";
import { Card, Row, Col, Spin } from "antd";
import { Line, DualAxes } from "@ant-design/charts";
import { quantApi, BacktestNav } from "../utils";

interface BacktestChartProps {
  backtestId: number;
}

export default function BacktestChart({ backtestId }: BacktestChartProps) {
  const [navData, setNavData] = useState<BacktestNav[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadData();
  }, [backtestId]);

  const loadData = async () => {
    setLoading(true);
    try {
      const data = await quantApi.getBacktestNav(backtestId);
      setNavData(Array.isArray(data) ? data : []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <Spin size="large" style={{ display: "block", padding: 40 }} />;
  }

  if (navData.length === 0) {
    return <div style={{ padding: 20, color: "#999" }}>暂无净值数据</div>;
  }

  // 准备图表数据
  const chartData = navData.map((item) => ({
    date: item.trade_date,
    nav: item.nav != null ? Number(item.nav) : 1,
    benchmark: item.benchmark_nav != null ? Number(item.benchmark_nav) : null,
    totalAssets: item.total_assets != null ? Number(item.total_assets) : 0,
    cash: item.cash != null ? Number(item.cash) : 0,
    positionValue: item.position_value != null ? Number(item.position_value) : 0,
  }));

  // 计算回撤数据
  let peak = 0;
  const drawdownData = chartData.map((item) => {
    if (item.totalAssets > peak) {
      peak = item.totalAssets;
    }
    const drawdown = peak > 0 ? ((item.totalAssets - peak) / peak) * 100 : 0;
    return {
      date: item.date,
      drawdown: Math.round(drawdown * 100) / 100,
    };
  });

  // 收益率数据
  const returnData = chartData.map((item) => ({
    date: item.date,
    return: Math.round((item.nav - 1) * 10000) / 100, // 百分比
  }));

  // 准备双线数据
  const hasBenchmark = chartData.some((d) => d.benchmark != null);
  const dualLineData = hasBenchmark
    ? chartData.flatMap((d) => [
        { date: d.date, type: "策略净值", value: d.nav },
        ...(d.benchmark != null ? [{ date: d.date, type: "沪深300", value: d.benchmark }] : []),
      ])
    : chartData.map((d) => ({ date: d.date, type: "策略净值", value: d.nav }));

  return (
    <Row gutter={16}>
      <Col span={24}>
        <Card title="净值曲线" size="small" style={{ marginBottom: 16 }}>
          {hasBenchmark ? (
            <Line
              data={dualLineData}
              xField="date"
              yField="value"
              seriesField="type"
              height={300}
              point={{ size: 0 }}
              line={{ style: { lineWidth: 2 } }}
              color={["#1890ff", "#999"]}
              tooltip={{
                formatter: (datum: any) => ({
                  name: datum.type,
                  value: datum.value?.toFixed(4),
                }),
              }}
            />
          ) : (
            <Line
              data={chartData}
              xField="date"
              yField="nav"
              height={300}
              point={{ size: 0 }}
              line={{ style: { lineWidth: 2 } }}
              tooltip={{
                formatter: (datum: any) => ({
                  name: "净值",
                  value: datum.nav?.toFixed(4),
                }),
              }}
            />
          )}
        </Card>
      </Col>
      <Col span={12}>
        <Card title="收益率 (%)" size="small">
          <Line
            data={returnData}
            xField="date"
            yField="return"
            height={200}
            point={{ size: 0 }}
            line={{ style: { lineWidth: 1.5 } }}
            yAxis={{
              label: {
                formatter: (v: string) => `${v}%`,
              },
            }}
            tooltip={{
              formatter: (datum: any) => ({
                name: "收益率",
                value: `${datum.return?.toFixed(2)}%`,
              }),
            }}
          />
        </Card>
      </Col>
      <Col span={12}>
        <Card title="回撤 (%)" size="small">
          <Line
            data={drawdownData}
            xField="date"
            yField="drawdown"
            height={200}
            point={{ size: 0 }}
            line={{ style: { lineWidth: 1.5, stroke: "#cf1322" } }}
            yAxis={{
              label: {
                formatter: (v: string) => `${v}%`,
              },
            }}
            tooltip={{
              formatter: (datum: any) => ({
                name: "回撤",
                value: `${datum.drawdown?.toFixed(2)}%`,
              }),
            }}
          />
        </Card>
      </Col>
    </Row>
  );
}
