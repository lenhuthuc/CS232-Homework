"""Continuous pipeline: new posts + revisits -> per-post processing."""
import argparse
import asyncio
import queue
import sys
import threading
from datetime import datetime

import yaml
from filelock import FileLock, Timeout

from crawler.browser import is_checkpoint, make_driver
from crawler.collect_posts import collect_posts
from crawler.expand_post import Checkpoint, crawl_post
from crawler.utils import human_sleep
from db.repo import connect
from nlp.export import export_report
from nlp.predict import load_bundle, predict_new
from nlp.preprocess import preprocess_db, preprocess_post
from parser.parse_html import parse_all, parse_file

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LOGIN_LOCK = threading.Lock()


def count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _driver(cfg, profile):
    driver = make_driver(profile, cfg["headless"])
    driver.get("https://www.facebook.com/me")
    if not is_checkpoint(driver):
        driver.get(cfg["group_url"])
        return driver
    if cfg["headless"]:
        driver.quit()
        raise Checkpoint(f"Facebook yêu cầu đăng nhập cho profile {profile}.")
    with LOGIN_LOCK:
        input(f"Hãy đăng nhập Facebook trong cửa sổ profile {profile}, xong nhấn Enter...")
    driver.get("https://www.facebook.com/me")
    if is_checkpoint(driver):
        driver.quit()
        raise Checkpoint(f"Chưa đăng nhập Facebook thành công cho profile {profile}.")
    driver.get(cfg["group_url"])
    return driver


def _claim(conn, sql, status):
    row = conn.execute(sql).fetchone()
    if row is None:
        return None
    changed = conn.execute(
        "UPDATE crawl_queue SET status=? WHERE post_id=? AND status=?",
        (status, row["post_id"], row["status"]),
    ).rowcount
    conn.commit()
    return row if changed else None


def _claim_new(conn):
    return _claim(conn, """SELECT post_id, post_url, status FROM crawl_queue
        WHERE status IN ('pending','failed') AND attempts < 3
        ORDER BY first_seen_at LIMIT 1""", "crawling")


def _claim_revisit(conn):
    return _claim(conn, """SELECT post_id, post_url, status FROM crawl_queue
        WHERE status='done' AND next_revisit_at <= CURRENT_TIMESTAMP
          AND revisit_until > CURRENT_TIMESTAMP
        ORDER BY next_revisit_at LIMIT 1""", "revisiting")


def _crawl_one(driver, conn, cfg, row, failure_status):
    return crawl_post(
        driver, conn, row["post_id"], row["post_url"], cfg["raw_html_dir"],
        cfg["revisit_days"], cfg["revisit_interval_minutes"], failure_status,
    )


def _notify(ready, stop, post_id):
    while not stop.is_set():
        try:
            ready.put(post_id, timeout=1)
            return
        except queue.Full:
            continue


def new_worker(cfg, ready, stop, once=False):
    conn = connect(cfg["db_path"])
    driver = None
    try:
        driver = _driver(cfg, cfg["user_data_dir"])
        while not stop.is_set():
            found = collect_posts(driver, conn, cfg["group_url"], cfg["max_new_posts"])
            print(f"[new] tìm thấy {found} bài mới")
            crawled = 0
            while not stop.is_set() and (row := _claim_new(conn)) is not None:
                print(f"[new] {row['post_url']}")
                if _crawl_one(driver, conn, cfg, row, "failed"):
                    _notify(ready, stop, row["post_id"])
                crawled += 1
                human_sleep(5, 15)
                if crawled % 20 == 0:
                    human_sleep(120, 300)
            if once:
                return
            if not found:
                human_sleep(30, 90)
    finally:
        if driver:
            driver.quit()
        conn.close()


def revisit_worker(cfg, ready, stop, once=False):
    conn = connect(cfg["db_path"])
    driver = None
    try:
        while not stop.is_set():
            row = _claim_revisit(conn)
            if row is None:
                if once:
                    return
                human_sleep(60, 180)
                continue
            if driver is None:
                driver = _driver(cfg, cfg["revisit_user_data_dir"])
            print(f"[revisit] {row['post_url']}")
            if _crawl_one(driver, conn, cfg, row, "done"):
                _notify(ready, stop, row["post_id"])
            human_sleep(5, 15)
    finally:
        if driver:
            driver.quit()
        conn.close()


