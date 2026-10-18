export function renderNavbar(lastUpdated: Date | null, isLoading: boolean, currentTheme: string): string {
  const timeStr = lastUpdated
    ? `Cập nhật lúc ${lastUpdated.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`
    : "Đang nạp dữ liệu...";

  return `
    <header class="app-header">
      <div class="header-inner">
        <div class="brand-group">
          <div class="brand-symbol">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
            </svg>
          </div>
          <div class="brand-text">
            <div class="brand-title">UIT Signal <span class="brand-badge">Monitor</span></div>
            <div class="brand-desc">Hệ thống giám sát sắc thái thảo luận sinh viên</div>
          </div>
        </div>

        <div class="header-status">
          <span class="status-indicator ${isLoading ? "status-pulse" : "status-live"}"></span>
          <span class="status-time">${timeStr}</span>
        </div>

        <div class="header-actions">
          <button id="btn-refresh" class="btn-action" title="Tải lại dữ liệu mới nhất" ${isLoading ? "disabled" : ""}>
            <svg class="${isLoading ? "spin-icon" : ""}" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.3"></path>
            </svg>
            <span>Làm mới</span>
          </button>

          <button id="btn-theme-toggle" class="btn-icon" title="Chuyển chế độ sáng/tối" aria-label="Toggle theme">
            ${
              currentTheme === "dark"
                ? `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>`
                : `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>`
            }
          </button>
        </div>
      </div>
    </header>
  `;
}
