"""Dashboard kết quả crawl và demo dự đoán POS/NEG.

Chạy: python demo_app.py
Kiểm tra nhanh model: python demo_app.py --text "Hôm nay vui quá"
"""
import argparse
import json
import mimetypes
import sqlite3
import sys
import threading
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
CONFIG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
ARCHIVE = ROOT / CONFIG["pos_neg_archive"]
MODEL_DIR = ROOT / CONFIG["pos_neg_model_dir"]
DB_PATH = ROOT / CONFIG["db_path"]
WEB_DIST = ROOT / "web" / "dist"
_predictor = None


DASHBOARD_QUERY = """
SELECT pr.target_type AS type, pr.target_id, pr.label, pr.p_negative, pr.p_neutral,
       pr.p_positive, pr.related_score,
       COALESCE(a.name, 'Ẩn danh') AS author_name, c.text, p.title AS post_title,
       p.post_url, c.time_text AS time, pr.predicted_at,
       c.parent_comment_id, parent.text AS parent_text
FROM predictions pr
JOIN comments c ON pr.target_type='comment' AND pr.target_id=c.comment_id
JOIN posts p ON p.post_id=c.post_id
LEFT JOIN authors a ON a.author_id=c.author_id
LEFT JOIN comments parent ON parent.comment_id=c.parent_comment_id
WHERE pr.model_version=?
UNION ALL
SELECT pr.target_type, pr.target_id, pr.label, pr.p_negative, pr.p_neutral,
       pr.p_positive, pr.related_score,
       COALESCE(a.name, 'Ẩn danh'), p.caption, p.title, p.post_url, p.time_text,
       pr.predicted_at, NULL, NULL
FROM predictions pr
JOIN posts p ON pr.target_type='post' AND pr.target_id=p.post_id
LEFT JOIN authors a ON a.author_id=p.author_id
WHERE pr.model_version=?
ORDER BY p_negative DESC
"""


def dashboard_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    version = CONFIG["model_version"]
    items = [dict(row) for row in conn.execute(DASHBOARD_QUERY, (version, version)).fetchall()]
    summary = {
        "posts": conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
        "comments": conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0],
        "replies": conn.execute(
            "SELECT COUNT(*) FROM comments WHERE parent_comment_id IS NOT NULL"
        ).fetchone()[0],
        "analyzed": len(items),
        "negative": sum(item["label"] == "negative" for item in items),
        "neutral": sum(item["label"] == "neutral" for item in items),
        "positive": sum(item["label"] == "positive" for item in items),
        "flagged": sum((item["p_negative"] or 0) >= CONFIG["negative_threshold"] for item in items),
        "threshold": CONFIG["negative_threshold"],
        "model_version": version,
    }
    conn.close()
    return {"summary": summary, "items": items}


def load_predictor():
    global _predictor
    if _predictor is not None:
        return _predictor
    if not ARCHIVE.is_file():
        raise FileNotFoundError(f"Không tìm thấy model: {ARCHIVE}")
    if not (MODEL_DIR / "config.json").is_file():
        MODEL_DIR.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(ARCHIVE) as archive:
            archive.extractall(MODEL_DIR.parent)
        (MODEL_DIR.parent / "model_bundle").rename(MODEL_DIR)
    sys.path.insert(0, str(MODEL_DIR))
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    from neural_model import NeuralFusion

    config = json.loads((MODEL_DIR / "config.json").read_text(encoding="utf-8"))
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR / "phobert_text")
    text_model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR / "phobert_text").eval()
    checkpoint = torch.load(MODEL_DIR / "neural_fusion.pt", map_location="cpu", weights_only=True)
    fusion = NeuralFusion(**checkpoint["architecture"])
    fusion.load_state_dict(checkpoint["state_dict"])
    fusion.eval()

    class TextPredictor:
        @torch.no_grad()
        def predict(self, text):
            from underthesea import word_tokenize
            segmented = word_tokenize(text, format="text")
            encoded = tokenizer(segmented, return_tensors="pt", truncation=True,
                                max_length=config["max_length"])
            text_prob = text_model(**encoded).logits.softmax(-1)
            count = torch.zeros((1, 1))
            logits = fusion(text_prob, torch.zeros_like(text_prob), count)[0]
            probabilities = logits.softmax(-1)[0].tolist()
            return {"label": config["labels"][probabilities.index(max(probabilities))],
                    "probabilities": dict(zip(config["labels"], probabilities))}

    _predictor = TextPredictor()
    return _predictor


def predict(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Vui lòng nhập nội dung cần phân tích.")
    return load_predictor().predict(text.strip())


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self._add_cors_headers()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/results":
            try:
                self._json(200, dashboard_data())
            except Exception as exc:
                self._json(500, {"error": str(exc)})
        else:
            self._serve_static(path)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path != "/predict":
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(size))
            self._json(200, predict(data.get("text")))
        except Exception as exc:
            self._json(400, {"error": str(exc)})

    def _serve_static(self, rel_path):
        if rel_path in ("", "/"):
            rel_path = "index.html"
        rel_path = rel_path.lstrip("/")

        base = WEB_DIST.resolve()
        target = (WEB_DIST / rel_path).resolve()

        # Prevent path traversal outside WEB_DIST
        try:
            target.relative_to(base)
        except ValueError:
            self.send_error(403)
            return

        if not target.is_file():
            fallback = WEB_DIST / "index.html"
            if fallback.is_file():
                target = fallback
            else:
                msg = (
                    b"Web UI chua duoc build.\n"
                    b"Vui long chay:\n"
                    b"  cd web\n"
                    b"  pnpm install\n"
                    b"  pnpm run build\n"
                )
                self._send(404, msg, "text/plain; charset=utf-8")
                return

        ctype, _ = mimetypes.guess_type(str(target))
        if not ctype:
            ctype = "application/octet-stream"
        if target.suffix == ".js":
            ctype = "application/javascript; charset=utf-8"
        elif target.suffix == ".css":
            ctype = "text/css; charset=utf-8"
        elif target.suffix == ".html":
            ctype = "text/html; charset=utf-8"

        try:
            body = target.read_bytes()
            self._send(200, body, ctype)
        except OSError:
            self.send_error(500)

    def _add_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept")

    def _json(self, status, data):
        self._send(status, json.dumps(data, ensure_ascii=False).encode(),
                   "application/json; charset=utf-8")

    def _send(self, status, body, content_type):
        self.send_response(status)
        self._add_cors_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", help="Chạy một dự đoán rồi thoát")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if args.text:
        print(json.dumps(predict(args.text), ensure_ascii=False, indent=2))
        return
    url = f"http://127.0.0.1:{args.port}"
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Dashboard đang chạy tại {url} (Ctrl+C để dừng)")
    if not args.no_browser:
        threading.Timer(1, webbrowser.open, args=(url,)).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
