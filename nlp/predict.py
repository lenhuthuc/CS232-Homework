import json
import zipfile
from pathlib import Path


PENDING = """
SELECT 'comment' AS target_type, c.comment_id AS target_id, c.text_clean AS text
FROM comments c
LEFT JOIN predictions pr ON pr.target_type='comment' AND pr.target_id=c.comment_id AND pr.model_version=:v
WHERE pr.id IS NULL AND c.text_clean IS NOT NULL
UNION ALL
SELECT 'post', p.post_id, p.text_clean
FROM posts p
LEFT JOIN predictions pr ON pr.target_type='post' AND pr.target_id=p.post_id AND pr.model_version=:v
WHERE pr.id IS NULL AND p.text_clean IS NOT NULL
"""

PENDING_POST = """
SELECT 'comment' AS target_type, comment_id AS target_id, text_clean AS text
FROM comments WHERE post_id=:post_id AND text_clean IS NOT NULL
UNION ALL
SELECT 'post', post_id, text_clean
FROM posts WHERE post_id=:post_id AND text_clean IS NOT NULL
"""


def _load_bundle(archive_path, model_dir):
    archive, root = Path(archive_path), Path(model_dir)
    if not (root / "config.json").is_file():
        if not archive.is_file():
            return None
        root.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(root.parent)
        extracted = root.parent / "model_bundle"
        if extracted != root:
            extracted.rename(root)

    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    from models.pos_neg.neural_model import NeuralFusion

    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    tokenizer = AutoTokenizer.from_pretrained(root / "phobert_text")
    text_model = AutoModelForSequenceClassification.from_pretrained(root / "phobert_text").eval()
    checkpoint = torch.load(root / "neural_fusion.pt", map_location="cpu", weights_only=True)
    fusion = NeuralFusion(**checkpoint["architecture"])
    fusion.load_state_dict(checkpoint["state_dict"])
    fusion.eval()
    return tokenizer, text_model, fusion, torch, config


def _probs(bundle, texts, batch_size=32):
    tokenizer, text_model, fusion, torch, config = bundle
    result = []
    for i in range(0, len(texts), batch_size):
        encoded = tokenizer(texts[i:i + batch_size], padding=True, truncation=True,
                            max_length=config["max_length"], return_tensors="pt")
        with torch.no_grad():
            text_prob = text_model(**encoded).logits.softmax(-1)
            count = torch.zeros((len(text_prob), 1))
            logits = fusion(text_prob, torch.zeros_like(text_prob), count)[0]
            result += logits.softmax(-1).tolist()
    return result


def load_bundle(cfg):
    return _load_bundle(cfg["pos_neg_archive"], cfg["pos_neg_model_dir"])


def predict_new(conn, cfg, bundle=None, post_id=None):
    bundle = bundle or load_bundle(cfg)
    if bundle is None:
        print("Chưa có pos_neg_model_bundle.zip -> bỏ qua bước dự đoán.")
        return 0

    if post_id is None:
        rows = conn.execute(PENDING, {"v": cfg["model_version"]}).fetchall()
    else:
        conn.execute("""DELETE FROM predictions WHERE model_version=? AND (
            (target_type='post' AND target_id=?) OR
            (target_type='comment' AND target_id IN
                (SELECT comment_id FROM comments WHERE post_id=?)))""",
                     (cfg["model_version"], post_id, post_id))
        rows = conn.execute(PENDING_POST, {"post_id": post_id}).fetchall()
    if not rows:
        conn.commit()
        return 0
    labels = [label.upper() for label in bundle[4]["labels"]]
    negative_index, positive_index = labels.index("NEG"), labels.index("POS")
    probabilities = _probs(bundle, [row["text"] or "" for row in rows])
    for row, scores in zip(rows, probabilities):
        negative, positive = scores[negative_index], scores[positive_index]
        conn.execute("""INSERT OR IGNORE INTO predictions (target_type, target_id, model_version, related_score,
            p_negative, p_neutral, p_positive, label) VALUES (?,?,?,?,?,?,?,?)""",
                     (row["target_type"], row["target_id"], cfg["model_version"], 1.0,
                      negative, 0.0, positive, "negative" if negative >= positive else "positive"))
    conn.commit()
    return len(rows)
