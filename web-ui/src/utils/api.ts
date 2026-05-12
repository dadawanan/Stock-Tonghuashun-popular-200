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