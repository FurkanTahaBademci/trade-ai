export type Instrument = { ticker: string; name: string; city: string | null; is_active: boolean; updated_at: string };
export type Price = { date: string; close: number; high: number | null; low: number | null; avg_price: number | null; volume_try: number | null; close_usd: number | null; market_cap_try: number | null };
export type IndexPrice = { date: string; value: number };
export type NewsArticle = { id: number; source: string; canonical_url: string; title: string; summary: string | null; author: string | null; image_url: string | null; published_at: string; ticker_codes: string[]; impact_score?: number | null; sentiment_score?: number | null; event_type?: string | null; source_guid?: string | null; raw_entry?: Record<string, unknown>; fetched_at?: string; updated_at?: string };
export type Attachment = { obj_id: string; file_name: string; file_extension: string | null; size_bytes?: number | null };
export type Disclosure = { disclosure_index: number; published_at: string; kap_title: string; subject: string | null; summary: string | null; disclosure_class: string | null; disclosure_type: string | null; disclosure_category: string | null; ticker_codes: string[]; is_late: boolean; attachment_count: number; body_html?: string | null; body_text?: string | null; attachments?: Attachment[] };
export type Evaluation = { id: number; source_type: "news" | "kap"; source_id: number; prompt_version: string; tier: number; provider: string; api_mode: "interactions" | "generate_content"; model: string; status: string; attempt_count: number; ticker_codes: string[]; relevance_score: number | null; sentiment_score: number | null; impact_score: number | null; confidence: number | null; event_type: string | null; time_horizon: string | null; summary: string | null; requires_tier2: boolean; input_tokens: number | null; output_tokens: number | null; total_tokens: number | null; latency_ms: number | null; completed_at: string | null; created_at: string; rationale?: string | null; result?: Record<string, unknown> | null; error_text?: string | null };
export type Fundamental = { ticker: string; financial_group: string; exchange: string; year: number; period: number; revenue: number | null; gross_profit: number | null; operating_profit: number | null; ebitda_proxy: number | null; net_income: number | null; operating_cash_flow: number | null; free_cash_flow: number | null; current_assets: number | null; cash: number | null; current_liabilities: number | null; short_term_debt: number | null; long_term_debt: number | null; equity: number | null; revenue_yoy: number | null; net_income_yoy: number | null; gross_margin: number | null; operating_margin: number | null; net_margin: number | null; current_ratio: number | null; debt_to_equity: number | null; cash_to_debt: number | null; annualized_roe: number | null; operating_cash_flow_margin: number | null; free_cash_flow_margin: number | null; fundamental_score: number | null; score_components: Record<string, number>; data_completeness: number; computed_at: string };
export type Consensus = { ticker: string; as_of_date: string; institution_count: number; buy_count: number; hold_count: number; sell_count: number; review_count: number; average_target: number | null; median_target: number | null; minimum_target: number | null; maximum_target: number | null; market_price: number | null; implied_upside_pct: number | null; target_dispersion: number | null; recommendation_score: number | null; source_breakdown: Record<string, unknown>; computed_at: string };
export type Recommendation = { ticker: string; source: string; institution: string; recommendation_raw: string; recommendation_normalized: string; target_price: number | null; reference_price: number | null; upside_pct: number | null; recommendation_date: string; source_url: string; updated_at: string };
export type FundFlow = { fund_kind: string; date: string; fund_count: number; flow_observation_count: number; total_aum: number; total_net_flow: number | null; total_stock_exposure: number; estimated_stock_flow: number | null; positive_flow_pct: number | null; computed_at: string };
export type CompositeSignal = { id: number; ticker: string; as_of_date: string; model_version: string; composite_score: number; signal_label: "VERY_POSITIVE" | "POSITIVE" | "NEUTRAL" | "NEGATIVE" | "VERY_NEGATIVE"; confidence: number; coverage_count: number; component_scores: Record<string, number>; component_weights: Record<string, number>; evidence: Record<string, unknown>; computed_at: string };
export type SignalHistoryPoint = { as_of_date: string; composite_score: number; signal_label: CompositeSignal["signal_label"]; confidence: number; component_scores: Record<string, number> };
export type SignalDriver = { kind: "news" | "kap" | "analyst" | string; title: string; occurred_at: string | null; effect: number; href: string };
export type SignalHistory = { ticker: string; points: SignalHistoryPoint[]; drivers: SignalDriver[] };
export type SignalHorizonStat ={ horizon: number; label: string; observation_count: number; average_return_pct: number | null; hit_rate_pct: number | null; average_excess_pct?: number | null; beat_rate_pct?: number | null };
export type CalendarEventType = "PPK" | "FINANCIAL_REPORT" | "DIVIDEND" | "GENERAL_ASSEMBLY" | "CAPITAL_INCREASE";
export type CalendarEvent = { id: string; date: string; type: CalendarEventType; type_label: string; title: string; detail: string | null; source: "TCMB" | "KAP"; tickers: string[]; disclosure_index: number | null; upcoming: boolean };
export type MarketFeedItem = { ticker: string; name: string; composite_score: number | null; signal_label: string | null };
export type PaperPortfolio = { id: number; name: string; strategy_version: string; base_currency: string; status: "ACTIVE" | "PAUSED"; initial_cash: number; cash_balance: number; realized_pnl: number; total_fees: number; created_at: string; updated_at: string };
export type PaperPosition = { id: number; portfolio_id: number; ticker: string; quantity: number; average_cost: number; last_price: number; market_value: number; unrealized_pnl: number; high_water_price?: number | null; opened_at: string; updated_at: string };
export type PaperTrade = { id: number; ticker: string; signal_snapshot_id: number | null; strategy_version: string; trade_date: string; side: "BUY" | "SELL"; quantity: number; price: number; gross_amount: number; fee_amount: number; realized_pnl: number | null; reason: string; exit_reason?: "stop_loss" | "take_profit" | "trailing_stop" | "signal" | "rebalance" | null; created_at: string };
export type PaperSnapshot = { id: number; portfolio_id: number; snapshot_date: string; cash_balance: number; positions_value: number; total_equity: number; realized_pnl: number; unrealized_pnl: number; total_return_pct: number; position_count: number; weights: Record<string, number>; computed_at: string };
export type PaperRisk = { portfolio_id: number; observations: number; max_drawdown_pct: number; volatility_pct: number | null; top_position_ticker: string | null; top_position_weight_pct: number; cash_weight_pct: number; sector_allocation: { sector: string; value: number; weight_pct: number }[]; rules: { stop_loss_pct: number; take_profit_pct: number; trailing_stop_pct: number; max_position_weight_pct: number; max_sector_weight_pct: number; rebalance_enabled: boolean } };
export type ComponentHealth = { name: string; label: string; state: "healthy" | "stale" | "error" | "pending"; last_success: string | null; last_error_at: string | null; age_seconds: number | null; max_age_seconds: number };
export type SystemHealth = { status: "ok" | "degraded"; db: string; redis: string; monitoring: { status: "ok" | "degraded" | "pending"; problem_count: number; pending_count: number; worker: ComponentHealth; collectors: Record<string, ComponentHealth>; checked_at: string } | null };
export type MonetaryPolicyDecision = { id: number; decision_no: string; decision_date: string; status: "PUBLISHED" | "SCHEDULED"; decision_type: "HIKE" | "CUT" | "HOLD" | "SCHEDULED"; policy_rate: number | null; previous_policy_rate: number | null; change_bps: number | null; lending_rate: number | null; borrowing_rate: number | null; title: string; summary: string | null; guidance: string | null; source_url: string | null; market_impact: { method: string; change_bps: number | null; overall: string; equities: string; banks: string; real_estate: string; try: string; bonds: string; disclaimer: string }; created_at: string; updated_at: string };
export type CollectorSchedule = { name: string; label: string; job_name: string; interval_minutes: number; minimum_interval_minutes: number; enabled: boolean; next_run_at: string | null; last_enqueued_at: string | null; updated_at: string };
export type SettingStatus = { key: string; label: string; kind: "secret" | "url" | "boolean" | "choice" | "text"; is_set: boolean; source: "database" | "env" | "unset"; preview: string | null; choices: { value: string; label: string }[]; updated_at: string | null };
export type StorageReport = { database_size_bytes: number; tables: { table: string; size_bytes: number; row_estimate: number }[] };
export type LlmOperationsReport = {
  provider_pause?: { reason: "daily_quota" | "rate_limit"; model: string; retry_at: string } | null;
  generated_at: string;
  config: { enabled: boolean; api_mode: "interactions" | "generate_content"; tier1_model: string; tier2_model: string; tier1_group_size: number; batch_size: number; max_attempts: number };
  budget: { window_started_at: string; input_tokens: { used: number; limit: number }; output_tokens: { used: number; limit: number }; exhausted: boolean };
  today: { succeeded: number; failed: number; running: number; last_completed_at: string | null };
  backlog: { news: number; kap: number; documents: number; estimated_tier1_requests: number; retryable_failures: number; stale_running: number };
  unresolved_failures: number;
  failure_categories?: { category: "daily_quota" | "rate_limit" | "provider_unavailable" | "invalid_response" | "other"; label: string; count: number }[];
};
export type BacktestPoint = { point_date: string; cash: number; positions_value: number; total_equity: number; position_count: number };
export type BacktestTrade = { id: number; ticker: string; side: "BUY" | "SELL"; signal_date: string; execution_date: string; quantity: number; price: number; gross_amount: number; fee_amount: number; realized_pnl: number | null };
export type BacktestRun = { id: number; strategy_version: string; signal_model_version: string; status: "COMPLETED" | "INSUFFICIENT_DATA"; start_date: string; end_date: string; initial_cash: number; final_equity: number; total_return_pct: number; max_drawdown_pct: number; annualized_volatility_pct: number | null; sharpe_ratio: number | null; closed_trades: number; winning_trades: number; win_rate_pct: number | null; total_fees: number; signal_count: number; price_count: number; skipped_signal_count: number; config: { entry_score: number; exit_score: number; min_confidence: number; min_coverage: number; max_positions: number; max_position_weight: number; fee_rate: number; slippage_rate: number; execution_price: string; risk_free_rate: number }; created_at: string; points?: BacktestPoint[]; trades?: BacktestTrade[] };
export type SystemStats = { instruments_total: number; news_total: number; news_by_source: Record<string, number>; disclosures_total: number; signals_total: number; signals_by_label: Record<string, number>; evaluations_total: number; evaluations_by_source: Record<string, number>; funds_total: number };

