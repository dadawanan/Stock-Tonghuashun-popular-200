BEGIN;

-- =========================================================
-- Stock Analysis Platform - PostgreSQL Formal Schema v2
-- Designed for:
-- 1. stock master data
-- 2. THS popularity ranking snapshots
-- 3. raw news ingestion
-- 4. market snapshots
-- 5. per-article LLM/rule analysis
-- 6. per-stock final analysis snapshots
-- 7. pipeline run audit trail
-- =========================================================

-- ---------------------------------------------------------
-- 0. Pipeline run audit
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS pipeline_run (
    id                  BIGSERIAL PRIMARY KEY,
    run_type            VARCHAR(32) NOT NULL,
    source              VARCHAR(32),
    trade_date          DATE,
    snapshot_time       TIMESTAMPTZ,
    stock_count         INT NOT NULL DEFAULT 0,
    news_count          INT NOT NULL DEFAULT 0,
    market_count        INT NOT NULL DEFAULT 0,
    analysis_count      INT NOT NULL DEFAULT 0,
    status              VARCHAR(16) NOT NULL DEFAULT 'running',
    error_message       TEXT,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_pipeline_run_type
        CHECK (run_type IN ('fetch', 'analyze', 'run_all', 'backfill', 'manual')),
    CONSTRAINT chk_pipeline_status
        CHECK (status IN ('running', 'success', 'failed', 'partial'))
);

CREATE INDEX IF NOT EXISTS idx_pipeline_run_trade_date
    ON pipeline_run (trade_date);

CREATE INDEX IF NOT EXISTS idx_pipeline_run_status_started
    ON pipeline_run (status, started_at DESC);


-- ---------------------------------------------------------
-- 1. Stock master
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_master (
    stock_code          VARCHAR(10) PRIMARY KEY,
    stock_name          VARCHAR(64) NOT NULL,
    market              VARCHAR(8) NOT NULL,
    market_code         VARCHAR(16),
    code_digits         VARCHAR(6),
    industry_name       VARCHAR(128),
    concept_tags        TEXT[],
    is_st               BOOLEAN NOT NULL DEFAULT FALSE,
    listed_date         DATE,
    status              VARCHAR(16) NOT NULL DEFAULT 'active',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_stock_market
        CHECK (market IN ('SH', 'SZ', 'BJ')),
    CONSTRAINT chk_stock_status
        CHECK (status IN ('active', 'delisted', 'suspended'))
);

CREATE INDEX IF NOT EXISTS idx_stock_master_market
    ON stock_master (market, stock_code);

CREATE INDEX IF NOT EXISTS idx_stock_master_name
    ON stock_master (stock_name);


-- ---------------------------------------------------------
-- 2. Popularity ranking snapshots
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS popularity_snapshot (
    id                  BIGSERIAL PRIMARY KEY,
    run_id              BIGINT REFERENCES pipeline_run(id) ON DELETE SET NULL,
    trade_date          DATE NOT NULL,
    snapshot_time       TIMESTAMPTZ NOT NULL,
    source              VARCHAR(32) NOT NULL DEFAULT 'ths_pywencai',
    stock_code          VARCHAR(10) NOT NULL REFERENCES stock_master(stock_code) ON DELETE CASCADE,
    stock_name          VARCHAR(64) NOT NULL,
    popularity_rank     INT NOT NULL,
    popularity_score    NUMERIC(18, 4),
    latest_price        NUMERIC(12, 4),
    latest_pct_change   NUMERIC(10, 4),
    is_new_entry        BOOLEAN NOT NULL DEFAULT FALSE,
    previous_rank       INT,
    rank_change         INT,
    raw_payload         JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_popularity_snapshot
        UNIQUE (trade_date, snapshot_time, stock_code, source)
);

CREATE INDEX IF NOT EXISTS idx_popularity_snapshot_trade_rank
    ON popularity_snapshot (trade_date, popularity_rank);

CREATE INDEX IF NOT EXISTS idx_popularity_snapshot_stock_time
    ON popularity_snapshot (stock_code, snapshot_time DESC);

