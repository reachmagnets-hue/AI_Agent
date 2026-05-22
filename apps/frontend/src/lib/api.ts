/**
 * Production-ready API client with error handling, retries, and caching.
 */

import axios, { AxiosInstance, AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios';

declare module 'axios' {
  export interface AxiosRequestConfig {
    retries?: number;
  }
  export interface InternalAxiosRequestConfig {
    retries?: number;
  }
}

// Environment configuration
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Custom error classes
export class APIError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public errorCode?: string,
    public details?: any
  ) {
    super(message);
    this.name = 'APIError';
  }
}

export class NetworkError extends Error {
  constructor(message: string = 'Network error occurred') {
    super(message);
    this.name = 'NetworkError';
  }
}

// API Response wrapper
export interface APIResponse<T> {
  data: T;
  success: boolean;
  error?: {
    message: string;
    statusCode?: number;
    errorCode?: string;
    details?: any;
  };
}

// Retry configuration
export interface RetryConfig {
  maxRetries: number;
  retryDelay: number; // ms
  retryOn: number[]; // Status codes to retry
}

const defaultRetryConfig: RetryConfig = {
  maxRetries: 3,
  retryDelay: 1000,
  retryOn: [408, 429, 500, 502, 503, 504]
};

// Cache implementation
class SimpleCache {
  private cache = new Map<string, { data: any; timestamp: number; ttl: number }>();

  set(key: string, data: any, ttl: number = 300000) {
    this.cache.set(key, { data, timestamp: Date.now(), ttl });
  }

  get<T>(key: string): T | null {
    const cached = this.cache.get(key);
    if (!cached) return null;

    const age = Date.now() - cached.timestamp;
    if (age > cached.ttl) {
      this.cache.delete(key);
      return null;
    }

    return cached.data;
  }

  clear() {
    this.cache.clear();
  }

  delete(key: string) {
    this.cache.delete(key);
  }
}

const globalCache = new SimpleCache();

// API Client class
class APIClient {
  private axiosInstance: AxiosInstance;
  private cache: SimpleCache;
  private retryConfig: RetryConfig;

  constructor(
    baseURL: string = API_BASE_URL,
    retryConfig: RetryConfig = defaultRetryConfig
  ) {
    this.axiosInstance = axios.create({
      baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.cache = globalCache;
    this.retryConfig = retryConfig;

    // Request interceptor
    this.axiosInstance.interceptors.request.use(
      (config) => {
        // Add auth token if available
        const token = this.getAuthToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor
    this.axiosInstance.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const config = error.config as (InternalAxiosRequestConfig & { retries?: number }) | undefined;

        // Don't retry if no config or max retries reached
        if (!config || (config.retries ?? 0) >= this.retryConfig.maxRetries) {
          return Promise.reject(this.formatError(error));
        }

        // Check if should retry
        const statusCode = error.response?.status;
        if (
          statusCode &&
          this.retryConfig.retryOn.includes(statusCode) &&
          (config.retries ?? 0) < this.retryConfig.maxRetries
        ) {
          config.retries = (config.retries ?? 0) + 1;
          const delay = this.retryConfig.retryDelay * Math.pow(2, config.retries - 1);

          console.warn(`Retrying request (${config.retries}/${this.retryConfig.maxRetries}) after ${delay}ms`);

          await new Promise(resolve => setTimeout(resolve, delay));
          return this.axiosInstance(config as any);
        }

        return Promise.reject(this.formatError(error));
      }
    );
  }

  private formatError(error: AxiosError): APIError {
    if (error.code === 'ECONNABORTED') {
      return new APIError('Request timeout', 408, 'TIMEOUT_ERROR');
    }

    if (error.code === 'ERR_NETWORK') {
      return new NetworkError();
    }

    const response = error.response;
    if (response) {
      const errorData = (response.data as any)?.error || response.data;
      return new APIError(
        errorData?.message || error.message,
        response.status,
        errorData?.errorCode || `HTTP_${response.status}`,
        errorData?.details
      );
    }

    return new APIError(error.message);
  }

  private getAuthToken(): string | null {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('auth_token');
    }
    return null;
  }

  // Generic request methods
  async request<T>(
    method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
    url: string,
    data?: any,
    useCache: boolean = false,
    cacheKey?: string,
    cacheTTL: number = 300000
  ): Promise<APIResponse<T>> {
    const requestKey = cacheKey || `${method}:${url}:${JSON.stringify(data)}`;

    if (useCache && method === 'GET') {
      const cached = this.cache.get<T>(requestKey);
      if (cached) {
        return { data: cached, success: true };
      }
    }

    try {
      const response: AxiosResponse<T> = await this.axiosInstance({
        method,
        url,
        data,
        retries: 0
      } as any);

      if (useCache && method === 'GET') {
        this.cache.set(requestKey, response.data, cacheTTL);
      }

      return {
        data: response.data,
        success: true
      };
    } catch (error) {
      if (error instanceof APIError) {
        return {
          data: null as any,
          success: false,
          error: {
            message: error.message,
            statusCode: error.statusCode,
            errorCode: error.errorCode,
            details: error.details
          }
        };
      }
      throw error;
    }
  }

  // Convenience methods
  get<T>(url: string, params?: any, useCache: boolean = false): Promise<APIResponse<T>> {
    return this.request<T>('GET', url, params, useCache);
  }

  post<T>(url: string, data?: any): Promise<APIResponse<T>> {
    return this.request<T>('POST', url, data);
  }

  put<T>(url: string, data?: any): Promise<APIResponse<T>> {
    return this.request<T>('PUT', url, data);
  }

  patch<T>(url: string, data?: any): Promise<APIResponse<T>> {
    return this.request<T>('PATCH', url, data);
  }

  delete<T>(url: string): Promise<APIResponse<T>> {
    return this.request<T>('DELETE', url);
  }

  // Cache management
  clearCache(pattern?: string): void {
    if (pattern) {
      // Clear specific cache entries
      const keys = Array.from(this.cache['cache'].keys());
      keys.forEach(key => {
        if (key.includes(pattern)) {
          this.cache.delete(key);
        }
      });
    } else {
      this.cache.clear();
    }
  }

  setAuthToken(token: string): void {
    if (typeof window !== 'undefined') {
      localStorage.setItem('auth_token', token);
    }
  }

  removeAuthToken(): void {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('auth_token');
    }
  }
}

