import { message } from "antd";

import {
  clearAuthStorage,
  getAccessToken,
  setTokens,
  type AuthTokensPublic,
} from "./auth-storage";

const BASE_URL = "";

interface ApiEnvelope<T = unknown> {
  code: number;
  msg: string;
  data: T;
}

interface RequestConfig extends RequestInit {
  params?: Record<string, string | number | boolean | null | undefined>;
  showError?: boolean;
}

/** 这些路径失败时不尝试 refresh，避免死循环 */
const NO_REFRESH_PATHS = [
  "/api/auth/login",
  "/api/auth/register",
  "/api/auth/refresh",
];

let refreshInFlight: Promise<boolean> | null = null;

function pathOnly(fullURL: string): string {
  try {
    const u = fullURL.startsWith("http") ? new URL(fullURL) : new URL(fullURL, "http://local");
    return u.pathname;
  } catch {
    return fullURL.split("?")[0] ?? fullURL;
  }
}

function shouldTryRefresh(fullURL: string): boolean {
  const p = pathOnly(fullURL);
  return !NO_REFRESH_PATHS.some((x) => p === x || p.endsWith(x));
}

async function tryRefreshTokens(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      });
      const text = await res.text();
      if (!res.ok) {
        clearAuthStorage();
        return false;
      }
      let body: ApiEnvelope<AuthTokensPublic>;
      try {
        body = JSON.parse(text) as ApiEnvelope<AuthTokensPublic>;
      } catch {
        clearAuthStorage();
        return false;
      }
      if (body.code !== 0 || !body.data?.access_token) {
        clearAuthStorage();
        return false;
      }
      setTokens(body.data);
      return true;
    } catch {
      clearAuthStorage();
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

class HttpClient {
  private baseURL: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  private buildURL(url: string, params?: Record<string, unknown>): string {
    const fullURL = url.startsWith("http") ? url : `${this.baseURL}${url}`;

    if (!params || Object.keys(params).length === 0) {
      return fullURL;
    }

    const queryString = Object.entries(params)
      .filter(([, value]) => value !== undefined && value !== null)
      .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
      .join("&");

    return queryString ? `${fullURL}?${queryString}` : fullURL;
  }

  private mergeAuth(headers?: HeadersInit): HeadersInit {
    const h = new Headers({
      "Content-Type": "application/json",
      ...headers,
    });
    const token = getAccessToken();
    if (token) {
      h.set("Authorization", `Bearer ${token}`);
    }
    return h;
  }

  private async handleResponse<T>(response: Response, showError: boolean = true): Promise<T> {
    if (!response.ok) {
      const errorText = await response.text().catch(() => "");
      let errorMessage = `HTTP Error: ${response.status} ${response.statusText}`;

      try {
        const errorData = JSON.parse(errorText) as { detail?: string; msg?: string };
        errorMessage = errorData.detail || errorData.msg || errorMessage;
      } catch {
        errorMessage = errorText || errorMessage;
      }

      if (showError) {
        message.error(errorMessage);
      }

      throw new Error(errorMessage);
    }

    const data = (await response.json()) as ApiEnvelope<T>;

    if (data.code !== undefined && data.code !== 0) {
      const errorMsg = data.msg || "请求失败";
      if (showError) {
        message.error(errorMsg);
      }
      throw new Error(errorMsg);
    }

    return data.data as T;
  }

  private async request<T>(
    fullURL: string,
    init: RequestInit,
    showError: boolean,
    retriedAfterRefresh: boolean,
  ): Promise<T> {
    let response = await fetch(fullURL, {
      ...init,
      credentials: "include",
      headers: this.mergeAuth(init.headers),
    });

    if (response.status === 401 && !retriedAfterRefresh && shouldTryRefresh(fullURL)) {
      const ok = await tryRefreshTokens();
      if (ok) {
        response = await fetch(fullURL, {
          ...init,
          credentials: "include",
          headers: this.mergeAuth(init.headers),
        });
      }
    }

    return this.handleResponse<T>(response, showError);
  }

  async get<T = unknown>(url: string, config?: RequestConfig): Promise<T> {
    const { params, showError = true, ...init } = config || {};
    const fullURL = this.buildURL(url, params);

    try {
      return await this.request<T>(
        fullURL,
        { method: "GET", ...init },
        showError,
        false,
      );
    } catch (error) {
      console.error(`GET ${url} failed:`, error);
      throw error;
    }
  }

  async post<T = unknown>(url: string, data?: unknown, config?: RequestConfig): Promise<T> {
    const { showError = true, ...init } = config || {};

    try {
      return await this.request<T>(
        this.buildURL(url),
        {
          method: "POST",
          body: data ? JSON.stringify(data) : undefined,
          ...init,
        },
        showError,
        false,
      );
    } catch (error) {
      console.error(`POST ${url} failed:`, error);
      throw error;
    }
  }

  async put<T = unknown>(url: string, data?: unknown, config?: RequestConfig): Promise<T> {
    const { showError = true, ...init } = config || {};

    try {
      return await this.request<T>(
        this.buildURL(url),
        {
          method: "PUT",
          body: data ? JSON.stringify(data) : undefined,
          ...init,
        },
        showError,
        false,
      );
    } catch (error) {
      console.error(`PUT ${url} failed:`, error);
      throw error;
    }
  }

  async delete<T = unknown>(url: string, config?: RequestConfig): Promise<T> {
    const { params, showError = true, ...init } = config || {};
    const fullURL = this.buildURL(url, params);

    try {
      return await this.request<T>(
        fullURL,
        { method: "DELETE", ...init },
        showError,
        false,
      );
    } catch (error) {
      console.error(`DELETE ${url} failed:`, error);
      throw error;
    }
  }
}

const http = new HttpClient(BASE_URL);

export default http;

export interface ApiResponse<T = unknown> {
  code: number;
  msg: string;
  data: T;
}

export type { RequestConfig };
