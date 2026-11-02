// Short names for the generated API types. schema.d.ts is generated from the backend's
// OpenAPI schema (`npm run gen:api`), so a backend change that breaks the frontend
// fails the type check instead of failing in the browser (D47).
import type { components } from "./schema";

type Schemas = components["schemas"];

export type CaseCover = Schemas["CaseOut"];
export type Game = Schemas["GameOut"];
export type Hints = Schemas["HintsOut"];
export type Expression = Schemas["LineOut"]["expression"];
export type ActionResult = Schemas["ActionOut"];
export type GameEvent = ActionResult["events"][number];
export type Line = Schemas["LineOut"];
export type Exchange = Schemas["ExchangeOut"];
export type Evidence = Schemas["EvidenceOut"];
export type Location = Schemas["LocationOut"];
export type Suspect = Schemas["SuspectOut"];
export type Difficulty = Game["difficulty"];
export type PlayedBy = Game["played_by"];

/** Each action endpoint and the body it takes. */
export interface ActionBodies {
  talk: Schemas["TalkRequest"];
  ask: Schemas["AskRequest"];
  search: Schemas["SearchRequest"];
  show: Schemas["ShowRequest"];
  accuse: Schemas["AccuseRequest"];
  hint: Record<string, never>;
}
export type Verb = keyof ActionBodies;
export type NotebookEntry = Schemas["NotebookEntryOut"];
export type Statement = Schemas["StatementOut"];
export type Result = Schemas["ResultOut"];
export type Help = Schemas["DifficultyProfile"];
export type Accusation = Schemas["Accusation"];
