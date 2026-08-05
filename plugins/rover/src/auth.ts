/**
 * Kerberos + OIDC token management for Rover authentication.
 *
 * Flow:
 * 1. Verify a Kerberos ticket exists (`klist -s`)
 * 2. SPNEGO against Keycloak via `curl --negotiate` to obtain an auth code
 * 3. Exchange the code for access + refresh tokens
 * 4. Proactively refresh before expiry; fall back to full Kerberos re-auth
 */

import { execFile } from "node:child_process";
import { promisify } from "node:util";

import type { OidcTokenResponse } from "./types.js";

const execFileAsync = promisify(execFile);

const KEYCLOAK_BASE = "https://auth.redhat.com/auth";
const REALM = "EmployeeIDP";
const CLIENT_ID = "rover-people-oidc";
const REDIRECT_URI = "https://rover.redhat.com/people/profile/";

const AUTH_URL = `${KEYCLOAK_BASE}/realms/${REALM}/protocol/openid-connect/auth`;
const TOKEN_URL = `${KEYCLOAK_BASE}/realms/${REALM}/protocol/openid-connect/token`;

/** Refresh this many ms before the access token actually expires. */
const REFRESH_SKEW_MS = 60_000;

const KERBEROS_HINT =
  "No valid Kerberos ticket found. Run `kinit` in a terminal, verify with `klist`, " +
  "then restart your IDE or MCP host so it inherits the ticket.";

export class AuthError extends Error {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = "AuthError";
  }
}

export class AuthManager {
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  /** Epoch ms when the access token should be treated as expired. */
  private accessTokenExpiresAt = 0;
  /** In-flight obtain/refresh so concurrent callers share one request. */
  private pending: Promise<string> | null = null;

  /**
   * Returns a valid Bearer access token, refreshing or re-authenticating as needed.
   */
  async getAccessToken(): Promise<string> {
    if (this.isAccessTokenFresh()) {
      return this.accessToken as string;
    }

    if (this.pending) {
      return this.pending;
    }

    this.pending = this.obtainAccessToken().finally(() => {
      this.pending = null;
    });

    return this.pending;
  }

  /** Clears cached tokens (forces Kerberos re-auth on next request). */
  clearTokens(): void {
    this.accessToken = null;
    this.refreshToken = null;
    this.accessTokenExpiresAt = 0;
  }

  /**
   * Marks the access token invalid so the next getAccessToken() refreshes
   * (or re-auths). Used after a Rover API 401.
   */
  invalidateAccessToken(): void {
    this.accessToken = null;
    this.accessTokenExpiresAt = 0;
  }

  /** Fail fast if the process has no valid Kerberos ticket. */
  async ensureKerberosTicket(): Promise<void> {
    await this.assertKerberosTicket();
  }

  private isAccessTokenFresh(): boolean {
    return (
      this.accessToken !== null &&
      Date.now() < this.accessTokenExpiresAt - REFRESH_SKEW_MS
    );
  }

  private async obtainAccessToken(): Promise<string> {
    if (this.refreshToken) {
      try {
        return await this.refreshAccessToken();
      } catch (error) {
        console.error(
          "Token refresh failed; falling back to Kerberos re-auth:",
          error instanceof Error ? error.message : error,
        );
        this.clearTokens();
      }
    }

    return this.authenticateWithKerberos();
  }

  /**
   * Full Kerberos → auth code → token exchange.
   */
  private async authenticateWithKerberos(): Promise<string> {
    await this.assertKerberosTicket();
    const code = await this.fetchAuthorizationCode();
    const tokens = await this.exchangeAuthorizationCode(code);
    return this.storeTokens(tokens);
  }

  private async refreshAccessToken(): Promise<string> {
    if (!this.refreshToken) {
      throw new AuthError("No refresh token available");
    }

    const body = new URLSearchParams({
      grant_type: "refresh_token",
      client_id: CLIENT_ID,
      refresh_token: this.refreshToken,
    });

    const tokens = await this.postToken(body);
    return this.storeTokens(tokens);
  }

  private storeTokens(tokens: OidcTokenResponse): string {
    if (!tokens.access_token) {
      throw new AuthError("Token response missing access_token");
    }

    this.accessToken = tokens.access_token;
    if (tokens.refresh_token) {
      this.refreshToken = tokens.refresh_token;
    }

    const expiresInSec = tokens.expires_in ?? 300;
    this.accessTokenExpiresAt = Date.now() + expiresInSec * 1000;

    return this.accessToken;
  }

