import sqlite3
from pathlib import Path

SCHEMA = Path(__file__).with_name("schema.sql")


def connect(path):
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    columns = {row[1] for row in conn.execute("PRAGMA table_info(crawl_queue)")}
    for name, declaration in {
        "next_revisit_at": "TIMESTAMP",
        "processed_at": "TIMESTAMP",
        "process_error": "TEXT",
    }.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE crawl_queue ADD COLUMN {name} {declaration}")
    conn.execute("""UPDATE crawl_queue SET next_revisit_at=COALESCE(crawled_at, CURRENT_TIMESTAMP)
        WHERE status='done' AND next_revisit_at IS NULL""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_crawl_revisit ON crawl_queue(status, next_revisit_at)")
    conn.commit()
    return conn


def upsert_author(conn, a):
    conn.execute("""INSERT INTO authors (author_id, name, profile_url)
        VALUES (:author_id, :name, :profile_url)
        ON CONFLICT(author_id) DO UPDATE SET name = excluded.name,
            profile_url = excluded.profile_url""", a)


def upsert_post(conn, p):
    conn.execute("""INSERT INTO posts (post_id, author_id, title, caption, time_text, post_url)
        VALUES (:post_id, :author_id, :title, :caption, :time_text, :post_url)
        ON CONFLICT(post_id) DO UPDATE SET author_id = excluded.author_id, title = excluded.title,
            caption = excluded.caption, time_text = excluded.time_text,
            post_url = excluded.post_url, text_clean = NULL""", p)


def upsert_comment(conn, c):
    conn.execute("""INSERT INTO comments (comment_id, post_id, parent_comment_id, author_id, text, time_text)
        VALUES (:comment_id, :post_id, :parent_comment_id, :author_id, :text, :time_text)
        ON CONFLICT(comment_id) DO UPDATE SET post_id = excluded.post_id,
            parent_comment_id = excluded.parent_comment_id, author_id = excluded.author_id,
            text = excluded.text, time_text = excluded.time_text, text_clean = NULL""", c)
