import { useEffect, useState } from "react";
import { Card, Row, Col, Spin, Empty } from "antd";
import { Line } from "@ant-design/charts";

interface DailySnapshot {
  trade_date: string;
  market_value: number;
  pnl: number;
  pnl_pct: number;
}

interface AccountChartProps {
  accountId: number;
}

export default function AccountChart({ accountId }: AccountChartProps) {
  const [snapshots, setSnapshots] = useState<DailySnapshot[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadSnapshots();
  }, [accountId]);

  const loadSnapshots = async () => {
    setLoading(true);
    try {
      // 从 position_daily_snapshot 聚合每日总资产
      const resp = await fetch(`/api/quant/sim/accounts/${accountId}/daily-assets`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
      });
      const data = await resp.json();
      if (data.code === 0 && Array.isArray(data.data)) {
        setSnapshots(data.data);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <Spin size="large" style={{ display: "block", padding: 40 }} />;
  }

  if (snapshots.length === 0) {
    return <Empty description="暂无历史数据" style={{ padding: 40 }} />;
  }

  // 计算每日总资产（需要从后端聚合）
  // 这里简化为直接用 market_value
  const chartData = snapshots.map((s) => ({
    date: s.trade_date,
    value: s.market_value,
    pnl: s.pnl,
  }));

  // 计算回撤
  let peak = 0;
  const drawdownData = chartData.map((item) => {
    if (item.value > peak) peak = item.value;
    const dd = peak > 0 ? ((item.value - peak) / peak) * 100 : 0;
    return { date: item.date, drawdown: Math.round(dd * 100) / 100 };
  });

  return (
    <Row gutter={16} style={{ marginBottom: 16 }}>
      <Col span={24}>
        <Card title="账户净值曲线" size="small">
          <Line
            data={chartData}
            xField="date"
            yField="value"
            height={250}
            point={{ size: 0 }}
            line={{ style: { lineWidth: 2 } }}
          />
        </Card>
      </Col>
    </Row>
  );
}