CREATE INDEX IF NOT EXISTS idx_popularity_snapshot_new_entry
    ON popularity_snapshot (trade_date, is_new_entry);


-- ---------------------------------------------------------
-- 3. Raw news articles
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS news_article (
    id                  BIGSERIAL PRIMARY KEY,
    run_id              BIGINT REFERENCES pipeline_run(id) ON DELETE SET NULL,
    stock_code          VARCHAR(10) NOT NULL REFERENCES stock_master(stock_code) ON DELETE CASCADE,
    stock_name          VARCHAR(64),
    source              VARCHAR(64),
    keyword             VARCHAR(64),
    title               TEXT NOT NULL,
    content             TEXT,
    summary             TEXT,
    url                 TEXT,
    published_at        TIMESTAMPTZ,
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload         JSONB,
    content_hash        VARCHAR(64),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_news_article_stock_url
    ON news_article (stock_code, url)
    WHERE url IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_news_article_hash
    ON news_article (stock_code, content_hash)
    WHERE content_hash IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_news_article_stock_published
    ON news_article (stock_code, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_news_article_fetched_at
    ON news_article (fetched_at DESC);


-- ---------------------------------------------------------
-- 4. Market snapshots
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_snapshot (
    id                          BIGSERIAL PRIMARY KEY,
    run_id                      BIGINT REFERENCES pipeline_run(id) ON DELETE SET NULL,
    stock_code                  VARCHAR(10) NOT NULL REFERENCES stock_master(stock_code) ON DELETE CASCADE,
    stock_name                  VARCHAR(64),
    trade_date                  DATE,
    snapshot_time               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source                      VARCHAR(32) NOT NULL DEFAULT 'eastmoney',
    latest_price                NUMERIC(12, 4),
    pct_change                  NUMERIC(10, 4),
    change_amount               NUMERIC(12, 4),
    open_price                  NUMERIC(12, 4),
    high_price                  NUMERIC(12, 4),
    low_price                   NUMERIC(12, 4),
    prev_close                  NUMERIC(12, 4),
    volume                      NUMERIC(20, 2),
    amount                      NUMERIC(20, 2),
    volume_ratio                NUMERIC(10, 4),
    turnover_rate               NUMERIC(10, 4),
    amplitude                   NUMERIC(10, 4),
    main_net_inflow             NUMERIC(20, 2),
    main_net_inflow_ratio       NUMERIC(10, 4),
    fund_flow_date              DATE,
    benchmark_code              VARCHAR(16),
    benchmark_name              VARCHAR(32),
    benchmark_pct_change        NUMERIC(10, 4),
    relative_strength_vs_index  NUMERIC(10, 4),
    source_latest_price         NUMERIC(12, 4),
    source_pct_change           NUMERIC(10, 4),
    raw_payload                 JSONB,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_market_snapshot_stock_time
    ON market_snapshot (stock_code, snapshot_time DESC);

CREATE INDEX IF NOT EXISTS idx_market_snapshot_trade_date
    ON market_snapshot (trade_date, stock_code);

CREATE INDEX IF NOT EXISTS idx_market_snapshot_fund_flow_date
    ON market_snapshot (fund_flow_date, stock_code);


-- ---------------------------------------------------------
-- 5. Per-article analysis
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS news_analysis (
    id                  BIGSERIAL PRIMARY KEY,
    run_id              BIGINT REFERENCES pipeline_run(id) ON DELETE SET NULL,
    article_id          BIGINT NOT NULL REFERENCES news_article(id) ON DELETE CASCADE,
    stock_code          VARCHAR(10) NOT NULL REFERENCES stock_master(stock_code) ON DELETE CASCADE,
    analyzer_type       VARCHAR(16) NOT NULL DEFAULT 'rule',
    model_name          VARCHAR(64),
    model_version       VARCHAR(64),
    prompt_version      VARCHAR(64),
    event_type          VARCHAR(64),
    event_label         VARCHAR(16) NOT NULL DEFAULT '中性',
    event_score         NUMERIC(10, 4),
    sentiment_score     NUMERIC(10, 4),
    sentiment_strength  VARCHAR(16),
    duration_tag        VARCHAR(16),
    fact_support        VARCHAR(16),
    impact_scope        VARCHAR(32),
    impact_direction    VARCHAR(16),
    impact_path         TEXT,
    bullish_logic       TEXT,
    bearish_logic       TEXT,
    extracted_entities  JSONB,
    analysis_json       JSONB,
    analyzed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_news_analysis_type
        CHECK (analyzer_type IN ('rule', 'llm', 'hybrid'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_news_analysis_article_analyzer
    ON news_analysis (article_id, analyzer_type, COALESCE(model_name, ''), COALESCE(prompt_version, ''));

CREATE INDEX IF NOT EXISTS idx_news_analysis_stock_time
    ON news_analysis (stock_code, analyzed_at DESC);

CREATE INDEX IF NOT EXISTS idx_news_analysis_event_type
    ON news_analysis (event_type, event_label);


-- ---------------------------------------------------------
-- 6. Final per-stock analysis snapshot
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_analysis_snapshot (
    id                      BIGSERIAL PRIMARY KEY,
    run_id                  BIGINT REFERENCES pipeline_run(id) ON DELETE SET NULL,
    stock_code              VARCHAR(10) NOT NULL REFERENCES stock_master(stock_code) ON DELETE CASCADE,
    stock_name              VARCHAR(64),
    trade_date              DATE,
    snapshot_time           TIMESTAMPTZ,
    event_types             TEXT,
    text_event_label        VARCHAR(16) NOT NULL DEFAULT '中性',
    text_score              NUMERIC(10, 4),
    sentiment_strength      VARCHAR(16),
    duration_tag            VARCHAR(16),
    fact_support            VARCHAR(16),
    bullish_logic           TEXT,
    bearish_logic           TEXT,
    news_count              INT NOT NULL DEFAULT 0,
    price_volume_signal     VARCHAR(32) NOT NULL DEFAULT '数据不足',
    fund_flow_signal        VARCHAR(32) NOT NULL DEFAULT '资金观望',
    behavior_label          VARCHAR(32) NOT NULL DEFAULT '中性',
    market_score            NUMERIC(10, 4),
    integrated_score        NUMERIC(10, 4),
    decision                TEXT,
    reasoning_json          JSONB,
    analyzed_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_stock_analysis_snapshot_run_stock
    ON stock_analysis_snapshot (run_id, stock_code)
    WHERE run_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_stock_analysis_snapshot_score
    ON stock_analysis_snapshot (integrated_score DESC);

CREATE INDEX IF NOT EXISTS idx_stock_analysis_snapshot_stock_time
    ON stock_analysis_snapshot (stock_code, analyzed_at DESC);

CREATE INDEX IF NOT EXISTS idx_stock_analysis_snapshot_trade_date
    ON stock_analysis_snapshot (trade_date, stock_code);


-- ---------------------------------------------------------
-- 7. Optional helper views
-- ---------------------------------------------------------
CREATE OR REPLACE VIEW v_latest_market_snapshot AS
SELECT DISTINCT ON (stock_code)
    id,
    stock_code,
    stock_name,
    trade_date,
    snapshot_time,
    latest_price,
    pct_change,
    main_net_inflow,
    main_net_inflow_ratio,
    benchmark_pct_change,
    relative_strength_vs_index
FROM market_snapshot
ORDER BY stock_code, snapshot_time DESC, id DESC;

CREATE OR REPLACE VIEW v_latest_stock_analysis AS
SELECT DISTINCT ON (stock_code)
    id,
    run_id,
    stock_code,
    stock_name,
    trade_date,
    snapshot_time,
    text_event_label,
    text_score,
    market_score,
    integrated_score,
    decision,
    analyzed_at
FROM stock_analysis_snapshot
ORDER BY stock_code, analyzed_at DESC, id DESC;

-- ---------------------------------------------------------
-- 8. User authentication
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              BIGSERIAL PRIMARY KEY,
    username        VARCHAR(64) NOT NULL UNIQUE,
    password_hash   VARCHAR(128) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      VARCHAR(128) NOT NULL UNIQUE,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);

COMMIT;
