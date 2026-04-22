import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "arvex.db"
SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA_PATH.read_text())


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def new_id() -> str:
    return str(uuid.uuid4())


# --- orgs ---

def insert_org(name: str, university: str = None, instagram: str = None, email: str = None) -> str:
    org_id = new_id()
    with connect() as conn:
        conn.execute(
            "INSERT INTO orgs (id, name, university, instagram, email) VALUES (?, ?, ?, ?, ?)",
            (org_id, name, university, instagram, email),
        )
    return org_id


def update_org(org_id: str, **fields):
    if not fields:
        return
    fields["updated_at"] = "datetime('now')"
    set_clause = ", ".join(f"{k} = ?" for k in fields if k != "updated_at")
    set_clause += ", updated_at = datetime('now')"
    values = [v for k, v in fields.items() if k != "updated_at"]
    with connect() as conn:
        conn.execute(f"UPDATE orgs SET {set_clause} WHERE id = ?", (*values, org_id))


def get_org(org_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM orgs WHERE id = ?", (org_id,)).fetchone()
        return dict(row) if row else None


def list_orgs(status: str = None) -> list[dict]:
    with connect() as conn:
        if status:
            rows = conn.execute("SELECT * FROM orgs WHERE status = ? ORDER BY priority DESC", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM orgs ORDER BY priority DESC").fetchall()
        return [dict(r) for r in rows]


# --- proposals ---

def insert_proposal(org_id: str, slug: str, expires_at: str) -> str:
    proposal_id = new_id()
    with connect() as conn:
        conn.execute(
            "INSERT INTO proposals (id, org_id, slug, expires_at) VALUES (?, ?, ?, ?)",
            (proposal_id, org_id, slug, expires_at),
        )
    return proposal_id


def update_proposal(proposal_id: str, **fields):
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    with connect() as conn:
        conn.execute(f"UPDATE proposals SET {set_clause} WHERE id = ?", (*fields.values(), proposal_id))


# --- outreach ---

def insert_outreach(org_id: str, proposal_id: str, channel: str, sent_at: str) -> str:
    outreach_id = new_id()
    with connect() as conn:
        conn.execute(
            "INSERT INTO outreach (id, org_id, proposal_id, channel, sent_at) VALUES (?, ?, ?, ?, ?)",
            (outreach_id, org_id, proposal_id, channel, sent_at),
        )
    return outreach_id


def record_response(outreach_id: str, response: str, responded_at: str):
    with connect() as conn:
        conn.execute(
            "UPDATE outreach SET response = ?, responded_at = ? WHERE id = ?",
            (response, responded_at, outreach_id),
        )


# --- orders ---

def insert_order(org_id: str, pages: int, has_domain_sub: bool = False, special_plan: bool = False) -> str:
    order_id = new_id()
    price = _calc_price(pages, special_plan)
    with connect() as conn:
        conn.execute(
            "INSERT INTO orders (id, org_id, pages, price, has_domain_sub) VALUES (?, ?, ?, ?, ?)",
            (order_id, org_id, pages, price, int(has_domain_sub)),
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
    print(f"DB initialized at {DB_PATH}")
