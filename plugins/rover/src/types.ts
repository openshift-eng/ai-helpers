/**
 * Shared TypeScript interfaces for Rover People API data and tool outputs.
 */

/** Envelope returned by all Rover REST endpoints. */
export interface RoverApiResponse<T> {
  result: T;
}

// ---------------------------------------------------------------------------
// Nested profile objects
// ---------------------------------------------------------------------------

export type RoverProjectType =
  | "business_unit"
  | "component"
  | "product"
  | "role"
  | string;

export interface RoverProject {
  id?: string;
  type?: RoverProjectType;
  name?: string;
  [key: string]: unknown;
}

export interface RoverBadge {
  badgeId?: string;
  imageName?: string;
  tooltip?: string;
  category?: string;
  [key: string]: unknown;
}

/** Community affiliation as returned on a profile (shape varies). */
export type RoverCommunity = string | Record<string, unknown>;

export interface RoverManagerSummary {
  rhatUuid?: string;
  uid?: string;
  name?: string;
  displayName?: string;
  mail?: string;
  rhatJobTitle?: string;
  employeeType?: string;
  [key: string]: unknown;
}

export interface SocialUrl {
  type?: string;
  url?: string;
  [key: string]: unknown;
}

export interface ChatPlatform {
  type?: string;
  handle?: string;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Profile shapes
// ---------------------------------------------------------------------------

/**
 * Lightweight person object from `/user/{uid}/simple` and simple search.
 */
export interface SimpleProfile {
  rhatUuid?: string;
  uid?: string;
  name?: string;
  displayName?: string;
  preferredLastName?: string;
  mail?: string;
  rhatJobTitle?: string;
  businessCardTitle?: string;
  rhatLocation?: string;
  rhatGeo?: string;
  country?: string;
  managerUuid?: string;
  employeeType?: string;
  formerEmployee?: boolean;
  isManager?: boolean;
  financialPartyId?: string;
  [key: string]: unknown;
}

/**
 * Full profile from `/user/{uid}/profile`.
 */
export interface FullProfile {
  // Identity
  rhatUuid?: string;
  uid?: string;
  uidNumber?: string | number;
  name?: string;
  displayName?: string;
  givenName?: string;
  sn?: string;
  preferredLastName?: string;

  // Contact
  mail?: string;
  mobile?: string;
  aliases?: string[];

  // Job
  rhatJobTitle?: string;
  businessCardTitle?: string;
  rhatJobRole?: string;
  jobCode?: string;
  employeeNumber?: string;
  employeeType?: string;

  // Location
  l?: string;
  st?: string;
  countryCode?: string;
  countryCodeThreeChar?: string;
  rhatLocation?: string;
  rhatGeo?: string;
  workProfile?: string;
  officeLocation?: string;
  postalCode?: string;
  street?: string;

  // Organization
  organizationName?: string;
  rhatCostCenter?: string;
  rhatCostCenterDesc?: string;
  managerUuid?: string;

  // Dates
  rhatHireDate?: string;
  rhatTermDate?: string;

  // Status
  formerEmployee?: boolean;
  deleted?: boolean;
  isManager?: boolean;

  // Relationships
  manager?: RoverManagerSummary;
  reports?: SimpleProfile[];

  // Projects / social / communities / badges
  rhatProjects?: RoverProject[];
  socialUrls?: SocialUrl[];
  chatPlatforms?: ChatPlatform[];
  rhatCommunities?: RoverCommunity[];
  badgePersons?: RoverBadge[];

  // Bio / prefs / misc
  rhatBio?: string;
  preferredTimezone?: string;
  rhatBJNMeetingID?: string;
  rhatBJNUserName?: string;
  ipaSshPubKeys?: string[];

  [key: string]: unknown;
}

/**
 * Entry from `/user/{uid}/subordinates` or `/subordinates/indirect`.
 */
export interface Subordinate {
  rhatUuid?: string;
  uid?: string;
  name?: string;
  mail?: string;
  rhatJobTitle?: string;
  businessCardTitle?: string;
  rhatLocation?: string;
  roomNumber?: string;
  [key: string]: unknown;
}

/**
 * Entry from `/user/{uid}/hierarchy` (index 0 = self, last = CEO).
 */
export interface HierarchyEntry {
  rhatUuid?: string;
  uid?: string;
  name?: string;
  mail?: string;
  rhatJobTitle?: string;
  displayName?: string;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

/** Verified advanced-search criteria fields. */
export interface AdvancedSearchCriteria {
  name?: string;
  mail?: string;
  managerUid?: string;
  uid?: string;
  rhatCostCenter?: string;
  rhatGeo?: string;
  rhatLocation?: string;
  countryCode?: string;
  rhatJobTitle?: string;
  employeeNumber?: string;
  workProfile?: string;
  [key: string]: string | undefined;
}

// ---------------------------------------------------------------------------
// Auth (Keycloak OIDC) — used by Phase 2
// ---------------------------------------------------------------------------

export interface OidcTokenResponse {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
  expires_in?: number;
  refresh_expires_in?: number;
  id_token?: string;
  scope?: string;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Tool-facing result shapes (normalized for MCP responses)
// ---------------------------------------------------------------------------

export interface PersonSummary {
  uid?: string;
  name?: string;
  title?: string;
  email?: string;
  location?: string;
  /** True when Rover marks the person as a former employee. */
  formerEmployee?: boolean;
}

export interface PersonDetails extends PersonSummary {
  manager?: PersonSummary;
  costCenter?: string;
  org?: string;
  hireDate?: string;
  bio?: string;
  timezone?: string;
}

export interface OrgChartResult {
  person: PersonSummary;
  managerChain: PersonSummary[];
  directReports: PersonSummary[];
  indirectReports?: PersonSummary[];
}

export interface TeamResult {
  manager: PersonSummary;
  members: PersonSummary[];
}

export interface GroupsResult {
  uid: string;
  projects: RoverProject[];
  communities: RoverCommunity[];
  badges: RoverBadge[];
}
