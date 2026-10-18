import re
import time
from datetime import datetime, timedelta
from pathlib import Path

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from crawler.browser import is_checkpoint
from crawler.utils import human_sleep

POST_DIALOG_XPATH = ("//div[@role='dialog'][.//*[self::h1 or self::h2 or self::h3 or self::h4]["
                     "starts-with(normalize-space(.), 'Bài viết của') or "
                     "starts-with(normalize-space(.), 'Post by')]]")
EXPAND_LABEL = re.compile(
    r"^(?:Xem|View)\b.*(?:phản hồi|câu trả lời|bình luận|repl(?:y|ies)|comments?)\b",
    re.IGNORECASE,
)


class Checkpoint(Exception):
    pass


def find_post_dialog(driver, post_id):
    dialogs = driver.find_elements(By.XPATH, POST_DIALOG_XPATH)
    matching = [d for d in dialogs
                if d.find_elements(By.CSS_SELECTOR, f"a[href*='/posts/{post_id}']")]
    return matching[-1] if matching else None  # Facebook lồng hai role=dialog; phần tử cuối là modal trong


def show_all_comments(driver, dialog):
    try:
        dialog.find_element(
            By.XPATH, ".//span[contains(., 'Phù hợp nhất') or contains(., 'Most relevant')]"
        ).click()
        human_sleep()
        driver.find_element(
            By.XPATH, "//span[contains(., 'Tất cả bình luận') or contains(., 'All comments')]"
        ).click()
        human_sleep(2, 3)
    except Exception:
        pass  # bài ít comment thì không có menu này


def is_expand_label(text):
    return bool(EXPAND_LABEL.search(" ".join((text or "").split())))


def _expand_buttons(dialog):
    result = []
    for button in dialog.find_elements(By.CSS_SELECTOR, "[role='button']"):
        try:
            label = " ".join((button.text or button.get_attribute("aria-label") or "").split())
            if button.is_displayed() and is_expand_label(label):
                result.append((button, label))
        except StaleElementReferenceException:
            continue
    return result


def _comment_count(dialog):
    return len(dialog.find_elements(By.CSS_SELECTOR, "div[role='article'][aria-label]"))


def expand_all(driver, post_id, timeout=180):
    end = time.time() + timeout
    opened = 0
    while time.time() < end:
        dialog = find_post_dialog(driver, post_id)
        if dialog is None:
            raise RuntimeError("Không còn thấy modal trong lúc mở phản hồi")

        buttons = _expand_buttons(dialog)
        if not buttons:
            print(f"  Đã mở hết phản hồi ({opened} lần bấm).")
            return

        button, label = buttons[0]
        before = _comment_count(dialog)
        print(f"  Mở: {label}")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", button)
        driver.execute_script("arguments[0].click();", button)
        opened += 1

        try:
            WebDriverWait(driver, min(15, max(1, end - time.time()))).until(
                lambda d: _expansion_finished(d, post_id, button, before)
            )
        except TimeoutException:
            dialog = find_post_dialog(driver, post_id)
            remaining = _expand_buttons(dialog) if dialog else []
            labels = ", ".join(label for _, label in remaining[:3])
            raise RuntimeError(f"Bấm '{label}' nhưng Facebook không tải phản hồi; còn: {labels}")
        human_sleep(0.4, 1.0)

    dialog = find_post_dialog(driver, post_id)
    remaining = _expand_buttons(dialog) if dialog else []
    labels = ", ".join(label for _, label in remaining[:3])
    raise RuntimeError(f"Hết {timeout}s nhưng vẫn còn nút mở phản hồi: {labels}")


def _expansion_finished(driver, post_id, clicked_button, before_count):
    try:
        clicked_button.is_enabled()
    except StaleElementReferenceException:
        return True
    dialog = find_post_dialog(driver, post_id)
    return dialog is not None and _comment_count(dialog) > before_count


def crawl_post(driver, conn, post_id, url, html_dir, revisit_days=7,
               revisit_minutes=60, failure_status="failed"):
    try:
        driver.get(url)
        if is_checkpoint(driver):
            raise Checkpoint(driver.current_url)
        dialog = WebDriverWait(driver, 15).until(lambda d: find_post_dialog(d, post_id))
        show_all_comments(driver, dialog)
        expand_all(driver, post_id)
        dialog = find_post_dialog(driver, post_id)
        if dialog is None:
            raise RuntimeError("Không còn thấy modal của đúng bài viết")
        remaining = _expand_buttons(dialog)
        if remaining:
            labels = ", ".join(label for _, label in remaining[:3])
            raise RuntimeError(f"Chưa mở hết phản hồi: {labels}")

        path = Path(html_dir) / f"post_{post_id}.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dialog.get_attribute("outerHTML"), encoding="utf-8")
        comments = len(dialog.find_elements(By.CSS_SELECTOR, "div[role='article'][aria-label]"))
        print(f"  Đã lưu modal bài viết và {comments} comment.")
        now = datetime.now()
        conn.execute("""UPDATE crawl_queue SET status='done', attempts=0, last_error=NULL,
            html_path=?, crawled_at=?, revisit_until=COALESCE(revisit_until, ?), next_revisit_at=?
            WHERE post_id=?""",
                     (str(path), now.strftime("%Y-%m-%d %H:%M:%S"),
                      (now + timedelta(days=revisit_days)).strftime("%Y-%m-%d %H:%M:%S"),
                      (now + timedelta(minutes=revisit_minutes)).strftime("%Y-%m-%d %H:%M:%S"),
                      post_id))
    except Checkpoint:
        raise
    except Exception as e:
        Path("logs").mkdir(exist_ok=True)
        try:
            driver.save_screenshot(f"logs/fail_{post_id}.png")
        except Exception:
            pass
        conn.execute("""UPDATE crawl_queue SET status=?, attempts=attempts+1, last_error=?,
            next_revisit_at=datetime('now', '+' || ? || ' minutes') WHERE post_id=?""",
                     (failure_status, str(e)[:500], revisit_minutes, post_id))
        conn.commit()
        return False
    conn.commit()
    return True
