import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from selenium.common.exceptions import StaleElementReferenceException

from crawler.collect_posts import collect_posts
from db.repo import connect
from nlp.export import export_report
from nlp.predict import predict_new
from run_pipeline import _claim_revisit, _next_processing, _process_one


class Link:
    def __init__(self, href):
        self.href = href

    def get_attribute(self, name):
        return self.href if name == "href" else None


class StaleLink:
    def get_attribute(self, name):
        raise StaleElementReferenceException()


class FeedDriver:
    def __init__(self):
        self.scrolls = 0

    def get(self, url):
        self.url = url

    def find_elements(self, by, selector):
        ids = ["1", "10"] if self.scrolls == 0 else ["1", "10", "11"]
        return [StaleLink()] + [
            Link(f"https://www.facebook.com/groups/g/posts/{post_id}") for post_id in ids
        ]

    def execute_script(self, script):
        self.scrolls += 1


class PipelineTest(unittest.TestCase):
    def test_collect_keeps_scrolling_after_known_post(self):
        conn = connect(":memory:")
        self.addCleanup(conn.close)
        conn.execute("INSERT INTO crawl_queue(post_id, post_url) VALUES ('1', 'known')")
        with patch("crawler.collect_posts.human_sleep", lambda *args: None):
            self.assertEqual(collect_posts(FeedDriver(), conn, "https://facebook/groups/g", 2), 2)
        ids = {row[0] for row in conn.execute("SELECT post_id FROM crawl_queue")}
        self.assertEqual(ids, {"1", "10", "11"})

    def test_existing_database_gets_queue_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "old.db"
            old = sqlite3.connect(path)
            old.execute("""CREATE TABLE crawl_queue (
                post_id TEXT PRIMARY KEY, post_url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER DEFAULT 0,
                last_error TEXT, html_path TEXT, first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                revisit_until TIMESTAMP, crawled_at TIMESTAMP)""")
            old.execute("""INSERT INTO crawl_queue
                (post_id, post_url, status, crawled_at, revisit_until)
                VALUES ('1', 'u', 'done', CURRENT_TIMESTAMP, datetime('now', '+1 day'))""")
            old.commit()
            old.close()

            conn = connect(path)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(crawl_queue)")}
            self.assertTrue({"next_revisit_at", "processed_at", "process_error"} <= columns)
            self.assertIsNotNone(conn.execute(
                "SELECT next_revisit_at FROM crawl_queue WHERE post_id='1'"
            ).fetchone()[0])
            conn.close()

    def test_export_creates_ignored_data_directory(self):
        conn = connect(":memory:")
        self.addCleanup(conn.close)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "data" / "output" / "report.csv"
            self.assertEqual(export_report(conn, {
                "model_version": "v", "related_threshold": 0.5, "negative_threshold": 0.7
            }, output), 0)
            self.assertTrue(output.is_file())

    def test_revisit_claim_and_processing_selection(self):
        conn = connect(":memory:")
        self.addCleanup(conn.close)
        conn.execute("""INSERT INTO crawl_queue
            (post_id, post_url, status, html_path, crawled_at, revisit_until, next_revisit_at)
            VALUES ('1', 'u', 'done', 'one.html', CURRENT_TIMESTAMP,
                    datetime('now', '+1 day'), datetime('now', '-1 minute'))""")
        conn.commit()
        row = _claim_revisit(conn)
        self.assertEqual(row["post_id"], "1")
        self.assertEqual(conn.execute(
            "SELECT status FROM crawl_queue WHERE post_id='1'"
        ).fetchone()[0], "revisiting")
        conn.execute("UPDATE crawl_queue SET status='done' WHERE post_id='1'")
        conn.commit()
        self.assertEqual(_next_processing(conn)["post_id"], "1")

    def test_process_one_marks_exact_crawl_processed(self):
        conn = connect(":memory:")
        self.addCleanup(conn.close)
        conn.execute("""INSERT INTO crawl_queue
            (post_id, post_url, status, html_path, crawled_at)
            VALUES ('1', 'u', 'done', 'one.html', CURRENT_TIMESTAMP)""")
        conn.commit()
        row = _next_processing(conn)
        with patch("run_pipeline.parse_file", return_value=2), \
                patch("run_pipeline.preprocess_post") as preprocess, \
                patch("run_pipeline.predict_new", return_value=3), \
                patch("run_pipeline.export_report"):
            _process_one(conn, {}, object(), row)
        preprocess.assert_called_once_with(conn, "1")
        state = conn.execute(
            "SELECT processed_at=crawled_at, process_error FROM crawl_queue WHERE post_id='1'"
        ).fetchone()
        self.assertEqual(tuple(state), (1, None))

    def test_revisit_replaces_predictions_for_one_post(self):
        conn = connect(":memory:")
        self.addCleanup(conn.close)
        conn.execute("INSERT INTO posts(post_id, caption, text_clean) VALUES ('1', 'p', 'p')")
        conn.execute("""INSERT INTO comments(comment_id, post_id, text, text_clean)
            VALUES ('2', '1', 'c', 'c')""")
        conn.execute("""INSERT INTO predictions
            (target_type, target_id, model_version, p_negative, label)
            VALUES ('post', '1', 'v', 0.1, 'positive')""")
        conn.commit()
        bundle = (None, None, None, None, {"labels": ["NEG", "POS"]})
        with patch("nlp.predict._probs", return_value=[[0.8, 0.2], [0.7, 0.3]]):
            self.assertEqual(predict_new(
                conn, {"model_version": "v"}, bundle=bundle, post_id="1"
            ), 2)
        rows = conn.execute(
            "SELECT target_type, p_negative, label FROM predictions ORDER BY target_type"
        ).fetchall()
        self.assertEqual([(r[0], r[1], r[2]) for r in rows], [
            ("comment", 0.8, "negative"), ("post", 0.7, "negative")
        ])


if __name__ == "__main__":
    unittest.main()