  /**
   * `klist -s` exits 0 when a valid ticket exists.
   */
  private async assertKerberosTicket(): Promise<void> {
    try {
      await execFileAsync("klist", ["-s"]);
    } catch (error) {
      throw new AuthError(KERBEROS_HINT, { cause: error });
    }
  }

  /**
   * SPNEGO negotiate against Keycloak; capture the auth code from the redirect.
   */
  private async fetchAuthorizationCode(): Promise<string> {
    const authUrl = new URL(AUTH_URL);
    authUrl.searchParams.set("response_type", "code");
    authUrl.searchParams.set("client_id", CLIENT_ID);
    authUrl.searchParams.set("redirect_uri", REDIRECT_URI);
    authUrl.searchParams.set("scope", "openid");

    // Do not follow redirects (-L). Keycloak returns 302 with ?code= in Location.
    // --negotiate -u : uses the current Kerberos ticket (empty user/password).
    let stdout: string;
    try {
      const result = await execFileAsync(
        "curl",
        [
          "--silent",
          "--show-error",
          "--negotiate",
          "-u",
          ":",
          "--include",
          "--output",
          "-",
          authUrl.toString(),
        ],
        { maxBuffer: 2 * 1024 * 1024 },
      );
      stdout = result.stdout;
      if (result.stderr.trim()) {
        console.error("curl stderr:", result.stderr.trim());
      }
    } catch (error) {
      throw new AuthError(
        `Kerberos authentication request failed. ${KERBEROS_HINT}`,
        { cause: error },
      );
    }

    const location = extractHeader(stdout, "location");
    if (!location) {
      throw new AuthError(
        "Keycloak did not return a redirect Location header. " +
          "Kerberos negotiation may have failed. " +
          KERBEROS_HINT,
      );
    }

    const code = extractQueryParam(location, "code");
    if (!code) {
      const errorParam = extractQueryParam(location, "error");
      const errorDesc = extractQueryParam(location, "error_description");
      throw new AuthError(
        errorParam
          ? `Keycloak auth error: ${errorParam}${errorDesc ? ` (${errorDesc})` : ""}`
          : `Redirect Location missing authorization code: ${location}`,
      );
    }

    return code;
  }

  private async exchangeAuthorizationCode(code: string): Promise<OidcTokenResponse> {
    const body = new URLSearchParams({
      grant_type: "authorization_code",
      client_id: CLIENT_ID,
      code,
      redirect_uri: REDIRECT_URI,
    });

    return this.postToken(body);
  }

  private async postToken(body: URLSearchParams): Promise<OidcTokenResponse> {
    let response: Response;
    try {
      response = await fetch(TOKEN_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body,
      });
    } catch (error) {
      throw new AuthError("Failed to reach Keycloak token endpoint", {
        cause: error,
      });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new AuthError(
        `Token endpoint returned HTTP ${response.status}: ${text.slice(0, 500)}`,
      );
    }

    let parsed: OidcTokenResponse;
    try {
      parsed = JSON.parse(text) as OidcTokenResponse;
    } catch (error) {
      throw new AuthError("Token endpoint returned non-JSON response", {
        cause: error,
      });
    }

    return parsed;
  }
}

function extractHeader(rawHttp: string, name: string): string | null {
  const lower = name.toLowerCase();
  // Handle possible multiple header blocks (e.g. 100 Continue); take the last Location.
  let found: string | null = null;
  for (const line of rawHttp.split(/\r?\n/)) {
    const idx = line.indexOf(":");
    if (idx === -1) continue;
    const headerName = line.slice(0, idx).trim().toLowerCase();
    if (headerName === lower) {
      found = line.slice(idx + 1).trim();
    }
  }
  return found;
}

function extractQueryParam(urlOrPath: string, key: string): string | null {
  try {
    const url = urlOrPath.startsWith("http")
      ? new URL(urlOrPath)
      : new URL(urlOrPath, "https://rover.redhat.com");
    return url.searchParams.get(key);
  } catch {
    const match = new RegExp(`[?&#]${key}=([^&#]+)`).exec(urlOrPath);
    return match ? decodeURIComponent(match[1]) : null;
  }
}
