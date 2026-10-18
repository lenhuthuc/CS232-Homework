import type { FeedItem } from "../types";
import { escapeHtml, formatPercent, safeFacebookUrl } from "../utils";

export function renderFeedList(
  items: FeedItem[],
  threshold: number,
  compactView: boolean
): string {
  if (items.length === 0) {
    return `
      <div class="empty-state">
        <div class="empty-icon">∅</div>
        <h3>Không tìm thấy dữ liệu phù hợp</h3>
        <p>Thử điều chỉnh từ khóa tìm kiếm hoặc bỏ bớt các bộ lọc bên trên.</p>
      </div>
    `;
  }

  return `
    <div class="feed-container ${compactView ? "feed-compact" : ""}">
      ${items
        .map((item) => {
          const isFlagged = item.p_negative >= threshold;
          const kindLabel =
            item.type === "post"
              ? "Bài viết"
              : item.parent_comment_id
              ? "Phản hồi"
              : "Bình luận";

          const pNeg = item.p_negative || 0;
          const pNegPercent = formatPercent(pNeg);
          const pRelPercent = formatPercent(item.related_score);

          const sentimentClass =
            item.label === "negative"
              ? "tag-negative"
              : item.label === "positive"
              ? "tag-positive"
              : "tag-neutral";

          const sentimentText =
            item.label === "negative"
              ? "Tiêu cực"
              : item.label === "positive"
              ? "Tích cực"
              : "Trung tính";

          return `
            <article class="feed-item ${isFlagged ? "item-flagged" : ""}" data-id="${escapeHtml(item.target_id)}">
              <header class="item-header">
                <div class="item-tags">
                  <span class="tag-sentiment ${sentimentClass}">
                    <span class="tag-dot"></span>
                    ${sentimentText}
                  </span>
                  <span class="tag-kind">${kindLabel}</span>
                  ${isFlagged ? `<span class="tag-alert">Nguy cơ cao</span>` : ""}
                </div>

                <div class="item-metrics">
                  <div class="metric-meter" title="Xác suất tiêu cực: ${pNegPercent}">
                    <span class="metric-meter-label">P(Neg):</span>
                    <div class="metric-meter-track">
                      <div class="metric-meter-fill ${isFlagged ? "fill-alert" : ""}" style="width: ${Math.min(100, pNeg * 100)}%"></div>
                    </div>
                    <span class="metric-meter-val">${pNegPercent}</span>
                  </div>
                  <span class="metric-sep">/</span>
                  <span class="metric-related" title="Độ liên quan UIT: ${pRelPercent}">UIT: ${pRelPercent}</span>
                </div>
              </header>

              <div class="item-author-row">
                <span class="author-name">${escapeHtml(item.author_name || "Ẩn danh")}</span>
                <span class="item-time">${escapeHtml(item.time || "Không rõ thời gian")}</span>
              </div>

              <div class="item-body">
                <p class="item-text">${escapeHtml(item.text)}</p>
              </div>

              ${
                item.parent_text
                  ? `
                <div class="item-parent-context">
                  <span class="context-icon">↳</span>
                  <div class="context-body">
                    <span class="context-label">Đang phản hồi cho:</span>
                    <p class="context-text">${escapeHtml(item.parent_text)}</p>
                  </div>
                </div>
              `
                  : ""
              }

              <footer class="item-footer">
                <div class="item-source">
                  ${
                    item.type === "comment" && item.post_title
                      ? `<span class="source-title" title="${escapeHtml(item.post_title)}">Bài viết: <em>${escapeHtml(item.post_title)}</em></span>`
                      : ""
                  }
                </div>
                <div class="item-actions">
                  <button class="btn-copy" data-text="${escapeHtml(item.text)}" title="Sao chép nội dung">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                    </svg>
                    <span>Sao chép</span>
                  </button>
                  <a href="${safeFacebookUrl(item.post_url)}" target="_blank" rel="noopener noreferrer" class="link-external">
                    <span>Mở Facebook</span>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                      <polyline points="15 3 21 3 21 9"></polyline>
                      <line x1="10" y1="14" x2="21" y2="3"></line>
                    </svg>
                  </a>
                </div>
              </footer>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}
