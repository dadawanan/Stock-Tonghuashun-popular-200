-- Stock pool table
CREATE TABLE IF NOT EXISTS stocks (
    stock_code      VARCHAR(10) PRIMARY KEY,
    stock_name      VARCHAR(64),
    source_latest_price  DECIMAL(12, 4),
    source_pct_change    DECIMAL(8, 4),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Raw news articles per stock
CREATE TABLE IF NOT EXISTS news_data (
    id              BIGSERIAL PRIMARY KEY,
    stock_code      VARCHAR(10) NOT NULL REFERENCES stocks(stock_code),
    stock_name      VARCHAR(64),
    keyword         VARCHAR(32),
    title           TEXT,
    content         TEXT,
    published_at    TEXT,
    source          VARCHAR(64),
    url             TEXT,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_news_data_stock_code ON news_data(stock_code);

-- Latest market snapshot per stock (one row per run)
CREATE TABLE IF NOT EXISTS market_data (
    id                          BIGSERIAL PRIMARY KEY,
    stock_code                  VARCHAR(10) NOT NULL REFERENCES stocks(stock_code),
    stock_name                  VARCHAR(64),
    latest_price                DECIMAL(12, 4),
    pct_change                  DECIMAL(8, 4),
    change_amount               DECIMAL(12, 4),
    open_price                  DECIMAL(12, 4),
    high_price                  DECIMAL(12, 4),
    low_price                   DECIMAL(12, 4),
    prev_close                  DECIMAL(12, 4),
    volume                      DECIMAL(20, 2),
    amount                      DECIMAL(18, 2),
    volume_ratio                DECIMAL(8, 4),
    turnover_rate               DECIMAL(8, 4),
    amplitude                   DECIMAL(6, 2),
    main_net_inflow             DECIMAL(18, 2),
    main_net_inflow_ratio       DECIMAL(8, 4),
    fund_flow_date              DATE,
    benchmark_pct_change        DECIMAL(8, 4),
    relative_strength_vs_index  DECIMAL(8, 4),
    fetched_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_market_data_stock_code ON market_data(stock_code);

-- Final analysis result (replaces news_analysis + market_analysis)
CREATE TABLE IF NOT EXISTS analysis_result (
    id                      BIGSERIAL PRIMARY KEY,
    stock_code              VARCHAR(10) NOT NULL REFERENCES stocks(stock_code),
    stock_name              VARCHAR(64),
    event_types             TEXT,
    text_event_label        VARCHAR(16) DEFAULT '中性',
    text_score              DECIMAL(6, 2),
    sentiment_strength      VARCHAR(8) DEFAULT '未知',
    duration_tag            VARCHAR(8) DEFAULT '未知',
    fact_support            VARCHAR(8) DEFAULT '未知',
    bullish_logic           TEXT,
    bearish_logic           TEXT,
    news_count              INT NOT NULL DEFAULT 0,
    price_volume_signal     VARCHAR(32) DEFAULT '数据不足',
    fund_flow_signal        VARCHAR(16) DEFAULT '资金观望',
    behavior_label          VARCHAR(16) DEFAULT '中性',
    market_score            DECIMAL(6, 2),
    integrated_score        DECIMAL(8, 4),
    decision                TEXT,
    analyzed_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analysis_result_stock_code ON analysis_result(stock_code);
