import type { DashboardData, PredictResponse } from "./types";

export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
    this.name = "ApiError";
  }
}

export async function fetchDashboardData(): Promise<DashboardData> {
  const res = await fetch("/api/results", {
    cache: "no-store",
    headers: {
      Accept: "application/json",
    },
  });

  if (!res.ok) {
    let msg = `HTTP error ${res.status}`;
    try {
      const err = await res.json();
      if (err.error) msg = err.error;
    } catch {
      // ignore
    }
    throw new ApiError(msg, res.status);
  }

  return res.json();
}

export async function predictSentiment(text: string): Promise<PredictResponse> {
  const trimmed = text.trim();
  if (!trimmed) {
    throw new ApiError("Vui lòng nhập nội dung cần phân tích.");
  }

  const res = await fetch("/predict", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ text: trimmed }),
  });

  if (!res.ok) {
    let msg = `HTTP error ${res.status}`;
    try {
      const err = await res.json();
      if (err.error) msg = err.error;
    } catch {
      // ignore
    }
    throw new ApiError(msg, res.status);
  }

  return res.json();
}
