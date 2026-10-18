import type { FilterState } from "../types";

export function renderFilterControls(state: FilterState, totalCount: number, matchedCount: number): string {
  const isFiltered =
    Boolean(state.searchQuery) ||
    state.typeFilter !== "all" ||
    state.sentimentFilter !== "flagged" ||
    state.sortBy !== "risk_desc";

  return `
    <div class="filters-bar">
      <div class="search-box">
        <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <input 
          id="search-input" 
          type="search" 
          placeholder="Tìm kiếm nội dung, tác giả, tiêu đề bài viết..." 
          value="${state.searchQuery}"
          autocomplete="off"
        />
        <kbd class="kbd-hint">/</kbd>
      </div>

      <div class="filters-row">
        <div class="select-group">
          <label for="type-select">Loại:</label>
          <select id="type-select">
            <option value="all" ${state.typeFilter === "all" ? "selected" : ""}>Tất cả loại</option>
            <option value="post" ${state.typeFilter === "post" ? "selected" : ""}>Bài viết chính</option>
            <option value="comment" ${state.typeFilter === "comment" ? "selected" : ""}>Bình luận</option>
            <option value="reply" ${state.typeFilter === "reply" ? "selected" : ""}>Phản hồi lồng</option>
          </select>
        </div>

        <div class="select-group">
          <label for="sentiment-select">Cảm xúc:</label>
          <select id="sentiment-select">
            <option value="flagged" ${state.sentimentFilter === "flagged" ? "selected" : ""}>⚠️ Cần chú ý (≥ ngưỡng)</option>
            <option value="all" ${state.sentimentFilter === "all" ? "selected" : ""}>Tất cả cảm xúc</option>
            <option value="negative" ${state.sentimentFilter === "negative" ? "selected" : ""}>Tiêu cực (Negative)</option>
            <option value="neutral" ${state.sentimentFilter === "neutral" ? "selected" : ""}>Trung tính (Neutral)</option>
            <option value="positive" ${state.sentimentFilter === "positive" ? "selected" : ""}>Tích cực (Positive)</option>
          </select>
        </div>

        <div class="select-group">
          <label for="sort-select">Sắp xếp:</label>
          <select id="sort-select">
            <option value="risk_desc" ${state.sortBy === "risk_desc" ? "selected" : ""}>Nguy cơ tiêu cực (Cao → Thấp)</option>
            <option value="risk_asc" ${state.sortBy === "risk_asc" ? "selected" : ""}>Nguy cơ tiêu cực (Thấp → Cao)</option>
            <option value="related_desc" ${state.sortBy === "related_desc" ? "selected" : ""}>Độ liên quan UIT (Cao → Thấp)</option>
            <option value="author_asc" ${state.sortBy === "author_asc" ? "selected" : ""}>Tác giả (A → Z)</option>
          </select>
        </div>

        <button id="view-toggle" class="btn-ghost" title="Chuyển chế độ xem gọn / chi tiết">
          ${state.compactView ? "Chế độ chi tiết" : "Chế độ gọn"}
        </button>

        ${
          isFiltered
            ? `<button id="btn-reset-filters" class="btn-link" title="Xóa tất cả bộ lọc">Xóa lọc</button>`
            : ""
        }
      </div>

      <div class="filters-meta">
        <span class="count-badge">
          Hiển thị <strong>${matchedCount}</strong> / ${totalCount} bản ghi
        </span>
      </div>
    </div>
  `;
}
