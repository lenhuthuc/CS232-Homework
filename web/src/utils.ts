export function formatPercent(value: number | undefined | null, decimals = 1): string {
  const num = Number(value || 0);
  return `${(num * 100).toFixed(decimals)}%`;
}

export function escapeHtml(str: string | undefined | null): string {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function safeFacebookUrl(url: string | undefined | null): string {
  if (!url) return "#";
  try {
    const parsed = new URL(url);
    if (parsed.hostname.includes("facebook.com")) {
      return url;
    }
  } catch {
    // ignore
  }
  return "#";
}

export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
