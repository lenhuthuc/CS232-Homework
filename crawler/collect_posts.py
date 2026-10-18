import re

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By

from crawler.utils import human_sleep

POST_RE = re.compile(r"/groups/([^/]+)/(?:posts|permalink)/(\d+)")


def collect_posts(driver, conn, group_url, max_new=50):
    """Scroll feed mới nhất đến khi đủ max_new hoặc 3 lần scroll không có link mới."""
    driver.get(group_url.rstrip("/") + "?sorting_setting=CHRONOLOGICAL")
    human_sleep(3, 5)
    known = {r[0] for r in conn.execute("SELECT post_id FROM crawl_queue")}
    new, seen, idle = {}, set(), 0
    while len(new) < max_new and idle < 3:
        found = 0
        for a in driver.find_elements(By.CSS_SELECTOR, "a[href*='/posts/'], a[href*='/permalink/']"):
            try:
                m = POST_RE.search(a.get_attribute("href") or "")
            except StaleElementReferenceException:
                continue
            if not m:
                continue
            gid, pid = m.groups()
            if pid in seen:
                continue
            seen.add(pid)
            found += 1
            if pid not in known:
                new[pid] = f"https://www.facebook.com/groups/{gid}/posts/{pid}"
        idle = 0 if found else idle + 1
        if len(new) >= max_new:
            break
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        human_sleep(2, 5)
    added = 0
    for pid, url in list(new.items())[:max_new]:
        added += conn.execute(
            "INSERT OR IGNORE INTO crawl_queue (post_id, post_url) VALUES (?, ?)", (pid, url)
        ).rowcount
    conn.commit()
    return added