def _next_processing(conn, post_id=None):
    where = "AND post_id=?" if post_id else ""
    params = (post_id,) if post_id else ()
    return conn.execute(f"""SELECT post_id, post_url, html_path FROM crawl_queue
        WHERE status='done' AND html_path IS NOT NULL
          AND (processed_at IS NULL OR processed_at < crawled_at) {where}
        ORDER BY crawled_at LIMIT 1""", params).fetchone()


def _process_one(conn, cfg, bundle, row):
    post_id = row["post_id"]
    try:
        comments = parse_file(conn, row["html_path"], post_id, row["post_url"])
        preprocess_post(conn, post_id)
        predicted = predict_new(conn, cfg, bundle=bundle, post_id=post_id)
        conn.execute("""UPDATE crawl_queue SET processed_at=crawled_at, process_error=NULL
            WHERE post_id=?""", (post_id,))
        conn.commit()
        export_report(conn, cfg)
        print(f"[process] {post_id}: {comments} comment, {predicted} dự đoán")
    except Exception as error:
        conn.rollback()
        conn.execute("""UPDATE crawl_queue SET processed_at=crawled_at, process_error=?
            WHERE post_id=?""", (str(error)[:500], post_id))
        conn.commit()
        print(f"[process] lỗi {post_id}: {error}")


def process_worker(cfg, ready, stop, producers_done, once=False):
    conn = connect(cfg["db_path"])
    bundle = load_bundle(cfg)
    try:
        while not stop.is_set():
            try:
                post_id = ready.get(timeout=1)
            except queue.Empty:
                post_id = None
            row = _next_processing(conn, post_id) if post_id else _next_processing(conn)
            if row:
                _process_one(conn, cfg, bundle, row)
            if post_id:
                ready.task_done()
            if once and producers_done.is_set() and ready.empty() and _next_processing(conn) is None:
                return
    finally:
        conn.close()


async def run_workers(cfg, once=False):
    ready = queue.Queue(maxsize=100)
    stop = threading.Event()
    producers_done = threading.Event()
    async def run_producers():
        try:
            await asyncio.gather(
                asyncio.to_thread(new_worker, cfg, ready, stop, once),
                asyncio.to_thread(revisit_worker, cfg, ready, stop, once),
            )
        finally:
            producers_done.set()

    producers = asyncio.create_task(run_producers())
    processor = asyncio.create_task(asyncio.to_thread(
        process_worker, cfg, ready, stop, producers_done, once
    ))
    try:
        await asyncio.gather(producers, processor)
    finally:
        stop.set()
        producers_done.set()
        await asyncio.gather(producers, processor, return_exceptions=True)


def process_existing(cfg):
    conn = connect(cfg["db_path"])
    try:
        parse_all(conn)
        preprocess_db(conn)
        print("predicted:", predict_new(conn, cfg))
        print("report rows:", export_report(conn, cfg))
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Chạy một vòng rồi thoát")
    parser.add_argument("--no-crawl", action="store_true", help="Chỉ xử lý dữ liệu hiện có rồi thoát")
    args = parser.parse_args()
    cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
    lock = FileLock("pipeline.lock", timeout=0)
    try:
        lock.acquire()
    except Timeout:
        sys.exit("Lần chạy trước chưa xong.")

    conn = connect(cfg["db_path"])
    conn.execute("UPDATE crawl_queue SET status='pending' WHERE status='crawling'")
    conn.execute("UPDATE crawl_queue SET status='done' WHERE status='revisiting'")
    conn.commit()
    start, p0, c0 = datetime.now(), count(conn, "posts"), count(conn, "comments")
    conn.close()
    status, error = "ok", None
    try:
        if args.no_crawl:
            process_existing(cfg)
        else:
            asyncio.run(run_workers(cfg, args.once))
    except KeyboardInterrupt:
        status = "stopped"
    except Exception as exc:
        status = "checkpoint" if isinstance(exc, Checkpoint) else "error"
        error = str(exc)[:500]
        print(status, error)
    finally:
        conn = connect(cfg["db_path"])
        conn.execute("UPDATE crawl_queue SET status='pending' WHERE status='crawling'")
        conn.execute("UPDATE crawl_queue SET status='done' WHERE status='revisiting'")
        conn.execute("""INSERT INTO crawl_runs
            (started_at, finished_at, new_posts, new_comments, status, error)
            VALUES (?,?,?,?,?,?)""",
                     (start.isoformat(), datetime.now().isoformat(), count(conn, "posts") - p0,
                      count(conn, "comments") - c0, status, error))
        conn.commit()
        conn.close()
        lock.release()


if __name__ == "__main__":
    main()