export type MarketHeatmapStock = {
  ticker: string;
  name: string;
  sector: string;
  last_price: number;
  change_pct: number;
  volume_try: number;
  market_cap_try: number;
  composite_score: number | null;
  signal_label: string | null;
};

export type MarketHeatmapSector = {
  name: string;
  stock_count: number;
  avg_change_pct: number;
  total_volume_try: number;
  total_market_cap_try: number;
  stocks: MarketHeatmapStock[];
};

export type MarketHeatmapData = {
  as_of_date: string | null;
  sectors: MarketHeatmapSector[];
  summary: {
    total_instruments: number;
    positive_count: number;
    negative_count: number;
    neutral_count: number;
    market_avg_change_pct: number;
  };
};

export type AIBriefingCatalyst = {
  title: string;
  category: "KAP" | "HABER" | "MAKRO";
  impact: "POSITIVE" | "NEGATIVE" | "NEUTRAL";
  tickers: string[];
  description: string;
};

export type AIBriefingSector = {
  sector: string;
  trend: string;
  comment: string;
};

export type AIBriefingData = {
  date: string;
  session: "SABAH" | "AKŞAM";
  headline: string;
  market_mood: "BULLISH" | "NEUTRAL" | "BEARISH";
  summary: string;
  catalysts: AIBriefingCatalyst[];
  sector_commentary: AIBriefingSector[];
  actionable_takeaways: string[];
  generated_at: string;
};

