/**
 * List Rover projects, communities, and badges for a person.
 *
 * Rover has no dedicated group-membership REST endpoint; this uses the
 * closest available fields from the full profile.
 */

import {
  RoverNotFoundError,
  type RoverClient,
} from "../rover-client.js";
import type { GroupsResult } from "../types.js";
import { resolveUid } from "./mappers.js";

export type GetGroupsResult =
  | { found: true; groups: GroupsResult }
  | { found: false; message: string };

export async function getGroups(
  client: RoverClient,
  kerberosIdOrEmail: string,
): Promise<GetGroupsResult> {
  const input = kerberosIdOrEmail.trim();
  if (!input) {
    return { found: false, message: "No Kerberos ID or email provided." };
  }

  try {
    const uid = await resolveUid(client, input);
    if (!uid) {
      return {
        found: false,
        message: `No person found for "${input}".`,
      };
    }

    const profile = await client.getProfile(uid);
    const groups: GroupsResult = {
      uid: profile.uid ?? uid,
      projects: profile.rhatProjects ?? [],
      communities: profile.rhatCommunities ?? [],
      badges: profile.badgePersons ?? [],
    };

    return { found: true, groups };
  } catch (error) {
    if (error instanceof RoverNotFoundError) {
      return {
        found: false,
        message: `No person found for "${input}".`,
      };
    }
    throw error;
  }
}
