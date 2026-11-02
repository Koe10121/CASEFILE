import type { ActionResult, CaseCover, Game } from "../api/types";

const rhea = {
  id: "woman",
  label: "Woman",
  name: "DI Rhea Voss",
  pronouns: "she/her",
  bio: "Major Crimes.",
};

export function makeGame(overrides: Partial<Game> = {}): Game {
  return {
    id: "g1",
    difficulty: "normal",
    detective: rhea,
    help: {
      contradictions: "side_by_side",
      hints: "none",
      notebook: "by_suspect",
      evidence_picker: "all_found",
    },
    over: false,
    current_suspect: null,
    suspects: [{ id: "S_RICHARD", name: "Richard Okafor", interviewed: false }],
    locations: [],
    evidence: [],
    notebook: [],
    statements: [],
    interviews: {},
    tokens: { used: 0, budget: null },
    result: null,
    ...overrides,
  };
}

export const cover: CaseCover = {
  id: "blackwood-001",
  title: "The Last Evening at Blackwood Manor",
  place: "Blackwood Manor",
  date: "2026-10-31",
  intro: "Halloween.",
  detective: { callsign: "Nightjar", identities: [rhea] },
  people: [{ id: "S_RICHARD", name: "Richard Okafor", age: 58, bio: "CFO.", role: "suspect" }],
  accusation: { culprits: ["S_RICHARD"], motives: [], methods: [], max_evidence: 4 },
  ai: "mock",
  max_question_chars: 500,
};

/** Richard's first meeting: his opening statement and the lie it puts on record. */
export function talkResult(): ActionResult {
  const exchange = {
    detective: "",
    suspect: "I was in the billiard room.",
    demeanor: "hostile",
    shown: null,
  };
  return {
    line: { suspect: "S_RICHARD", dialogue: exchange.suspect, demeanor: exchange.demeanor },
    events: [
      { type: "lie_on_record", suspect: "S_RICHARD", lie: "LIE_RICHARD_BILLIARD", claim: "a" },
      { type: "location_searched", location: "LOC_STUDY", name: "Study" },
    ],
    game: makeGame({
      current_suspect: "S_RICHARD",
      interviews: { S_RICHARD: [exchange] },
      suspects: [{ id: "S_RICHARD", name: "Richard Okafor", interviewed: true }],
    }),
  };
}

export function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
