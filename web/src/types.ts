export type SentimentLabel = "negative" | "neutral" | "positive";
export type FeedItemType = "post" | "comment";

export interface FeedItem {
  type: FeedItemType;
  target_id: string;
  label: SentimentLabel;
  p_negative: number;
  p_neutral: number;
  p_positive: number;
  related_score: number;
  author_name: string;
  text: string;
  post_title: string;
  post_url: string;
  time: string;
  predicted_at: string;
  parent_comment_id?: string | null;
  parent_text?: string | null;
}

export interface Summary {
  posts: number;
  comments: number;
  replies: number;
  analyzed: number;
  negative: number;
  neutral: number;
  positive: number;
  flagged: number;
  threshold: number;
  model_version: string;
}

export interface DashboardData {
  summary: Summary;
  items: FeedItem[];
}

export interface PredictResponse {
  label: string;
  probabilities: Record<string, number>;
}


export type SentimentFilter = "all" | "flagged" | "negative" | "neutral" | "positive";
export type TypeFilter = "all" | "post" | "comment" | "reply";
export type SortOption = "risk_desc" | "risk_asc" | "related_desc" | "author_asc";

export interface FilterState {
  searchQuery: string;
  typeFilter: TypeFilter;
  sentimentFilter: SentimentFilter;
  sortBy: SortOption;
  compactView: boolean;
}
