import os
import uuid
from contextlib import contextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
# root .env（ユーザー管理）→ web/.vercel/.env.pulled（Vercel から pull した BLOB_READ_WRITE_TOKEN 等）
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "web" / ".vercel" / ".env.pulled", override=False)

SCHEMA_PATH = ROOT / "db" / "schema.sql"

_TURSO_URL = os.environ.get("TURSO_DATABASE_URL", "").rstrip("/")
_TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")


def _http_execute(statements: list[dict]) -> list:
    """Turso HTTP pipeline API を呼ぶ。statements は {"q": sql, "params": [...]} のリスト。"""
    url = _TURSO_URL.replace("libsql://", "https://") + "/v2/pipeline"
    payload = {"requests": [{"type": "execute", "stmt": s} for s in statements]}
    payload["requests"].append({"type": "close"})
    resp = httpx.post(
        url,
        json=payload,
        headers={"Authorization": f"Bearer {_TURSO_TOKEN}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["results"]


def _check_result(result: dict, sql: str) -> dict:
    if result.get("type") != "ok":
        raise RuntimeError(f"DB error on `{sql}`: {result}")
    return result


def execute(sql: str, params: list = None) -> dict:
    stmt = {"sql": sql, "args": [{"type": "text", "value": str(p)} if p is not None else {"type": "null"} for p in (params or [])]}
    results = _http_execute([stmt])
    return _check_result(results[0], sql)


def executemany(statements: list[tuple]) -> None:
    stmts = [
        {"sql": sql, "args": [{"type": "text", "value": str(p)} if p is not None else {"type": "null"} for p in (params or [])]}
        for sql, params in statements
    ]
    results = _http_execute(stmts)
    for (sql, _), result in zip(statements, results):
        _check_result(result, sql)


def init_db():
    sql = SCHEMA_PATH.read_text()
    stmts = [(s.strip(), []) for s in sql.split(";") if s.strip()]
    executemany(stmts)
    print(f"DB initialized at {_TURSO_URL}")


def new_id() -> str:
    return str(uuid.uuid4())


def _parse_rows(result: dict) -> list[dict]:
    if result.get("type") != "ok":
        raise RuntimeError(f"DB error: {result}")
    rows_data = result["response"]["result"]["rows"]
    cols = [c["name"] for c in result["response"]["result"]["cols"]]
    return [dict(zip(cols, [cell.get("value") for cell in row])) for row in rows_data]


# --- orgs ---

def insert_org(name: str, university: str = None, instagram: str = None, email: str = None) -> str:
    org_id = new_id()
    execute(
        "INSERT INTO orgs (id, name, university, instagram, email) VALUES (?, ?, ?, ?, ?)",
        [org_id, name, university, instagram, email],
    )
    return org_id


def update_org(org_id: str, **fields):
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    set_clause += ", updated_at = datetime('now')"
    values = list(fields.values())
    execute(f"UPDATE orgs SET {set_clause} WHERE id = ?", [*values, org_id])


def get_org(org_id: str) -> dict | None:
    result = execute("SELECT * FROM orgs WHERE id = ?", [org_id])
    rows = _parse_rows(result)
    return rows[0] if rows else None


def list_orgs(status: str = None) -> list[dict]:
    if status:
        result = execute("SELECT * FROM orgs WHERE status = ? ORDER BY priority DESC", [status])
    else:
        result = execute("SELECT * FROM orgs ORDER BY priority DESC")
    return _parse_rows(result)


# --- proposals ---

def insert_proposal(org_id: str, slug: str, expires_at: str) -> str:
    """Upsert by slug: drop any existing row for this slug, then insert fresh.

    Without this, regeneration silently kept stale MDX in the DB because
    `proposals.slug UNIQUE` rejected the second INSERT and the subsequent UPDATE
    targeted a UUID that was never written.
    """
    proposal_id = new_id()
    existing = execute("SELECT id FROM proposals WHERE slug = ?", [slug])
    rows = _parse_rows(existing)
    if rows:
        old_id = rows[0]["id"]
        execute("UPDATE outreach SET proposal_id = NULL WHERE proposal_id = ?", [old_id])
        execute("DELETE FROM proposals WHERE id = ?", [old_id])
    execute(
        "INSERT INTO proposals (id, org_id, slug, expires_at) VALUES (?, ?, ?, ?)",
        [proposal_id, org_id, slug, expires_at],
    )
    return proposal_id


def update_proposal(proposal_id: str, **fields):
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    execute(f"UPDATE proposals SET {set_clause} WHERE id = ?", [*fields.values(), proposal_id])


def get_proposal_by_slug(slug: str) -> dict | None:
    result = execute("SELECT * FROM proposals WHERE slug = ? AND status = 'active'", [slug])
    rows = _parse_rows(result)
    return rows[0] if rows else None


# --- outreach ---

def insert_outreach(org_id: str, proposal_id: str, channel: str, sent_at: str) -> str:
    outreach_id = new_id()
    execute(
        "INSERT INTO outreach (id, org_id, proposal_id, channel, sent_at) VALUES (?, ?, ?, ?, ?)",
        [outreach_id, org_id, proposal_id, channel, sent_at],
    )
    return outreach_id


def record_response(outreach_id: str, response: str, responded_at: str):
    execute(
        "UPDATE outreach SET response = ?, responded_at = ? WHERE id = ?",
        [response, responded_at, outreach_id],
    )


# --- orders ---

def insert_order(org_id: str, pages: int, has_domain_sub: bool = False, special_plan: bool = False) -> str:
    order_id = new_id()
    price = _calc_price(pages, special_plan)
    execute(
        "INSERT INTO orders (id, org_id, pages, price, has_domain_sub) VALUES (?, ?, ?, ?, ?)",
        [order_id, org_id, pages, price, int(has_domain_sub)],
    )
    return order_id


def _calc_price(pages: int, special_plan: bool = False) -> int:
    if pages <= 0:
        return 0
    if special_plan and pages <= 10:
        return 15000
    price = 4000
    if pages >= 2:
        price += 3000
    if pages >= 3:
        price += 2000 * (pages - 2)
    return price


if __name__ == "__main__":
    init_db()
