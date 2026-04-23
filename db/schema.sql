CREATE TABLE IF NOT EXISTS orgs (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    university     TEXT,
    category       TEXT,              -- '集客型' | '信用型' | null
    instagram      TEXT,
    email          TEXT,
    bio_summary    TEXT,
    pain_points    TEXT,
    source_assets  TEXT,              -- JSON: [{type, url, caption, posted_at}]
    source_text    TEXT,              -- JSON: [{type, url, content}] — 生テキスト素材
    published_content TEXT,           -- JSON: {external_links, articles} — link_explorer の成果物
    notable_facts  TEXT,              -- JSON: {names, dates, events, orgs, places, quotes} — 素材から regex 抽出した固有情報
    priority       INTEGER DEFAULT 0,
    status         TEXT DEFAULT 'discovered',
    -- discovered → analyzed → proposal_sent → negotiating → won | lost | expired
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS proposals (
    id            TEXT PRIMARY KEY,
    org_id        TEXT NOT NULL REFERENCES orgs(id),
    slug          TEXT UNIQUE NOT NULL,
    vercel_url    TEXT,
    form_url      TEXT,
    design_brief  TEXT,                   -- JSON: DesignBrief
    images        TEXT,                   -- JSON: [{role, url, prompt, aspect_ratio, alt}]
    html          TEXT,                   -- 完全な HTML 文字列（<!DOCTYPE html>...</html>）
    status        TEXT DEFAULT 'active',  -- active | deleted
    expires_at    TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS outreach (
    id           TEXT PRIMARY KEY,
    org_id       TEXT NOT NULL REFERENCES orgs(id),
    proposal_id  TEXT REFERENCES proposals(id),
    channel      TEXT NOT NULL,          -- 'instagram' | 'email' | 'form'
    sent_at      TEXT,
    response     TEXT,                   -- null | 'no_reply' | 'interested' | 'rejected' | 'requirements'
    responded_at TEXT
);

CREATE TABLE IF NOT EXISTS orders (
    id              TEXT PRIMARY KEY,
    org_id          TEXT NOT NULL REFERENCES orgs(id),
    pages           INTEGER NOT NULL,
    price           INTEGER NOT NULL,
    has_domain_sub  INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'in_progress',  -- in_progress | delivered
    delivered_at    TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
