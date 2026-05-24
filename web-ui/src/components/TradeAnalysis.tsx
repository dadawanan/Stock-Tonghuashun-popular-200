import { useEffect, useState } from "react";
import { Card, Col, Row, Statistic, Spin } from "antd";
import { quantApi } from "../utils";

interface TradeAnalysisData {
  total_trades: number;
  buy_count: number;
  sell_count: number;
  win_count: number;
  loss_count: number;
  win_rate: number;
  total_pnl: number;
  avg_win: number;
  avg_loss: number;
  profit_loss_ratio: number;
  avg_holding_days: number;
  max_consecutive_losses: number;
}

interface TradeAnalysisProps {
  accountId: number;
}

export default function TradeAnalysis({ accountId }: TradeAnalysisProps) {
  const [data, setData] = useState<TradeAnalysisData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadData();
  }, [accountId]);

  const loadData = async () => {
    setLoading(true);
    try {
      const result = await quantApi.getTradeAnalysis(accountId);
      setData(result);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <Spin size="small" />;
  }

  if (!data || data.total_trades === 0) {
    return null;
  }

  return (
    <Card title="交易分析" size="small" style={{ marginBottom: 16 }}>
      <Row gutter={16}>
        <Col span={4}>
          <Statistic title="总交易次数" value={data.total_trades} />
        </Col>
        <Col span={4}>
          <Statistic title="胜率" value={data.win_rate * 100} precision={1} suffix="%" />
        </Col>
        <Col span={4}>
          <Statistic
            title="总盈亏"
            value={data.total_pnl}
            precision={2}
            prefix="¥"
            valueStyle={{ color: data.total_pnl >= 0 ? "#3f8600" : "#cf1322" }}
          />
        </Col>
        <Col span={3}>
          <Statistic title="平均盈利" value={data.avg_win} precision={0} prefix="¥" />
        </Col>
        <Col span={3}>
          <Statistic title="平均亏损" value={data.avg_loss} precision={0} prefix="¥" />
        </Col>
        <Col span={3}>
          <Statistic title="盈亏比" value={data.profit_loss_ratio} precision={2} />
        </Col>
        <Col span={3}>
          <Statistic title="平均持仓天数" value={data.avg_holding_days} precision={1} suffix="天" />
        </Col>
      </Row>
    </Card>
  );
}
