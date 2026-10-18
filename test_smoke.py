"""python test_smoke.py -- kiểm tra parser + preprocess trên HTML giả."""
import pathlib
import tempfile

from db.repo import connect
from crawler.expand_post import is_expand_label
from nlp.preprocess import clean
from parser.parse_html import parse_all, parse_file

assert is_expand_label("Xem 6 câu trả lời")
assert is_expand_label("Xem 3 phản hồi")
assert is_expand_label("Xem thêm bình luận")
assert is_expand_label("View 2 more replies")
assert not is_expand_label("Viết phản hồi công khai…")

assert clean("Ko dc quáaaa 😡").split()[:2] == ["không", "được"], clean("Ko dc quáaaa 😡")

html = """<div role="article"><a href="/groups/1/user/10/">An</a>
<div data-ad-preview="message">[HỎI] Lịch thi đổi</div></div>
<div role="article" aria-label="Bình luận của Binh"><a href="/groups/1/user/11/">Binh</a>
<div dir="auto">chán thật</div><a href="/groups/1/posts/9/?comment_id=555">x</a></div>
<div role="article" aria-label="Phản hồi của Chi"><a href="/user/12/">Chi</a>
<div dir="auto">đúng</div><a href="/groups/1/posts/9/?comment_id=555&amp;reply_comment_id=556">x</a></div>"""
p = pathlib.Path(tempfile.gettempdir()) / "t.html"
p.write_text(html, encoding="utf-8")
conn = connect(":memory:")
assert parse_file(conn, p, "9", "u") == 2
rows = [tuple(r) for r in conn.execute("SELECT comment_id, parent_comment_id, text FROM comments ORDER BY 1")]
assert rows == [("555", None, "chán thật"), ("556", "555", "đúng")], rows
conn.close()

# Facebook giữ feed phía sau modal; parser chỉ được lấy modal có đúng post_id.
html = """<div data-ad-preview="message">nội dung sai phía sau</div>
<div role="article" aria-label="Bình luận dưới tên Sai vào 1 giờ trước">
<div dir="auto">comment sai</div><a href="/groups/1/posts/8/?comment_id=800">x</a></div>
<div role="dialog"><h2>Bài viết của An</h2><a href="/groups/1/user/10/">An</a>
<a href="/groups/1/posts/9/">4 giờ trước</a>
<div data-ad-preview="message">nội dung đúng</div>
<div role="article" aria-label="Bình luận dưới tên Bình vào khoảng 1 giờ trước">
<a href="/groups/1/user/11/">Bình</a><div dir="auto">comment đúng</div>
<a href="/groups/1/posts/9/?comment_id=999">x</a></div></div>"""
p.write_text(html, encoding="utf-8")
conn = connect(":memory:")
assert parse_file(conn, p, "9", "u") == 1
assert conn.execute("SELECT caption FROM posts").fetchone()[0] == "nội dung đúng"
assert conn.execute("SELECT text FROM comments").fetchone()[0] == "comment đúng"
conn.close()

# HTML cũ của một lần crawl thất bại không được parse lại.
conn = connect(":memory:")
conn.execute(
    "INSERT INTO crawl_queue(post_id, post_url, status, html_path) VALUES (?,?,?,?)",
    ("9", "u", "failed", str(p)),
)
assert parse_all(conn) == 0
assert conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0] == 0
conn.execute("UPDATE crawl_queue SET status='done' WHERE post_id='9'")
assert parse_all(conn) == 1
conn.close()
print("ok")
