const ACCESS_KEY = "stock_access_token";
/** 历史遗留：refresh 已迁至 HttpOnly Cookie，登录后清理本地残留 */
const LEGACY_REFRESH_KEY = "stock_refresh_token";
const USERNAME_KEY = "stock_username";

export interface AuthTokensPublic {
  access_token: string;
  token_type?: string;
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_KEY);
}

export function getStoredUsername(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(USERNAME_KEY);
}

export function setTokens(data: AuthTokensPublic) {
  if (typeof window === "undefined") return;
  localStorage.setItem(ACCESS_KEY, data.access_token);
  localStorage.removeItem(LEGACY_REFRESH_KEY);
}

export function setStoredUsername(username: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem(USERNAME_KEY, username);
}

export function clearAuthStorage() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(LEGACY_REFRESH_KEY);
  localStorage.removeItem(USERNAME_KEY);
}
