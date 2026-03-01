CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id VARCHAR(255) UNIQUE NOT NULL,
    source VARCHAR(50) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    severity INTEGER CHECK (severity BETWEEN 1 AND 5),
    magnitude FLOAT,
    coordinates GEOGRAPHY(POINT, 4326) NOT NULL,
    started_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    raw_data JSONB,
    is_active BOOLEAN DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_events_coordinates ON events USING GIST(coordinates);
CREATE INDEX IF NOT EXISTS idx_events_external_id ON events(external_id);
CREATE INDEX IF NOT EXISTS idx_events_source ON events(source);
CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_is_active ON events(is_active) WHERE is_active = true;

CREATE TABLE IF NOT EXISTS situation_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region VARCHAR(255) NOT NULL,
    severity INTEGER CHECK (severity BETWEEN 1 AND 5),
    content TEXT NOT NULL,
    event_ids UUID[],
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS news_articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_url VARCHAR(1024) UNIQUE NOT NULL,
    source VARCHAR(100) NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    coordinates GEOGRAPHY(POINT, 4326),
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_news_coordinates ON news_articles USING GIST(coordinates);
CREATE INDEX IF NOT EXISTS idx_news_published_at ON news_articles(published_at DESC);

CREATE TABLE IF NOT EXISTS risk_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region VARCHAR(255) NOT NULL,
    risk_score FLOAT NOT NULL CHECK (risk_score BETWEEN 1.0 AND 5.0),
    risk_level VARCHAR(20) NOT NULL,
    components JSONB NOT NULL,
    explanation TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_region ON risk_assessments(region);
CREATE INDEX IF NOT EXISTS idx_risk_created_at ON risk_assessments(created_at DESC);
