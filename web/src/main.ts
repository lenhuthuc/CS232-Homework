import "./style.css";
import { fetchDashboardData } from "./api";
import { store } from "./state";
import { renderNavbar } from "./components/navbar";
import { renderStatsBar } from "./components/statsBar";
import { renderFilterControls } from "./components/filterControls";
import { renderFeedList } from "./components/feedList";
import { copyToClipboard } from "./utils";
import type { SentimentFilter, SortOption, TypeFilter } from "./types";

// Theme handling
const THEME_KEY = "uit_signal_theme";
let currentTheme = localStorage.getItem(THEME_KEY) || "light";
document.documentElement.setAttribute("data-theme", currentTheme);

function toggleTheme() {
  currentTheme = currentTheme === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", currentTheme);
  localStorage.setItem(THEME_KEY, currentTheme);
  renderApp();
}

function showToast(message: string) {
  const existing = document.querySelector(".toast-msg");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.className = "toast-msg";
  toast.textContent = message;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 2000);
}

// Initial HTML structure
const app = document.getElementById("app")!;
app.innerHTML = `
  <div id="navbar-container"></div>
  <main class="app-main">
    <section id="stats-container"></section>
    <section class="feed-section">
      <div id="filters-container"></div>
      <div id="feed-container"></div>
    </section>
  </main>
`;

// Render function
function renderApp() {
  const navbarContainer = document.getElementById("navbar-container")!;
  const statsContainer = document.getElementById("stats-container")!;
  const filtersContainer = document.getElementById("filters-container")!;
  const feedContainer = document.getElementById("feed-container")!;

  // 1. Navbar
  navbarContainer.innerHTML = renderNavbar(
    store.getLastUpdated(),
    store.isLoading(),
    currentTheme
  );

  // 2. Stats
  statsContainer.innerHTML = renderStatsBar(store.getSummary());

  // 3. Filters
  const filters = store.getFilters();
  const rawItems = store.getRawItems();
  const filteredItems = store.getFilteredItems();
  filtersContainer.innerHTML = renderFilterControls(
    filters,
    rawItems.length,
    filteredItems.length
  );

  // 4. Feed
  const threshold = store.getSummary()?.threshold ?? 0.7;
  feedContainer.innerHTML = renderFeedList(
    filteredItems,
    threshold,
    filters.compactView
  );

  attachDynamicEvents();
}

// Attach event listeners for dynamic elements
function attachDynamicEvents() {
  // Theme toggle
  const btnTheme = document.getElementById("btn-theme-toggle");
  if (btnTheme) {
    btnTheme.onclick = toggleTheme;
  }

  // Refresh
  const btnRefresh = document.getElementById("btn-refresh");
  if (btnRefresh) {
    btnRefresh.onclick = loadData;
  }

  // Search input
  const searchInput = document.getElementById("search-input") as HTMLInputElement | null;
  if (searchInput) {
    searchInput.oninput = () => {
      store.updateFilters({ searchQuery: searchInput.value });
    };
  }

  // Type filter
  const typeSelect = document.getElementById("type-select") as HTMLSelectElement | null;
  if (typeSelect) {
    typeSelect.onchange = () => {
      store.updateFilters({ typeFilter: typeSelect.value as TypeFilter });
    };
  }

  // Sentiment filter
  const sentimentSelect = document.getElementById("sentiment-select") as HTMLSelectElement | null;
  if (sentimentSelect) {
    sentimentSelect.onchange = () => {
      store.updateFilters({ sentimentFilter: sentimentSelect.value as SentimentFilter });
    };
  }

  // Sort select
  const sortSelect = document.getElementById("sort-select") as HTMLSelectElement | null;
  if (sortSelect) {
    sortSelect.onchange = () => {
      store.updateFilters({ sortBy: sortSelect.value as SortOption });
    };
  }

  // View mode toggle
  const viewToggle = document.getElementById("view-toggle");
  if (viewToggle) {
    viewToggle.onclick = () => {
      const current = store.getFilters().compactView;
      store.updateFilters({ compactView: !current });
    };
  }

  // Reset filters
  const btnReset = document.getElementById("btn-reset-filters");
  if (btnReset) {
    btnReset.onclick = () => {
      store.resetFilters();
    };
  }

  // Copy buttons
  document.querySelectorAll<HTMLButtonElement>(".btn-copy").forEach((btn) => {
    btn.onclick = async () => {
      const text = btn.dataset.text || "";
      const ok = await copyToClipboard(text);
      if (ok) {
        showToast("Đã sao chép nội dung vào clipboard");
      }
    };
  });
}

// Global keyboard shortcuts
window.addEventListener("keydown", (e) => {
  if (e.key === "/" && document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "TEXTAREA") {
    e.preventDefault();
    const searchInput = document.getElementById("search-input") as HTMLInputElement | null;
    searchInput?.focus();
  }
});

// Load data
async function loadData() {
  store.setLoading(true);
  try {
    const data = await fetchDashboardData();
    store.setData(data);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Không thể tải dữ liệu";
    store.setError(msg);
  }
}

// Subscribe to store updates
store.subscribe(renderApp);

// Initialize
loadData();
