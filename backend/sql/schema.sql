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

CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region VARCHAR(255) NOT NULL,
    alert_level VARCHAR(20) NOT NULL CHECK (alert_level IN ('elevated', 'high', 'critical')),
    risk_score FLOAT NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    explanation TEXT,
    drivers JSONB,
    actions_taken JSONB,
    acknowledged BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_region ON alerts(region);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_acknowledged ON alerts(acknowledged) WHERE acknowledged = false;

CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel VARCHAR(50) NOT NULL,
    recipient VARCHAR(255) NOT NULL,
    alert_level VARCHAR(20),
    region VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'sent',
    payload JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_region ON notifications(region);
CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications(created_at DESC);

-- ============================================================
-- Multi-tenant tables
-- ============================================================

DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('owner', 'admin', 'member', 'viewer');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    municipality VARCHAR(255) NOT NULL,
    department VARCHAR(255),
    country VARCHAR(100) DEFAULT 'Peru',
    -- Bounding box for spatial filtering
    bbox_min_lat DOUBLE PRECISION NOT NULL,
    bbox_max_lat DOUBLE PRECISION NOT NULL,
    bbox_min_lon DOUBLE PRECISION NOT NULL,
    bbox_max_lon DOUBLE PRECISION NOT NULL,
    -- Map defaults
    map_center_lat DOUBLE PRECISION NOT NULL,
    map_center_lon DOUBLE PRECISION NOT NULL,
    map_zoom INTEGER DEFAULT 10,
    -- Notification config
    teams_webhook_url TEXT,
    teams_enabled BOOLEAN DEFAULT false,
    bluesky_handle VARCHAR(255),
    bluesky_app_password_encrypted TEXT,
    bluesky_enabled BOOLEAN DEFAULT false,
    -- Status
    is_active BOOLEAN DEFAULT true,
    onboarding_completed BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug);
CREATE INDEX IF NOT EXISTS idx_organizations_active ON organizations(is_active) WHERE is_active = true;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entra_oid VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) NOT NULL,
    display_name VARCHAR(255),
    org_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    role user_role DEFAULT 'member',
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_entra_oid ON users(entra_oid);
CREATE INDEX IF NOT EXISTS idx_users_org_id ON users(org_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS emergency_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(255),
    phone VARCHAR(50),
    email VARCHAR(255),
    notify_on_level TEXT[] DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_emergency_contacts_org ON emergency_contacts(org_id);

CREATE TABLE IF NOT EXISTS monitored_zones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    bbox_min_lat DOUBLE PRECISION NOT NULL,
    bbox_max_lat DOUBLE PRECISION NOT NULL,
    bbox_min_lon DOUBLE PRECISION NOT NULL,
    bbox_max_lon DOUBLE PRECISION NOT NULL,
    is_primary BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_monitored_zones_org ON monitored_zones(org_id);

-- Add org_id to existing tables (nullable for backward compatibility)
DO $$ BEGIN
    ALTER TABLE risk_assessments ADD COLUMN org_id UUID REFERENCES organizations(id);
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE alerts ADD COLUMN org_id UUID REFERENCES organizations(id);
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE notifications ADD COLUMN org_id UUID REFERENCES organizations(id);
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE situation_reports ADD COLUMN org_id UUID REFERENCES organizations(id);
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_risk_assessments_org ON risk_assessments(org_id);
CREATE INDEX IF NOT EXISTS idx_alerts_org ON alerts(org_id);
CREATE INDEX IF NOT EXISTS idx_notifications_org ON notifications(org_id);
CREATE INDEX IF NOT EXISTS idx_situation_reports_org ON situation_reports(org_id);
