#!/usr/bin/env node
/**
 * Rover People MCP server — stdio entry point.
 *
 * Exposes Rover directory tools to MCP clients (Claude Code, Cursor, etc.).
 * Authenticates with the user's Kerberos ticket via Keycloak OIDC.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

import { AuthError, AuthManager } from "./auth.js";
import { RoverApiError, RoverClient } from "./rover-client.js";
import { getGroups } from "./tools/get-groups.js";
import { getOrgChart } from "./tools/get-org-chart.js";
import { getPerson } from "./tools/get-person.js";
import { getTeam } from "./tools/get-team.js";
import { searchPeople } from "./tools/search-people.js";

const SERVER_NAME = "rover-mcp";
const SERVER_VERSION = "0.1.0";

const nonEmptyString = (description: string) =>
  z.string().trim().min(1).describe(description);

function jsonText(data: unknown): { content: [{ type: "text"; text: string }] } {
  return {
    content: [{ type: "text", text: JSON.stringify(data, null, 2) }],
  };
}

function errorText(message: string): {
  content: [{ type: "text"; text: string }];
  isError: true;
} {
  return {
    content: [{ type: "text", text: message }],
    isError: true,
  };
}

function formatError(error: unknown): string {
  if (error instanceof AuthError || error instanceof RoverApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

async function main(): Promise<void> {
  const auth = new AuthManager();
  await auth.ensureKerberosTicket();

  const client = new RoverClient(auth);
  const server = new McpServer({
    name: SERVER_NAME,
    version: SERVER_VERSION,
  });

  server.registerTool(
    "get_person",
    {
      title: "Get person",
      description:
        "Look up a Red Hat employee by Kerberos ID (uid) or email address. " +
        "Returns name, title, email, location, manager, cost center, org, hire date, bio, and timezone. " +
        "Includes formerEmployee when Rover marks the person as a former employee.",
      inputSchema: {
        kerberos_id: nonEmptyString(
          "Kerberos uid (e.g. cmoore) or email (e.g. cmoore@redhat.com)",
        ),
      },
    },
    async ({ kerberos_id }) => {
      try {
        const result = await getPerson(client, kerberos_id);
        if (!result.found) {
          return { content: [{ type: "text", text: result.message }] };
        }
        return jsonText(result.person);
      } catch (error) {
        return errorText(formatError(error));
      }
    },
  );

  server.registerTool(
    "search_people",
    {
      title: "Search people",
      description:
        "Search Red Hat employees by name, Kerberos uid, or email. " +
        "Returns matching people with name, uid, title, email, and location.",
      inputSchema: {
        query: nonEmptyString("Name, uid, or email to search for"),
      },
    },
    async ({ query }) => {
      try {
        const result = await searchPeople(client, query);
        return jsonText(result);
      } catch (error) {
        return errorText(formatError(error));
      }
    },
  );

  server.registerTool(
    "get_org_chart",
    {
      title: "Get org chart",
      description:
        "Get the management chain (up to CEO) and direct reports for a person. " +
        "Optionally include all indirect reports.",
      inputSchema: {
        kerberos_id: nonEmptyString("Kerberos uid or email of the person"),
        include_indirect: z
          .boolean()
          .optional()
          .describe("If true, also return all indirect reports (default false)"),
      },
    },
    async ({ kerberos_id, include_indirect }) => {
      try {
        const result = await getOrgChart(client, kerberos_id, {
          includeIndirect: include_indirect,
        });
        if (!result.found) {
          return { content: [{ type: "text", text: result.message }] };
        }
        return jsonText(result.orgChart);
      } catch (error) {
        return errorText(formatError(error));
      }
    },
  );

  server.registerTool(
    "get_team",
    {
      title: "Get team",
      description:
        "List all members reporting to a manager (direct and, by default, indirect). " +
        "Returns each member's name, uid, title, and location.",
      inputSchema: {
        manager_kerberos_id: nonEmptyString(
          "Kerberos uid or email of the manager",
        ),
        include_indirect: z
          .boolean()
          .optional()
          .describe(
            "If true (default), include indirect reports as well as directs",
          ),
      },
    },
    async ({ manager_kerberos_id, include_indirect }) => {
      try {
        const result = await getTeam(client, manager_kerberos_id, {
          includeIndirect: include_indirect,
        });
        if (!result.found) {
          return { content: [{ type: "text", text: result.message }] };
        }
        return jsonText(result.team);
      } catch (error) {
        return errorText(formatError(error));
      }
    },
  );

  server.registerTool(
    "get_groups",
    {
      title: "Get groups",
      description:
        "List Rover projects/products, communities, and badges for a person. " +
        "Note: Rover has no dedicated group-membership API; these profile fields are the closest available data.",
      inputSchema: {
        kerberos_id: nonEmptyString("Kerberos uid or email of the person"),
      },
    },
    async ({ kerberos_id }) => {
      try {
        const result = await getGroups(client, kerberos_id);
        if (!result.found) {
          return { content: [{ type: "text", text: result.message }] };
        }
        return jsonText(result.groups);
      } catch (error) {
        return errorText(formatError(error));
      }
    },
  );

  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error(`${SERVER_NAME} v${SERVER_VERSION} running on stdio`);
}

main().catch((error: unknown) => {
  console.error("Fatal error starting rover-mcp:", formatError(error));
  process.exit(1);
});
