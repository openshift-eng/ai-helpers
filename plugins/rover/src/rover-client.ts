/**
 * Rover REST API client — authenticated fetch wrapper around
 * https://rover.redhat.com/people/rest/
 */

import type { AuthManager } from "./auth.js";
import type {
  AdvancedSearchCriteria,
  FullProfile,
  HierarchyEntry,
  RoverApiResponse,
  SimpleProfile,
  Subordinate,
} from "./types.js";

const ROVER_BASE_URL = "https://rover.redhat.com/people/rest";

export class RoverApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly body?: string,
  ) {
    super(message);
    this.name = "RoverApiError";
  }
}

export class RoverNotFoundError extends RoverApiError {
  constructor(message: string, body?: string) {
    super(message, 404, body);
    this.name = "RoverNotFoundError";
  }
}

export class RoverClient {
  constructor(private readonly auth: AuthManager) {}

  /** Current authenticated user's Kerberos uid. */
  async getUserPrincipal(): Promise<string> {
    return this.get<string>("/user/userPrincipal");
  }

  async getProfile(uid: string): Promise<FullProfile> {
    return this.get<FullProfile>(`/user/${encodeURIComponent(uid)}/profile`);
  }

  async getSimpleProfile(uid: string): Promise<SimpleProfile> {
    return this.get<SimpleProfile>(`/user/${encodeURIComponent(uid)}/simple`);
  }

  async getSubordinates(uid: string): Promise<Subordinate[]> {
    return this.get<Subordinate[]>(
      `/user/${encodeURIComponent(uid)}/subordinates`,
    );
  }

  async getIndirectSubordinates(uid: string): Promise<Subordinate[]> {
    return this.get<Subordinate[]>(
      `/user/${encodeURIComponent(uid)}/subordinates/indirect`,
    );
  }

  async getHierarchy(uid: string): Promise<HierarchyEntry[]> {
    return this.get<HierarchyEntry[]>(
      `/user/${encodeURIComponent(uid)}/hierarchy`,
    );
  }

  async searchSimple(criteria: string): Promise<SimpleProfile[]> {
    const params = new URLSearchParams({ criteria });
    return this.get<SimpleProfile[]>(`/search/simple?${params}`);
  }

  async searchAdvanced(
    criteria: AdvancedSearchCriteria,
  ): Promise<SimpleProfile[]> {
    const params = new URLSearchParams({
      criteria: JSON.stringify(criteria),
    });
    return this.get<SimpleProfile[]>(`/search/advanced?${params}`);
  }

  private async get<T>(path: string): Promise<T> {
    return this.request<T>(path, false);
  }

  /**
   * GET with Bearer auth. On 401, invalidate the access token, renew, and retry once.
   */
  private async request<T>(path: string, isRetry: boolean): Promise<T> {
    const token = await this.auth.getAccessToken();
    const url = `${ROVER_BASE_URL}${path}`;

    let response: Response;
    try {
      response = await fetch(url, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json",
        },
      });
    } catch (error) {
      throw new RoverApiError(
        `Failed to reach Rover API at ${path}: ${error instanceof Error ? error.message : String(error)}`,
        0,
      );
    }

    if (response.status === 401 && !isRetry) {
      this.auth.invalidateAccessToken();
      return this.request<T>(path, true);
    }

    const text = await response.text();

    if (response.status === 404) {
      throw new RoverNotFoundError(`Rover resource not found: ${path}`, text);
    }

    if (!response.ok) {
      throw new RoverApiError(
        `Rover API HTTP ${response.status} for ${path}: ${text.slice(0, 500)}`,
        response.status,
        text,
      );
    }

    let parsed: RoverApiResponse<T>;
    try {
      parsed = JSON.parse(text) as RoverApiResponse<T>;
    } catch {
      throw new RoverApiError(
        `Rover API returned non-JSON for ${path}`,
        response.status,
        text.slice(0, 500),
      );
    }

    if (!parsed || !("result" in parsed) || parsed.result === null || parsed.result === undefined) {
      throw new RoverNotFoundError(
        `Rover resource not found: ${path}`,
        text.slice(0, 500),
      );
    }

    return parsed.result;
  }
}
