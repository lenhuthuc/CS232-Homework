CREATE TABLE IF NOT EXISTS authors (
    author_id TEXT PRIMARY KEY, name TEXT NOT NULL, profile_url TEXT);
CREATE TABLE IF NOT EXISTS crawl_queue (
    post_id TEXT PRIMARY KEY, post_url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',          -- pending | crawling | revisiting | done | failed
    attempts INTEGER DEFAULT 0, last_error TEXT, html_path TEXT,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revisit_until TIMESTAMP, next_revisit_at TIMESTAMP, crawled_at TIMESTAMP,
    processed_at TIMESTAMP, process_error TEXT);
CREATE TABLE IF NOT EXISTS posts (
    post_id TEXT PRIMARY KEY, author_id TEXT REFERENCES authors(author_id),
    title TEXT, caption TEXT, time_text TEXT, post_url TEXT,
    text_clean TEXT, crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS comments (
    comment_id TEXT PRIMARY KEY, post_id TEXT NOT NULL REFERENCES posts(post_id),
    parent_comment_id TEXT, author_id TEXT REFERENCES authors(author_id),
    text TEXT, text_clean TEXT, time_text TEXT,
    crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, target_type TEXT NOT NULL, target_id TEXT NOT NULL,
    model_version TEXT NOT NULL, related_score REAL,
    p_negative REAL, p_neutral REAL, p_positive REAL, label TEXT,
    predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (target_type, target_id, model_version));
CREATE TABLE IF NOT EXISTS manual_labels (
    target_type TEXT NOT NULL, target_id TEXT NOT NULL,
    related_to_uit INTEGER, sentiment TEXT, labeler TEXT,
    PRIMARY KEY (target_type, target_id));
CREATE TABLE IF NOT EXISTS crawl_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TIMESTAMP, finished_at TIMESTAMP,
    new_posts INTEGER, new_comments INTEGER, status TEXT, error TEXT);
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id);
CREATE INDEX IF NOT EXISTS idx_pred_label ON predictions(model_version, label);
