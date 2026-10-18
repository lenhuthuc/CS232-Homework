from pathlib import Path

import pandas as pd

QUERY = """
SELECT a.name AS author_name, 'comment' AS type, c.text, p.title AS post_title,
       pr.p_negative, pr.related_score, p.post_url, c.time_text AS time
FROM predictions pr
JOIN comments c ON pr.target_type='comment' AND pr.target_id=c.comment_id
JOIN posts p ON p.post_id=c.post_id
LEFT JOIN authors a ON a.author_id=c.author_id
WHERE pr.model_version=:v AND pr.related_score>=:rel AND pr.p_negative>=:neg
UNION ALL
SELECT a.name, 'post', p.caption, p.title, pr.p_negative, pr.related_score, p.post_url, p.time_text
FROM predictions pr JOIN posts p ON pr.target_type='post' AND pr.target_id=p.post_id
LEFT JOIN authors a ON a.author_id=p.author_id
WHERE pr.model_version=:v AND pr.related_score>=:rel AND pr.p_negative>=:neg
ORDER BY p_negative DESC
"""


def export_report(conn, cfg, out="data/output/negative_report.csv"):
    df = pd.read_sql(QUERY, conn, params={"v": cfg["model_version"], "rel": cfg["related_threshold"],
                                          "neg": cfg["negative_threshold"]})
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_csv(path, index=False, encoding="utf-8-sig")
    except PermissionError:
        fallback = path.with_name(f"{path.stem}_new{path.suffix}")
        df.to_csv(fallback, index=False, encoding="utf-8-sig")
        print(f"Report cũ đang mở; đã ghi vào: {fallback}")
    return len(df)
