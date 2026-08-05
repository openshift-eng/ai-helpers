/**
 * Look up a person by Kerberos ID (uid) or email address.
 */

import {
  RoverNotFoundError,
  type RoverClient,
} from "../rover-client.js";
import type { PersonDetails } from "../types.js";
import { resolveUid, toPersonDetails } from "./mappers.js";

export type GetPersonResult =
  | { found: true; person: PersonDetails }
  | { found: false; message: string };

export async function getPerson(
  client: RoverClient,
  kerberosIdOrEmail: string,
): Promise<GetPersonResult> {
  const input = kerberosIdOrEmail.trim();
  if (!input) {
    return { found: false, message: "No Kerberos ID or email provided." };
  }

  try {
    const uid = await resolveUid(client, input);
    if (!uid) {
      return {
        found: false,
        message: `No person found with email "${input}".`,
      };
    }

    const profile = await client.getProfile(uid);
    return { found: true, person: toPersonDetails(profile) };
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
