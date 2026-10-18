import re
import unicodedata

TEENCODE = {"ko": "không", "k": "không", "hok": "không", "dc": "được", "đc": "được", "j": "gì",
            "trg": "trường", "gv": "giảng viên", "pđt": "phòng đào tạo", "pdt": "phòng đào tạo",
            "sv": "sinh viên", "vs": "với", "ntn": "như thế nào", "mn": "mọi người"}
EMOJI = {"😡": " tức_giận ", "😠": " tức_giận ", "😭": " buồn ", "😢": " buồn ", "😂": " buồn_cười ",
         "🤣": " buồn_cười ", "👍": " tốt ", "👎": " tệ ", "❤": " yêu_thích "}
_seg = None


def _segment(s):
    global _seg
    if _seg is None:
        try:
            from underthesea import word_tokenize
            _seg = lambda x: word_tokenize(x, format="text")
        except ImportError:
            _seg = lambda x: x  # ponytail: không tách từ nếu thiếu underthesea; PhoBERT v1 sẽ kém đi
    return _seg(s)


def clean(text):
    s = unicodedata.normalize("NFC", text or "").lower()
    s = re.sub(r"https?://\S+", " <url> ", s)
    for k, v in EMOJI.items():
        s = s.replace(k, v)
    s = re.sub(r"(.)\1{2,}", r"\1", s)  # quáaaa -> quá
    s = " ".join(TEENCODE.get(w, w) for w in s.split())
    return _segment(s)


def preprocess_db(conn):
    for table, key, col in (("comments", "comment_id", "text"), ("posts", "post_id", "caption")):
        for r in conn.execute(f"SELECT {key}, {col} FROM {table} WHERE text_clean IS NULL").fetchall():
            conn.execute(f"UPDATE {table} SET text_clean=? WHERE {key}=?", (clean(r[1]), r[0]))
    conn.commit()


def preprocess_post(conn, post_id):
    row = conn.execute(
        "SELECT caption FROM posts WHERE post_id=? AND text_clean IS NULL", (post_id,)
    ).fetchone()
    if row:
        conn.execute("UPDATE posts SET text_clean=? WHERE post_id=?", (clean(row[0]), post_id))
    for row in conn.execute(
            "SELECT comment_id, text FROM comments WHERE post_id=? AND text_clean IS NULL", (post_id,)):
        conn.execute("UPDATE comments SET text_clean=? WHERE comment_id=?", (clean(row[1]), row[0]))
    conn.commit()
