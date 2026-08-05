/**
 * List all members reporting to a manager (direct and indirect).
 */

import {
  RoverNotFoundError,
  type RoverClient,
} from "../rover-client.js";
import type { PersonSummary, TeamResult } from "../types.js";
import { resolveUid, toPersonSummary } from "./mappers.js";

export type GetTeamResult =
  | { found: true; team: TeamResult }
  | { found: false; message: string };

export interface GetTeamOptions {
  /** When true (default), include indirect reports as well as directs. */
  includeIndirect?: boolean;
}

export async function getTeam(
  client: RoverClient,
  managerKerberosIdOrEmail: string,
  options: GetTeamOptions = {},
): Promise<GetTeamResult> {
  const includeIndirect = options.includeIndirect ?? true;
  const input = managerKerberosIdOrEmail.trim();
  if (!input) {
    return { found: false, message: "No manager Kerberos ID or email provided." };
  }

  try {
    const uid = await resolveUid(client, input);
    if (!uid) {
      return {
        found: false,
        message: `No person found for "${input}".`,
      };
    }

    const [simple, directs, indirects] = await Promise.all([
      client.getSimpleProfile(uid),
      client.getSubordinates(uid),
      includeIndirect
        ? client.getIndirectSubordinates(uid)
        : Promise.resolve([]),
    ]);

    const byUid = new Map<string, PersonSummary>();
    for (const person of [...directs, ...indirects]) {
      const summary = toPersonSummary(person);
      if (summary.uid) {
        byUid.set(summary.uid, summary);
      }
    }

    const team: TeamResult = {
      manager: toPersonSummary(simple),
      members: [...byUid.values()],
    };

    return { found: true, team };
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
