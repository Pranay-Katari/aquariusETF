export type Source = {
  url: string;
  title: string;
  snippet: string;
  retrieved_at?: string | null;
};
export type Holding = {
  ticker: string;
  company_name: string;
  target_weight: number;
  theme_tag: string;
  rationale: string;
  confidence?: number | null;
  sources: Source[];
};
export type ETF = {
  id: string;
  name: string;
  symbol: string;
  description: string;
  version: number;
  holdings: Holding[];
  created_at: string;
  updated_at: string;
};
export type Config = {
  start_date: string;
  end_date: string;
  initial_capital: number;
  benchmark: "SPY" | "QQQ";
  rebalance_frequency: "none" | "monthly" | "quarterly";
  commission_bps: number;
  slippage_bps: number;
  dividend_mode: "total_return";
  risk_free_rate: number;
};
export type Backtest = {
  id: string;
  etf_id: string;
  portfolio_version: number;
  status: "queued" | "running" | "completed" | "failed" | "canceled";
  config: Config;
  metrics: Record<string, number | null>;
  warnings: string[];
  error: string | null;
  checksum: string;
  engine_version: string;
  created_at: string;
};
export type Point = { time: string; value: number };
export type Series = {
  portfolio: Point[];
  benchmark: Point[];
  drawdown: Point[];
};
export type Attribution = {
  ticker: string;
  contribution_to_return: number;
  pnl: number;
  average_weight: number;
  current_weight: number;
  traded_notional: number;
};
export type Preview = {
  id: string;
  environment: string;
  investment: number;
  orders: {
    symbol: string;
    notional: string;
    side: string;
    client_order_id: string;
  }[];
  residual_cash: number;
  broker_validated: boolean;
  expires_at: string;
  warning: string;
};