// Create singleton instance
export const apiClient = new APIClient();

// API Endpoints
export const contactsApi = {
  getAll: (page = 1, limit = 20, status?: string, search?: string, campaignId?: string) => {
    const params = new URLSearchParams();
    params.append('page', page.toString());
    params.append('limit', limit.toString());
    if (status) params.append('status', status);
    if (search) params.append('search', search);
    if (campaignId) params.append('campaign_id', campaignId);

    return apiClient.get(`/api/v1/leads/?${params.toString()}`, undefined, true);
  },

  getById: (id: string) => apiClient.get(`/api/v1/leads/${id}`),

  create: (data: any) => apiClient.post('/api/v1/leads/', data),

  update: (id: string, data: any) => apiClient.patch(`/api/v1/leads/${id}`, data),

  delete: (id: string) => apiClient.delete(`/api/v1/leads/${id}`),

  importBulk: (contacts: any[]) => apiClient.post('/api/v1/leads/bulk', { leads: contacts }),

  importCSV: (formData: FormData) => {
    return fetch(`${API_BASE_URL}/api/v1/leads/import-csv`, {
      method: 'POST',
      body: formData,
    }).then(r => r.json());
  },

  exportCSV: () => apiClient.get('/api/v1/leads/export'),
};

export const campaignsApi = {
  getAll: (page = 1, limit = 20, status?: string) => {
    const params = new URLSearchParams();
    params.append('page', page.toString());
    params.append('limit', limit.toString());
    if (status) params.append('status', status);

    return apiClient.get(`/api/v1/campaigns/?${params.toString()}`);
  },

  getById: (id: string) => apiClient.get(`/api/v1/campaigns/${id}`),

  create: (data: any) => apiClient.post('/api/v1/campaigns/', data),

  start: (id: string) => apiClient.post(`/api/v1/campaigns/${id}/start`),

  pause: (id: string) => apiClient.post(`/api/v1/campaigns/${id}/pause`),

  resume: (id: string) => apiClient.post(`/api/v1/campaigns/${id}/resume`),

  complete: (id: string) => apiClient.post(`/api/v1/campaigns/${id}/complete`),

  getLeads: (id: string, page = 1, limit = 25) =>
    apiClient.get(`/api/v1/campaigns/${id}/leads?page=${page}&limit=${limit}`),

  getCalls: (id: string) => apiClient.get(`/api/v1/campaigns/${id}/calls`),

  getStats: (id: string) => apiClient.get(`/api/v1/campaigns/${id}/stats`),
};

export const callsApi = {
  getAll: (page = 1, limit = 20, campaignId?: string) => {
    const params = new URLSearchParams();
    params.append('page', page.toString());
    params.append('limit', limit.toString());
    if (campaignId) params.append('campaign_id', campaignId);

    return apiClient.get(`/api/v1/calls/?${params.toString()}`, undefined, true);
  },

  getById: (id: string) => apiClient.get(`/api/v1/calls/${id}`),

  getStats: () => apiClient.get('/api/v1/calls/dashboard/stats'),
  
  getOverview: () => apiClient.get('/api/v1/calls/stats/overview'),
};

export const appointmentsApi = {
  getAll: (page = 1, limit = 20, status?: string) => {
    const params = new URLSearchParams();
    params.append('page', page.toString());
    params.append('limit', limit.toString());
    if (status) params.append('status', status);

    return apiClient.get(`/api/v1/appointments/?${params.toString()}`, undefined, true);
  },

  getById: (id: string) => apiClient.get(`/api/v1/appointments/${id}`),

  getUpcoming: () => apiClient.get('/api/v1/appointments/upcoming'),
};

export default apiClient;