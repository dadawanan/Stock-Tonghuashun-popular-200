import http from './request';
import type { AuthTokensPublic } from './auth-storage';

export interface AuthUser {
  id: number;
  username: string;
}

export const authApi = {
  login: (username: string, password: string) =>
    http.post<AuthTokensPublic>('/api/auth/login', { username, password }),

  register: (username: string, password: string) =>
    http.post<AuthUser>('/api/auth/register', { username, password }),

  logout: () => http.post<null>('/api/auth/logout'),

  /** 静默请求：未登录或 token 失效时不弹全局错误（由路由/布局处理跳转） */
  me: () => http.get<AuthUser>('/api/auth/me', { showError: false }),
};

export interface PopularityStock {
  stock_code: string;
  stock_name: string;
  rank: number;
  snapshot_time: string;
}

export interface PopularityComparison {
  current_snapshot_time: string;
  previous_snapshot_time: string;
  new_entries: Array<{
    stock_code: string;
    stock_name: string;
    current_rank: number;
  }>;
  removed_entries: Array<{
    stock_code: string;
    stock_name: string;
    previous_rank: number;
  }>;
  rank_changes: Array<any>;
}

export interface AnalysisResult {
  stock_code: string;
  stock_name: string;
  /** 最新人气榜快照中的名次（仅在同花顺人气 Top200 内时有值） */
  popularity_rank?: number | null;
  popularity_score?: number | null;
  popularity_previous_rank?: number | null;
  popularity_rank_change?: number | null;
  popularity_snapshot_time?: string | null;
  event_types: string;
  text_event_label: string;
  text_score: number;
  sentiment_strength: string;
  duration_tag: string;
  fact_support: string;
  bullish_logic: string;
  bearish_logic: string;
  news_count: number;
  price_volume_signal: string;
  fund_flow_signal: string;
  behavior_label: string;
  market_score: number;
  integrated_score: number;
  decision: string;
  analyzed_at: string;
}

export interface NewsItem {
  id: number;
  stock_code: string;
  stock_name?: string | null;
  title: string;
  content?: string | null;
  summary?: string | null;
  published_at?: string | null;
  source?: string | null;
  url?: string | null;
}

export const popularityApi = {
  fetch: () => http.post('/api/popularity/fetch'),
  
  getLatest: () => http.get<{
    snapshot_time: string;
    count: number;
    stocks: PopularityStock[];
  }>('/api/popularity/latest'),
  
  compareLatest: () => http.post<PopularityComparison>('/api/popularity/compare-latest'),
};

export interface AnalyzeApiData {
  result_count: number;
  stocks: string[];
  fetch_result?: {
    run_id: number;
    stock_count: number;
    news_count: number;
    market_count: number;
  };
  results?: unknown[];
  message?: string;
}

export const analysisApi = {
  runAll: () => http.post<{ analysis: AnalyzeApiData } & Record<string, unknown>>('/api/run-all'),

  analyzeSingle: (stockCode: string) =>
    http.post<AnalyzeApiData>(
      `/api/analyze?stock_code=${encodeURIComponent(stockCode.trim())}`,
    ),

  analyzeNewEntries: () => http.post('/api/analyze/new-entries'),
  
  getList: (limit: number = 200) => http.get<AnalysisResult[]>('/api/analysis', {
    params: { limit },
  }),
  
  getByStockCode: (stockCode: string) => http.get<AnalysisResult>(`/api/analysis/${stockCode}`),
};

export const newsApi = {
  getByStockCode: (stockCode: string, limit: number = 20) =>
    http.get<NewsItem[]>(`/api/news/${encodeURIComponent(stockCode)}`, {
      params: { limit },
    }),
};

export const stockApi = {
  getAll: () => http.get<any[]>('/api/stocks'),
};

export const healthApi = {
  check: () => http.get<{ ready: boolean }>('/api/health'),
};

// ── Quant Module APIs ──

