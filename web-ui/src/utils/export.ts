/**
 * Export data to CSV file
 */
export function exportToCsv(
  filename: string,
  headers: string[],
  rows: (string | number)[][]
): void {
  const csvContent = [
    headers.join(","),
    ...rows.map((row) =>
      row
        .map((cell) => {
          const str = String(cell ?? "");
          // Escape commas and quotes
          if (str.includes(",") || str.includes('"') || str.includes("\n")) {
            return `"${str.replace(/"/g, '""')}"`;
          }
          return str;
        })
        .join(",")
    ),
  ].join("\n");

  // Add BOM for Chinese character support in Excel
  const blob = new Blob(["﻿" + csvContent], {
    type: "text/csv;charset=utf-8;",
  });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

/**
 * Export trade orders to CSV
 */
export function exportOrdersToCsv(
  orders: any[],
  accountName: string
): void {
  const headers = [
    "股票代码",
    "股票名称",
    "方向",
    "价格",
    "数量",
    "手续费",
    "时间",
  ];

  const rows = orders.map((o) => [
    o.code,
    o.stock_name || "",
    o.side === "buy" ? "买入" : "卖出",
    o.price,
    o.quantity,
    o.commission || 0,
    o.created_at,
  ]);

  const date = new Date().toISOString().slice(0, 10);
  exportToCsv(`${accountName}_交易记录_${date}.csv`, headers, rows);
}

/**
 * Export positions to CSV
 */
export function exportPositionsToCsv(
  positions: any[],
  accountName: string
): void {
  const headers = [
    "股票代码",
    "股票名称",
    "持仓数量",
    "可用数量",
    "成本价",
  ];

  const rows = positions.map((p) => [
    p.code,
    p.stock_name || "",
    p.quantity,
    p.available_quantity || 0,
    p.avg_price,
  ]);

  const date = new Date().toISOString().slice(0, 10);
  exportToCsv(`${accountName}_持仓_${date}.csv`, headers, rows);
}

/**
 * Export backtest results to CSV
 */
export function exportBacktestToCsv(
  results: any[],
  strategies: any[]
): void {
  const strategyMap = Object.fromEntries(strategies.map((s: any) => [s.id, s.name]));

  const headers = [
    "ID",
    "策略",
    "开始日期",
    "结束日期",
    "总收益",
    "年化收益",
    "最大回撤",
    "夏普比率",
    "胜率",
    "交易次数",
  ];

  const rows = results.map((r) => [
    r.id,
    strategyMap[r.strategy_id] || r.strategy_id,
    r.start_date,
    r.end_date,
    r.total_return != null ? `${(r.total_return * 100).toFixed(2)}%` : "",
    r.annual_return != null ? `${(r.annual_return * 100).toFixed(2)}%` : "",
    r.max_drawdown != null ? `${(r.max_drawdown * 100).toFixed(2)}%` : "",
    r.sharpe_ratio != null ? Number(r.sharpe_ratio).toFixed(2) : "",
    r.win_rate != null ? `${(r.win_rate * 100).toFixed(1)}%` : "",
    r.total_trades || 0,
  ]);

  const date = new Date().toISOString().slice(0, 10);
  exportToCsv(`回测记录_${date}.csv`, headers, rows);
}

/**
 * Export backtest trades to CSV
 */
export function exportBacktestTradesToCsv(
  trades: any[],
  backtestId: number
): void {
  const headers = [
    "股票代码",
    "股票名称",
    "方向",
    "价格",
    "数量",
    "日期",
    "盈亏",
    "信号来源",
  ];

  const rows = trades.map((t) => [
    t.code,
    t.stock_name || "",
    t.side === "buy" ? "买入" : "卖出",
    t.price,
    t.quantity,
    t.trade_date,
    t.pnl || 0,
    t.signal_source || "",
  ]);

  exportToCsv(`回测明细_${backtestId}.csv`, headers, rows);
}
