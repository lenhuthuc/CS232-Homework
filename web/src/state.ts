import type { DashboardData, FeedItem, FilterState, Summary } from "./types";

export type StateListener = () => void;

class Store {
  private summary: Summary | null = null;
  private items: FeedItem[] = [];
  private loading = true;
  private error: string | null = null;
  private lastUpdated: Date | null = null;

  private filters: FilterState = {
    searchQuery: "",
    typeFilter: "all",
    sentimentFilter: "flagged",
    sortBy: "risk_desc",
    compactView: false,
  };

  private listeners: Set<StateListener> = new Set();

  public subscribe(listener: StateListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notify(): void {
    for (const listener of this.listeners) {
      listener();
    }
  }

  public setData(data: DashboardData): void {
    this.summary = data.summary;
    this.items = data.items;
    this.loading = false;
    this.error = null;
    this.lastUpdated = new Date();
    this.notify();
  }

  public setLoading(loading: boolean): void {
    this.loading = loading;
    this.notify();
  }

  public setError(error: string): void {
    this.error = error;
    this.loading = false;
    this.notify();
  }

  public updateFilters(partial: Partial<FilterState>): void {
    this.filters = { ...this.filters, ...partial };
    this.notify();
  }

  public resetFilters(): void {
    this.filters = {
      searchQuery: "",
      typeFilter: "all",
      sentimentFilter: "all",
      sortBy: "risk_desc",
      compactView: this.filters.compactView,
    };
    this.notify();
  }

  public getSummary(): Summary | null {
    return this.summary;
  }

  public getRawItems(): FeedItem[] {
    return this.items;
  }

  public getFilters(): FilterState {
    return { ...this.filters };
  }

  public isLoading(): boolean {
    return this.loading;
  }

  public getError(): string | null {
    return this.error;
  }

  public getLastUpdated(): Date | null {
    return this.lastUpdated;
  }

  public getFilteredItems(): FeedItem[] {
    const { searchQuery, typeFilter, sentimentFilter, sortBy } = this.filters;
    const threshold = this.summary?.threshold ?? 0.7;
    const query = searchQuery.trim().toLowerCase();

    return this.items
      .filter((item) => {
        // Search query
        if (query) {
          const combined = `${item.text || ""} ${item.parent_text || ""} ${item.author_name || ""} ${item.post_title || ""}`.toLowerCase();
          if (!combined.includes(query)) {
            return false;
          }
        }

        // Type filter
        if (typeFilter === "post" && item.type !== "post") return false;
        if (typeFilter === "comment" && (item.type !== "comment" || item.parent_comment_id)) return false;
        if (typeFilter === "reply" && !item.parent_comment_id) return false;

        // Sentiment filter
        if (sentimentFilter === "flagged") {
          return (item.p_negative || 0) >= threshold;
        } else if (sentimentFilter !== "all") {
          return item.label === sentimentFilter;
        }

        return true;
      })
      .sort((a, b) => {
        switch (sortBy) {
          case "risk_desc":
            return (b.p_negative || 0) - (a.p_negative || 0);
          case "risk_asc":
            return (a.p_negative || 0) - (b.p_negative || 0);
          case "related_desc":
            return (b.related_score || 0) - (a.related_score || 0);
          case "author_asc":
            return (a.author_name || "").localeCompare(b.author_name || "");
          default:
            return 0;
        }
      });
  }
}

export const store = new Store();
