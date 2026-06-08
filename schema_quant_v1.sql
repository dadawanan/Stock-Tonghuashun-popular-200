-- =========================================================
-- 量化系统初版表结构（PostgreSQL）
-- 与 schema_v2.sql 并列；执行顺序：可先执行 schema_v2，再执行本文件
-- =========================================================

BEGIN;

-- ------------------------------------------------------------
-- A. 基础信息（独立于 stock_master 也可用 code 关联）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_basic (
    id          BIGSERIAL PRIMARY KEY,
    code        VARCHAR(16) NOT NULL UNIQUE,
    name        VARCHAR(64),
    market      VARCHAR(16),
    industry    VARCHAR(64),
    list_date   DATE,
    status      VARCHAR(16),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stock_basic_market ON stock_basic (market);

COMMENT ON TABLE stock_basic IS '量化侧股票基础静态信息（可按 code 与 stock_master.stock_code 对齐）';


-- ------------------------------------------------------------
-- B. 日行情
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_daily (
    id          BIGSERIAL PRIMARY KEY,
    code        VARCHAR(16) NOT NULL,
    trade_date  DATE NOT NULL,

    open        NUMERIC(18, 4),
    high        NUMERIC(18, 4),
    low         NUMERIC(18, 4),
    close       NUMERIC(18, 4),

    volume      BIGINT,
    amount      BIGINT,

    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_stock_daily_code_date UNIQUE (code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_stock_daily_code_date ON stock_daily (code, trade_date);

COMMENT ON TABLE stock_daily IS '日 K 线与成交量额';


-- ------------------------------------------------------------
-- C. 技术指标
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_indicator (
    id          BIGSERIAL PRIMARY KEY,
    code        VARCHAR(16) NOT NULL,
    trade_date  DATE NOT NULL,

    ma5         NUMERIC(18, 4),
    ma20        NUMERIC(18, 4),

    rsi         NUMERIC(18, 4),

    macd        NUMERIC(18, 4),

    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_stock_indicator_code_date UNIQUE (code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_stock_indicator_code_date ON stock_indicator (code, trade_date);


-- ------------------------------------------------------------
-- D. 策略选股结果（strategy_id 可后续 FK 到策略定义表）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategy_pick (
    id            BIGSERIAL PRIMARY KEY,
    strategy_id   BIGINT NOT NULL,
    trade_date    DATE NOT NULL,
    code          VARCHAR(16) NOT NULL,
    score         NUMERIC(18, 4),
    reason        TEXT,

    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_pick_strategy_date
    ON strategy_pick (strategy_id, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_strategy_pick_code ON strategy_pick (code);


-- ------------------------------------------------------------
-- E. 回测概要
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backtest_result (
    id              BIGSERIAL PRIMARY KEY,
    strategy_id     BIGINT NOT NULL,

    start_date      DATE,
    end_date        DATE,

    total_return    NUMERIC(18, 6),
    annual_return   NUMERIC(18, 4),
    max_drawdown    NUMERIC(18, 4),
    max_drawdown_days INTEGER,
    sharpe          NUMERIC(18, 4),
    sortino         NUMERIC(18, 4),
    calmar          NUMERIC(18, 4),
    alpha           NUMERIC(18, 4),
    beta            NUMERIC(18, 4),
    information_ratio NUMERIC(18, 4),
    win_rate        NUMERIC(18, 4),
    total_trades    INTEGER,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_backtest_result_strategy ON backtest_result (strategy_id, created_at DESC);


-- ------------------------------------------------------------
-- F. 仿真/实盘订单与持仓（account_id 由业务侧含义约定）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trade_order (
    id          BIGSERIAL PRIMARY KEY,
    account_id  BIGINT NOT NULL,
    code        VARCHAR(16) NOT NULL,
    side        VARCHAR(8) NOT NULL,
    price       NUMERIC(18, 4),
    quantity    INTEGER,
    status      VARCHAR(16),

    -- side: 建议取值 buy / sell，由应用层校验
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trade_order_account_time ON trade_order (account_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trade_order_code ON trade_order (code);


CREATE TABLE IF NOT EXISTS position_account (
    id          BIGSERIAL PRIMARY KEY,
    account_id  BIGINT NOT NULL,
    code        VARCHAR(16) NOT NULL,
    quantity    INTEGER,
    avg_price   NUMERIC(18, 4),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_position_account UNIQUE (account_id, code)
);

CREATE INDEX IF NOT EXISTS idx_position_account_id ON position_account (account_id);

COMMENT ON TABLE position_account IS '账户持仓快照（表名避开 PostgreSQL 保留字 position）';


-- ------------------------------------------------------------
-- G. 策略定义
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategy (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(64) NOT NULL,
    type        VARCHAR(32) NOT NULL,
    params      JSONB,
    description TEXT,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE strategy IS '量化策略定义（popularity/sentiment/technical/multi_factor）';

-- ------------------------------------------------------------
-- H. 回测交易明细
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backtest_trade (
    id              BIGSERIAL PRIMARY KEY,
    backtest_id     BIGINT NOT NULL REFERENCES backtest_result(id),
    code            VARCHAR(16) NOT NULL,
    side            VARCHAR(8) NOT NULL,
    price           NUMERIC(18, 4),
    quantity        INTEGER,
    trade_date      DATE NOT NULL,
    pnl             NUMERIC(18, 4),
    signal_source   VARCHAR(32),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_backtest_trade_backtest ON backtest_trade (backtest_id, trade_date);

-- ------------------------------------------------------------
-- I. 回测每日净值
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backtest_daily_nav (
    id              BIGSERIAL PRIMARY KEY,
    backtest_id     BIGINT NOT NULL REFERENCES backtest_result(id),
    trade_date      DATE NOT NULL,
    nav             NUMERIC(18, 6),
    total_assets    NUMERIC(18, 2),
    cash            NUMERIC(18, 2),
    position_value  NUMERIC(18, 2),
    benchmark_nav   NUMERIC(18, 6),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_backtest_daily_nav UNIQUE (backtest_id, trade_date)
);

-- ------------------------------------------------------------
-- J. 模拟账户
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sim_account (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id),
    account_name    VARCHAR(64) NOT NULL,
    initial_capital NUMERIC(18, 2) NOT NULL DEFAULT 1000000.00,
    current_capital NUMERIC(18, 2) NOT NULL,
    total_assets    NUMERIC(18, 2) NOT NULL,
    status          VARCHAR(16) DEFAULT 'active',
    strategy_id     BIGINT REFERENCES strategy(id),
    config          JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sim_account_user ON sim_account (user_id);

-- ------------------------------------------------------------
-- K. 持仓每日快照
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS position_daily_snapshot (
    id                  BIGSERIAL PRIMARY KEY,
    account_id          BIGINT NOT NULL,
    code                VARCHAR(16) NOT NULL,
    trade_date          DATE NOT NULL,
    quantity            INTEGER,
    available_quantity  INTEGER,
    avg_price           NUMERIC(18, 4),
    close_price         NUMERIC(18, 4),
    market_value        NUMERIC(18, 2),
    pnl                 NUMERIC(18, 2),
    pnl_pct             NUMERIC(18, 4),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_position_snapshot UNIQUE (account_id, code, trade_date)
);

-- ------------------------------------------------------------
-- L. 反馈日志
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedback_log (
    id              BIGSERIAL PRIMARY KEY,
    backtest_id     BIGINT NOT NULL REFERENCES backtest_result(id),
    strategy_id     BIGINT NOT NULL REFERENCES strategy(id),
    feedback_type   VARCHAR(32) NOT NULL,
    before_params   JSONB,
    after_params    JSONB,
    reason          TEXT,
    status          VARCHAR(16) DEFAULT 'pending',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- M. 挂单表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pending_order (
    id              BIGSERIAL PRIMARY KEY,
    account_id      BIGINT NOT NULL REFERENCES sim_account(id),
    code            VARCHAR(16) NOT NULL,
    side            VARCHAR(8) NOT NULL,   -- buy/sell
    target_price    NUMERIC(18, 4) NOT NULL,
    quantity        INTEGER NOT NULL,
    status          VARCHAR(16) DEFAULT 'pending',  -- pending/filled/cancelled/expired
    note            TEXT,
    filled_at       TIMESTAMPTZ,
    filled_price    NUMERIC(18, 4),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pending_order_account ON pending_order (account_id, status);
CREATE INDEX IF NOT EXISTS idx_pending_order_status ON pending_order (status);

COMMENT ON TABLE pending_order IS '挂单表（限价单）';

-- ------------------------------------------------------------
-- 扩展现有表
-- ------------------------------------------------------------
ALTER TABLE trade_order ADD COLUMN IF NOT EXISTS strategy_id BIGINT;
ALTER TABLE trade_order ADD COLUMN IF NOT EXISTS trade_at TIMESTAMPTZ;
ALTER TABLE trade_order ADD COLUMN IF NOT EXISTS commission NUMERIC(18, 4) DEFAULT 0;
ALTER TABLE trade_order ADD COLUMN IF NOT EXISTS slippage NUMERIC(18, 4) DEFAULT 0;

ALTER TABLE position_account ADD COLUMN IF NOT EXISTS available_quantity INTEGER;

COMMIT;
