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

    annual_return   NUMERIC(18, 4),
    max_drawdown    NUMERIC(18, 4),
    sharpe          NUMERIC(18, 4),
    win_rate        NUMERIC(18, 4),

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

COMMIT;
