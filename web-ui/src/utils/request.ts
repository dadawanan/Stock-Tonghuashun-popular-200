import { message } from 'antd';

const BASE_URL = ''

interface ApiResponse<T = any> {
  code: number;
  msg: string;
  data: T;
}

interface RequestConfig extends RequestInit {
  params?: Record<string, any>;
  showError?: boolean;
}

class HttpClient {
  private baseURL: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  private buildURL(url: string, params?: Record<string, any>): string {
    const fullURL = url.startsWith('http') ? url : `${this.baseURL}${url}`;
    
    if (!params || Object.keys(params).length === 0) {
      return fullURL;
    }

    const queryString = Object.entries(params)
      .filter(([_, value]) => value !== undefined && value !== null)
      .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
      .join('&');

    return queryString ? `${fullURL}?${queryString}` : fullURL;
  }

  private async handleResponse<T>(response: Response, showError: boolean = true): Promise<T> {
    if (!response.ok) {
      const errorText = await response.text().catch(() => '');
      let errorMessage = `HTTP Error: ${response.status} ${response.statusText}`;
      
      try {
        const errorData = JSON.parse(errorText);
        errorMessage = errorData.detail || errorData.msg || errorMessage;
      } catch {
        errorMessage = errorText || errorMessage;
      }

      if (showError) {
        message.error(errorMessage);
      }

      throw new Error(errorMessage);
    }

    const data = await response.json();
    
    if (data.code !== undefined && data.code !== 0) {
      const errorMsg = data.msg || '请求失败';
      if (showError) {
        message.error(errorMsg);
      }
      throw new Error(errorMsg);
    }

    return data.data;
  }

  private getHeaders(headers?: HeadersInit): HeadersInit {
    return {
      'Content-Type': 'application/json',
      ...headers,
    };
  }

  async get<T = any>(url: string, config?: RequestConfig): Promise<T> {
    const { params, showError = true, ...init } = config || {};
    const fullURL = this.buildURL(url, params);

    try {
      const response = await fetch(fullURL, {
        method: 'GET',
        headers: this.getHeaders(init.headers),
        ...init,
      });
      return await this.handleResponse<T>(response, showError);
    } catch (error) {
      console.error(`GET ${url} failed:`, error);
      throw error;
    }
  }

  async post<T = any>(url: string, data?: any, config?: RequestConfig): Promise<T> {
    const { showError = true, ...init } = config || {};

    try {
      const response = await fetch(this.buildURL(url), {
        method: 'POST',
        headers: this.getHeaders(init.headers),
        body: data ? JSON.stringify(data) : undefined,
        ...init,
      });
      return await this.handleResponse<T>(response, showError);
    } catch (error) {
      console.error(`POST ${url} failed:`, error);
      throw error;
    }
  }

  async put<T = any>(url: string, data?: any, config?: RequestConfig): Promise<T> {
    const { showError = true, ...init } = config || {};

    try {
      const response = await fetch(this.buildURL(url), {
        method: 'PUT',
        headers: this.getHeaders(init.headers),
        body: data ? JSON.stringify(data) : undefined,
        ...init,
      });
      return await this.handleResponse<T>(response, showError);
    } catch (error) {
      console.error(`PUT ${url} failed:`, error);
      throw error;
    }
  }

  async delete<T = any>(url: string, config?: RequestConfig): Promise<T> {
    const { params, showError = true, ...init } = config || {};
    const fullURL = this.buildURL(url, params);

    try {
      const response = await fetch(fullURL, {
        method: 'DELETE',
        headers: this.getHeaders(init.headers),
        ...init,
      });
      return await this.handleResponse<T>(response, showError);
    } catch (error) {
      console.error(`DELETE ${url} failed:`, error);
      throw error;
    }
  }
}

const http = new HttpClient(BASE_URL);

export default http;

export type { ApiResponse, RequestConfig };