export interface Strategy {
  id: number;
  name: string;
  type: string;
  params: Record<string, any>;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface BacktestResult {
  id: number;
  strategy_id: number;
  start_date: string;
  end_date: string;
  total_return: number | null;
  annual_return: number | null;
  max_drawdown: number | null;
  max_drawdown_days: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  calmar_ratio: number | null;
  alpha: number | null;
  beta: number | null;
  information_ratio: number | null;
  win_rate: number | null;
  total_trades: number | null;
  monthly_returns: Record<string, number> | null;
  created_at: string;
}

export interface BacktestTrade {
  code: string;
  stock_name?: string | null;
  side: string;
  price: number | null;
  quantity: number | null;
  trade_date: string;
  pnl: number | null;
  signal_source: string | null;
}

export interface BacktestNav {
  trade_date: string;
  nav: number | null;
  benchmark_nav?: number | null;
  total_assets: number | null;
  cash: number | null;
  position_value: number | null;
}

export interface SimAccount {
  id: number;
  user_id: number;
  account_name: string;
  initial_capital: string;
  current_capital: string;
  total_assets: string;
  status: string;
  strategy_id: number | null;
  config: Record<string, any> | null;
  created_at: string;
}

export interface Position {
  id: number;
  account_id: number;
  code: string;
  stock_name?: string | null;
  quantity: number;
  avg_price: string;
  available_quantity: number | null;
}

export interface TradeOrder {
  id: number;
  code: string;
  stock_name?: string | null;
  side: string;
  price: string;
  quantity: number;
  status: string | null;
  commission: string | null;
  created_at: string;
}

export interface PendingOrder {
  id: number;
  account_id: number;
  code: string;
  stock_name?: string | null;
  side: string;
  target_price: string;
  quantity: number;
  status: string;
  note?: string | null;
  filled_at?: string | null;
  filled_price?: string | null;
  created_at: string;
}

export interface FeedbackInsight {
  overall: {
    win_rate: number | null;
    sharpe: number | null;
    max_drawdown: number | null;
    annual_return: number | null;
  };
  by_signal: Record<string, {
    wins: number;
    losses: number;
    total_pnl: number;
    trades: number;
    win_rate: number;
  }>;
  suggestions: string[];
}

export const quantApi = {
  // Strategies
  listStrategies: () => http.get<Strategy[]>('/api/quant/strategies/'),

  getStrategy: (id: number) => http.get<Strategy>(`/api/quant/strategies/${id}`),

  createStrategy: (data: { name: string; type: string; params?: Record<string, any>; description?: string }) =>
    http.post<Strategy>('/api/quant/strategies/', data),

  updateStrategy: (id: number, data: Partial<Strategy>) =>
    http.put<Strategy>(`/api/quant/strategies/${id}`, data),

  deleteStrategy: (id: number) => http.delete(`/api/quant/strategies/${id}`),

  previewSignals: (data?: { strategy_ids?: number[]; max_stocks?: number }) =>
    http.post<any>('/api/quant/strategies/signals/preview', data || {}),

  // Data maintenance
  backfillDaily: () =>
    http.post<{ message: string }>('/api/quant/daily/backfill'),

  computeIndicators: () =>
    http.post<{ computed: number }>('/api/quant/indicators/compute'),

  // Backtest
  runBacktest: (data: {
    strategy_id: number;
    start_date: string;
    end_date: string;
    initial_capital?: number;
    stock_codes?: string[];
  }) => http.post<{ backtest_id: number; metrics: any; trade_count: number; nav_count: number }>(
    '/api/quant/backtest/run', data
  ),

  listBacktestResults: (strategyId?: number) =>
    http.get<BacktestResult[]>('/api/quant/backtest/results', {
      params: strategyId ? { strategy_id: strategyId } : {},
    }),

  getBacktestResult: (id: number) => http.get<BacktestResult>(`/api/quant/backtest/results/${id}`),

  getBacktestTrades: (id: number) => http.get<BacktestTrade[]>(`/api/quant/backtest/results/${id}/trades`),

  getBacktestNav: (id: number) => http.get<BacktestNav[]>(`/api/quant/backtest/results/${id}/nav`),

  deleteBacktestResult: (id: number) => http.delete(`/api/quant/backtest/results/${id}`),

  batchDeleteBacktestResults: (ids: number[]) =>
    http.post<{ deleted: number }>('/api/quant/backtest/results/batch-delete', ids),

  // Sim Trading
  listSimAccounts: () => http.get<SimAccount[]>('/api/quant/sim/accounts'),

  createSimAccount: (data: { account_name: string; initial_capital?: number; strategy_id?: number }) =>
    http.post<SimAccount>('/api/quant/sim/accounts', data),

  getSimAccount: (id: number) => http.get<SimAccount>(`/api/quant/sim/accounts/${id}`),

  updateSimAccount: (id: number, data: { strategy_id?: number | null; strategy_ids?: number[] }) =>
    http.put<SimAccount>(`/api/quant/sim/accounts/${id}`, data),

  deleteSimAccount: (id: number) => http.delete(`/api/quant/sim/accounts/${id}`),

  resumeSimAccount: (id: number) => http.post<any>(`/api/quant/sim/accounts/${id}/resume`),

  getPositions: (accountId: number) =>
    http.get<Position[]>(`/api/quant/sim/accounts/${accountId}/positions`),

  getOrders: (accountId: number) =>
    http.get<TradeOrder[]>(`/api/quant/sim/accounts/${accountId}/orders`),

  getDailyAssets: (accountId: number) =>
    http.get<{ trade_date: string; market_value: number; pnl: number }[]>(
      `/api/quant/sim/accounts/${accountId}/daily-assets`
    ),

  getTradeAnalysis: (accountId: number) =>
    http.get<{
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
    }>(`/api/quant/sim/accounts/${accountId}/trade-analysis`),

  executeTrade: (data: { account_id: number; code: string; side: 'buy' | 'sell'; quantity: number; price?: number }) =>
    http.post<TradeOrder & { pnl?: number }>('/api/quant/sim/trade', data),

  dailySettlement: (accountId: number, tradeDate: string) =>
    http.post<any>(
      `/api/quant/sim/settlement?account_id=${accountId}&trade_date=${tradeDate}`
    ),

  // Pending Orders
  listPendingOrders: (accountId: number, status?: string) =>
    http.get<PendingOrder[]>(`/api/quant/pending-orders/`, {
      params: { account_id: accountId, status: status || "pending" },
    }),

  createPendingOrder: (data: {
    account_id: number;
    code: string;
    side: 'buy' | 'sell';
    target_price: number;
    quantity: number;
    note?: string;
  }) => http.post<PendingOrder>('/api/quant/pending-orders/', null, {
    params: data,
  }),

  cancelPendingOrder: (orderId: number) =>
    http.delete(`/api/quant/pending-orders/${orderId}`),

  cancelAllPendingOrders: (accountId: number) =>
    http.post<{ cancelled: number }>(`/api/quant/pending-orders/cancel-all`, null, {
      params: { account_id: accountId },
    }),

  // Feedback
  getInsights: (backtestId: number) =>
    http.get<FeedbackInsight>(`/api/quant/feedback/insights/${backtestId}`),

  getSuggestions: (backtestId: number) =>
    http.get<any>(`/api/quant/feedback/suggestions/${backtestId}`),

  // Market
  getRealtimePrices: (codes: string[]) =>
    http.get<Record<string, number | null>>('/api/quant/market/prices', {
      params: { codes: codes.join(',') },
    }),

  // Optimizer
  gridSearch: (data: {
    strategy_id: number;
    param_grid: Record<string, any[]>;
    stock_codes?: string[];
    start_date: string;
    end_date: string;
    initial_capital?: number;
    metric?: string;
    top_n?: number;
  }) => http.post<{ params: Record<string, any>; metrics: any; backtest_id: number }[]>(
    '/api/quant/optimizer/grid-search', data
  ),

  suggestParams: (strategyType: string) =>
    http.get<Record<string, any[]>>(`/api/quant/optimizer/suggest/${strategyType}`),

  walkForward: (data: {
    strategy_id: number;
    param_grid: Record<string, any[]>;
    stock_codes?: string[];
    start_date: string;
    end_date: string;
    train_days?: number;
    test_days?: number;
    step_days?: number;
    initial_capital?: number;
    metric?: string;
  }) => http.post<{
    windows: Array<{
      window_id: number;
      train_period: string;
      test_period: string;
      best_params: Record<string, any>;
      train_metrics: Record<string, number>;
      test_metrics: Record<string, number>;
    }>;
    avg_test_metrics: Record<string, number>;
    best_params_per_window: Record<string, any>[];
    stability_score: number;
  }>('/api/quant/optimizer/walk-forward', data),
};

// ── Chat Assistant ──

export interface IntentAction {
  type: 'navigate' | 'query' | 'analyze';
  payload: Record<string, any>;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  actions?: IntentAction[];
  isWelcome?: boolean;
}

export interface ChatChunk {
  type: 'token' | 'done' | 'error';
  content: string;
}

export const chatApi = {
  sendMessage: (message: string, history: { role: string; content: string }[] = []) =>
    fetch('/api/chat/send', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify({ message, history }),
    }),
};
