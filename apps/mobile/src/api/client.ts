/**
 * Typed fetch wrapper for the Curiosity API (docs/spec/06 §6.3).
 *
 * - Adds auth, app-version and platform headers.
 * - On 401 UNAUTHENTICATED it refreshes the session once (one shared in-flight
 *   refresh for concurrent requests) and retries the request.
 * - Throws ApiError with the server's error code, or NETWORK_ERROR when offline.
 */
import { ApiError, NETWORK_ERROR } from "./errors";
import type { Tokens, TokensResponse } from "./types";

export type TokenStore = {
  get(): Tokens | null;
  set(tokens: Tokens | null): Promise<void>;
};

export type ApiClientOptions = {
  baseUrl: string;
  appVersion: string;
  platform: string;
  tokenStore: TokenStore;
  /** Called once when the session cannot be refreshed (user must sign in again). */
  onSessionExpired?: () => void;
  fetchImpl?: typeof fetch;
};

export type RequestOptions = {
  body?: unknown;
  /** Send the bearer token (default true). */
  auth?: boolean;
};

type Method = "GET" | "POST" | "PATCH" | "DELETE";

export class ApiClient {
  private refreshing: Promise<boolean> | null = null;
  private sessionExpired: () => void;
  private readonly fetchImpl: typeof fetch;

  constructor(private readonly options: ApiClientOptions) {
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.sessionExpired = options.onSessionExpired ?? (() => undefined);
  }

  /** Replace the handler called when the session cannot be refreshed. */
  setSessionExpiredHandler(handler: () => void): void {
    this.sessionExpired = handler;
  }

  get<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>("GET", path, options);
  }

  post<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>("POST", path, { ...options, body });
  }

  patch<T>(path: string, body: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>("PATCH", path, { ...options, body });
  }

  delete<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>("DELETE", path, { ...options, body });
  }

  async request<T>(method: Method, path: string, options: RequestOptions = {}): Promise<T> {
    const auth = options.auth ?? true;
    const response = await this.send(method, path, options.body, auth);
    if (response.status === 401 && auth && this.options.tokenStore.get()) {
      const body = await readJson(response);
      const expired = ApiError.fromEnvelope(401, body);
      if (expired.code !== "UNAUTHENTICATED") throw expired;
      if (!(await this.refresh())) throw expired;
      return this.parse<T>(await this.send(method, path, options.body, auth));
    }
    return this.parse<T>(response);
  }

  /** Exchange the refresh token. Concurrent callers share one request. */
  refresh(): Promise<boolean> {
    if (!this.refreshing) {
      this.refreshing = this.doRefresh().finally(() => {
        this.refreshing = null;
      });
    }
    return this.refreshing;
  }

  private async doRefresh(): Promise<boolean> {
    const current = this.options.tokenStore.get();
    if (!current) return false;
    try {
      const response = await this.send(
        "POST",
        "/v1/auth/refresh",
        { refresh_token: current.refresh_token },
        false,
      );
      if (response.ok) {
        const body = (await response.json()) as TokensResponse;
        await this.options.tokenStore.set(body.tokens);
        return true;
      }
      if (response.status === 401) {
        await this.options.tokenStore.set(null);
        this.sessionExpired();
      }
      return false;
    } catch {
      return false; // offline: keep the session and let the caller report the network error
    }
  }

  private async send(
    method: Method,
    path: string,
    body: unknown,
    auth: boolean,
  ): Promise<Response> {
    const headers: Record<string, string> = {
      Accept: "application/json",
      "X-App-Version": this.options.appVersion,
      "X-Platform": this.options.platform,
    };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const token = this.options.tokenStore.get();
    if (auth && token) headers.Authorization = `Bearer ${token.access_token}`;
    try {
      return await this.fetchImpl(`${this.options.baseUrl}${path}`, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new ApiError(0, NETWORK_ERROR, "Network request failed");
    }
  }

  private async parse<T>(response: Response): Promise<T> {
    if (response.status === 204) return undefined as T;
    const body = await readJson(response);
    if (!response.ok) throw ApiError.fromEnvelope(response.status, body);
    return body as T;
  }
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}