export type CompanyComparePrice = {
  last_price: number;
  change_1d_pct: number;
  change_1m_pct: number;
  change_1y_pct: number;
  volume_try: number;
  market_cap_try: number;
};

export type CompanyCompareMultiples = {
  pe_ratio: number | null;
  pb_ratio: number | null;
  revenue_try: number | null;
  net_income_try: number | null;
  net_margin_pct: number | null;
  roe_pct: number | null;
  debt_to_equity: number | null;
  current_ratio: number | null;
  fundamental_score: number | null;
};

export type CompanyCompareConsensus = {
  target_price: number | null;
  upside_pct: number | null;
  buy_count: number;
  hold_count: number;
  sell_count: number;
  score: number;
};

export type CompanyCompareSignal = {
  composite_score: number;
  label: string;
};

export type CompanyCompareRadarScores = {
  valuation: number;
  profitability: number;
  momentum: number;
  analysts: number;
  ai_sentiment: number;
};

export type CompanyCompareStock = {
  ticker: string;
  name: string;
  sector: string;
  price: CompanyComparePrice;
  multiples: CompanyCompareMultiples;
  consensus: CompanyCompareConsensus;
  signal: CompanyCompareSignal;
  radar_scores: CompanyCompareRadarScores;
};

export type CompanyComparisonData = {
  tickers: string[];
  as_of_date: string;
  companies: CompanyCompareStock[];
  normalized_chart: Array<{ date: string; [ticker: string]: number | string }>;
  dimensions: Array<{ key: string; label: string }>;
};
export type MacroSeries = { code: string; label: string; latest_date: string | null; latest_value: number | null; change_pct: number | null; yoy_pct: number | null; history: { date: string; value: number }[] };
