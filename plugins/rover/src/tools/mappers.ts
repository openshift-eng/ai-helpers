/**
 * Map Rover API person objects onto tool-facing summaries.
 */

import type { RoverClient } from "../rover-client.js";
import type { FullProfile, PersonDetails, PersonSummary } from "../types.js";

/** Loose person-shaped object from any Rover endpoint. */
export interface PersonFields {
  uid?: unknown;
  name?: unknown;
  displayName?: unknown;
  mail?: unknown;
  rhatJobTitle?: unknown;
  businessCardTitle?: unknown;
  rhatLocation?: unknown;
  formerEmployee?: unknown;
}

function asOptionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

export function toPersonSummary(person: PersonFields): PersonSummary {
  const summary: PersonSummary = {
    uid: asOptionalString(person.uid),
    name:
      asOptionalString(person.name) ?? asOptionalString(person.displayName),
    title:
      asOptionalString(person.rhatJobTitle) ??
      asOptionalString(person.businessCardTitle),
    email: asOptionalString(person.mail),
    location: asOptionalString(person.rhatLocation),
  };

  if (typeof person.formerEmployee === "boolean") {
    summary.formerEmployee = person.formerEmployee;
  }

  return summary;
}

export function toPersonDetails(profile: FullProfile): PersonDetails {
  const manager = profile.manager
    ? toPersonSummary(profile.manager)
    : undefined;

  const costCenter = [
    asOptionalString(profile.rhatCostCenter),
    asOptionalString(profile.rhatCostCenterDesc),
  ]
    .filter(Boolean)
    .join(" — ");

  return {
    ...toPersonSummary(profile),
    manager,
    costCenter: costCenter || undefined,
    org: asOptionalString(profile.organizationName),
    hireDate: asOptionalString(profile.rhatHireDate),
    bio: asOptionalString(profile.rhatBio),
    timezone: asOptionalString(profile.preferredTimezone),
  };
}

export function looksLikeEmail(value: string): boolean {
  return value.includes("@");
}

/** Resolve a Kerberos uid or email to a uid. Returns undefined if email has no match. */
export async function resolveUid(
  client: RoverClient,
  kerberosIdOrEmail: string,
): Promise<string | undefined> {
  if (!looksLikeEmail(kerberosIdOrEmail)) {
    return kerberosIdOrEmail;
  }
  const matches = await client.searchAdvanced({ mail: kerberosIdOrEmail });
  return asOptionalString(matches[0]?.uid);
}
