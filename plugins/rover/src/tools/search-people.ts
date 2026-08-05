/**
 * Search for people by name, email, or other criteria.
 */

import type { RoverClient } from "../rover-client.js";
import type { PersonSummary } from "../types.js";
import { looksLikeEmail, toPersonSummary } from "./mappers.js";

export interface SearchPeopleResult {
  query: string;
  count: number;
  people: PersonSummary[];
  /** Present when the query was empty or produced no matches. */
  message?: string;
}

export async function searchPeople(
  client: RoverClient,
  query: string,
): Promise<SearchPeopleResult> {
  const trimmed = query.trim();
  if (!trimmed) {
    return {
      query: trimmed,
      count: 0,
      people: [],
      message: "Empty search query.",
    };
  }

  const matches = looksLikeEmail(trimmed)
    ? await client.searchAdvanced({ mail: trimmed })
    : await client.searchSimple(trimmed);

  const people = matches.map(toPersonSummary);
  if (people.length === 0) {
    return {
      query: trimmed,
      count: 0,
      people: [],
      message: `No people found for "${trimmed}".`,
    };
  }

  return { query: trimmed, count: people.length, people };
}
