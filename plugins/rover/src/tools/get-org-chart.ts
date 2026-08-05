/**
 * Get management chain and direct reports for a person.
 */

import {
  RoverNotFoundError,
  type RoverClient,
} from "../rover-client.js";
import type { OrgChartResult, PersonSummary } from "../types.js";
import { resolveUid, toPersonSummary } from "./mappers.js";

export type GetOrgChartResult =
  | { found: true; orgChart: OrgChartResult }
  | { found: false; message: string };

export interface GetOrgChartOptions {
  /** When true, also fetch all indirect reports. Default: false. */
  includeIndirect?: boolean;
}

export async function getOrgChart(
  client: RoverClient,
  kerberosIdOrEmail: string,
  options: GetOrgChartOptions = {},
): Promise<GetOrgChartResult> {
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

    const [hierarchy, directReports, indirectReports] = await Promise.all([
      client.getHierarchy(uid),
      client.getSubordinates(uid),
      options.includeIndirect
        ? client.getIndirectSubordinates(uid)
        : Promise.resolve(undefined),
    ]);

    // hierarchy[0] = self, [1..] = managers up to CEO
    const self = hierarchy[0];
    const person: PersonSummary = self
      ? toPersonSummary(self)
      : { uid };

    const managerChain = hierarchy.slice(1).map(toPersonSummary);

    const orgChart: OrgChartResult = {
      person,
      managerChain,
      directReports: directReports.map(toPersonSummary),
    };

    if (indirectReports) {
      orgChart.indirectReports = indirectReports.map(toPersonSummary);
    }

    return { found: true, orgChart };
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
