import type { Summary } from "../types";
import { formatPercent } from "../utils";

export function renderStatsBar(summary: Summary | null): string {
  if (!summary) {
    return `
      <div class="stats-grid skeleton-pulse">
        <div class="stat-card"></div>
        <div class="stat-card"></div>
        <div class="stat-card"></div>
        <div class="stat-card"></div>
      </div>
    `;
  }

  const negRate = summary.analyzed ? (summary.negative / summary.analyzed) * 100 : 0;
  const neuRate = summary.analyzed ? (summary.neutral / summary.analyzed) * 100 : 0;
  const posRate = summary.analyzed ? (summary.positive / summary.analyzed) * 100 : 0;

  return `
    <div class="stats-overview">
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-header">
            <span class="stat-label">Tổng bài viết</span>
            <span class="stat-tag">Posts</span>
          </div>
          <div class="stat-value">${summary.posts.toLocaleString()}</div>
          <div class="stat-sub">Đã thu thập từ UIT group</div>
        </div>

        <div class="stat-card">
          <div class="stat-header">
            <span class="stat-label">Bình luận / Phản hồi</span>
            <span class="stat-tag">Comments</span>
          </div>
          <div class="stat-value">${summary.comments.toLocaleString()}</div>
          <div class="stat-sub">Gồm ${summary.replies.toLocaleString()} lượt phản hồi lồng</div>
        </div>

        <div class="stat-card">
          <div class="stat-header">
            <span class="stat-label">Đã suy luận NLP</span>
            <span class="stat-tag">PhoBERT</span>
          </div>
          <div class="stat-value">${summary.analyzed.toLocaleString()}</div>
          <div class="stat-sub">Phiên bản: <code>${summary.model_version}</code></div>
        </div>

        <div class="stat-card stat-alert">
          <div class="stat-header">
            <span class="stat-label">Tiêu cực cần chú ý</span>
            <span class="badge-flagged">≥ ${formatPercent(summary.threshold, 0)}</span>
          </div>
          <div class="stat-value stat-value-alert">${summary.flagged.toLocaleString()}</div>
          <div class="stat-sub">Chiếm ${summary.analyzed ? formatPercent(summary.flagged / summary.analyzed) : "0%"} tổng thảo luận</div>
        </div>
      </div>

      <div class="distribution-panel">
        <div class="distribution-header">
          <span class="distribution-title">Phân bố cảm xúc cộng đồng</span>
          <div class="distribution-legend">
            <span class="legend-item"><span class="dot dot-negative"></span>Tiêu cực: <strong>${summary.negative}</strong> (${negRate.toFixed(1)}%)</span>
            <span class="legend-item"><span class="dot dot-neutral"></span>Trung tính: <strong>${summary.neutral}</strong> (${neuRate.toFixed(1)}%)</span>
            <span class="legend-item"><span class="dot dot-positive"></span>Tích cực: <strong>${summary.positive}</strong> (${posRate.toFixed(1)}%)</span>
          </div>
        </div>
        <div class="distribution-track" title="Tỷ lệ: Tiêu cực ${negRate.toFixed(1)}%, Trung tính ${neuRate.toFixed(1)}%, Tích cực ${posRate.toFixed(1)}%">
          <div class="bar-segment bar-negative" style="width: ${negRate}%"></div>
          <div class="bar-segment bar-neutral" style="width: ${neuRate}%"></div>
          <div class="bar-segment bar-positive" style="width: ${posRate}%"></div>
        </div>
      </div>
    </div>
  `;
}
