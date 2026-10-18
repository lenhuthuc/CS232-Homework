import hashlib
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from db.repo import upsert_author, upsert_comment, upsert_post

POST_HEADING = re.compile(r"^(?:Bài viết của|Post by)\s+(.+)$", re.I)
ROOT_COMMENT = re.compile(
    r"^(?:Bình luận dưới tên|Bình luận của|Comment by)\s+(.+?)(?:\s+(?:vào|at)\s+(?:khoảng\s+)?(.+))?$", re.I)
REPLY_COMMENT = re.compile(
    r"^(?:Phản hồi bình luận của .*? dưới tên|Phản hồi của|Reply by)\s+(.+?)(?:\s+(?:vào|at)\s+(?:khoảng\s+)?(.+))?$", re.I)
UID_RE = re.compile(r"/user/(\d+)|profile\.php\?id=(\d+)")
TIME_RE = re.compile(
    r"(?:khoảng\s+)?(?:\d+\s+(?:phút|giờ|ngày|tuần|tháng|năm)(?:\s+trước)?|vừa xong|hôm qua)", re.I)


def _post_root(soup, post_id):
    matches = []
    for dialog in soup.select("[role='dialog']"):
        heading = next((h for h in dialog.select("h1,h2,h3,h4")
                        if POST_HEADING.match(h.get_text(" ", strip=True))), None)
        if heading and dialog.select_one(f"a[href*='/posts/{post_id}']"):
            matches.append(dialog)
    return matches[-1] if matches else soup


def _author(block, name, identity):
    profile_url = None
    for link in block.find_all("a", href=True):
        if link.get_text(" ", strip=True) != name:
            continue
        profile_url = link["href"].split("?")[0]
        match = UID_RE.search(link["href"])
        if match:
            return {"author_id": match.group(1) or match.group(2), "name": name,
                    "profile_url": profile_url}
        path = urlparse(link["href"]).path.strip("/")
        if link["href"].startswith("http") and path and "/" not in path:
            return {"author_id": f"user:{path.lower()}", "name": name,
                    "profile_url": profile_url}
    digest = hashlib.sha1(f"{identity}:{name}".encode()).hexdigest()[:20]
    return {"author_id": f"name:{digest}", "name": name, "profile_url": profile_url}


def _text(block):
    parts = []
    for div in block.select("div[dir='auto']"):
        if not div.find("div", dir="auto"):
            text = div.get_text(" ", strip=True)
            if text:
                parts.append(text)
    return "\n".join(dict.fromkeys(parts))


def _comment_meta(label):
    match = REPLY_COMMENT.match(label)
    if match:
        return match.group(1), match.group(2), True
    match = ROOT_COMMENT.match(label)
    if match:
        return match.group(1), match.group(2), False
    return None


def _comment_link(block, post_id):
    for link in block.find_all("a", href=True):
        href = link["href"]
        if f"/posts/{post_id}" in href and "comment_id=" in href:
            return href, parse_qs(urlparse(href).query)
    return None, None


def _post_time(root, author_name):
    seen_author = False
    for value in root.stripped_strings:
        text = value.strip()
        if text == author_name:
            seen_author = True
        elif seen_author and TIME_RE.fullmatch(text):
            return text
    return None


def _caption(root):
    descriptions = [node.get_text("\n", strip=True)
                    for node in root.select("[data-ad-rendering-role='description']")]
    if descriptions:
        return max(descriptions, key=lambda text: (text.count(" "), len(text)))
    node = root.select_one("[data-ad-preview='message']")
    if node is not None:
        return node.get_text("\n", strip=True)
    for heading in root.select("h4"):
        text = heading.get_text(" ", strip=True)
        if text and not POST_HEADING.match(text) and "bình luận" not in text.lower():
            return text
    return ""


def parse_file(conn, path, post_id, post_url):
    soup = BeautifulSoup(Path(path).read_text(encoding="utf-8"), "lxml")
    root = _post_root(soup, post_id)
    heading = next((h for h in root.select("h1,h2,h3,h4")
                    if POST_HEADING.match(h.get_text(" ", strip=True))), None)
    author = None
    author_name = None
    if heading:
        author_name = POST_HEADING.match(heading.get_text(" ", strip=True)).group(1)
        author = _author(root, author_name, post_id)
        upsert_author(conn, author)

    caption = _caption(root)
    if not caption:
        raise ValueError("không thấy nội dung của đúng bài viết")
    upsert_post(conn, {"post_id": post_id, "author_id": author and author["author_id"],
                       "title": caption.split("\n", 1)[0][:200], "caption": caption,
                       "time_text": _post_time(root, author_name) if author_name else None,
                       "post_url": post_url})

    seen = set()
    for block in root.select("div[role='article'][aria-label]"):
        meta = _comment_meta(block.get("aria-label", ""))
        href, query = _comment_link(block, post_id)
        if not meta or not href:
            continue
        name, time_text, is_reply = meta
        comment_id = (query.get("reply_comment_id") or query.get("comment_id") or [None])[0]
        if not comment_id or comment_id in seen:
            continue
        text = _text(block)
        if not text:
            continue  # comment chỉ có ảnh/sticker chưa được lưu vào schema hiện tại
        comment_author = _author(block, name, f"{post_id}:{comment_id}")
        upsert_author(conn, comment_author)
        parent_id = (query.get("comment_id") or [None])[0] if is_reply else None
        upsert_comment(conn, {"comment_id": comment_id, "post_id": post_id,
                              "parent_comment_id": parent_id, "author_id": comment_author["author_id"],
                              "text": text, "time_text": time_text})
        seen.add(comment_id)
    conn.commit()
    return len(seen)


def parse_all(conn):
    total = 0
    for row in conn.execute(
            """SELECT post_id, post_url, html_path FROM crawl_queue
               WHERE status='done' AND html_path IS NOT NULL""").fetchall():
        try:
            total += parse_file(conn, row["html_path"], row["post_id"], row["post_url"])
        except Exception as error:
            print(f"parse fail {row['post_id']}: {error}")
    return total
