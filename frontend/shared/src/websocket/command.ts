/**
 * What every websocket command of Spook shares, on the frontend side.
 *
 * Each command has a small file of its own next to this one, with the shape
 * of its answer and a function that asks it. The backend twin of a command
 * lives under `custom_components/spook/ectoplasms/<domain>/websocket/`.
 */
import type { HomeAssistant } from "../hass";

/**
 * The name of a command. Names follow the rule in
 * `custom_components/spook/websocket.py`: `spook/<area>/<verb>`, or
 * `spook/<name>` for the few about Spook as a whole.
 */
export type SpookCommandType = `spook/${string}`;

/** The error code of a command called while Spook is not loaded. */
export const ERR_NOT_LOADED = "not_loaded";

/** How a websocket command fails: Home Assistant rejects with this. */
export interface WebSocketError {
  code: string;
  message: string;
}

/** Sends one of Spook's commands, and resolves with its answer. */
export const callSpookCommand = <Result>(
  hass: HomeAssistant,
  type: SpookCommandType,
  fields: Record<string, unknown> = {},
): Promise<Result> => hass.callWS<Result>({ ...fields, type });

/**
 * Whether a command failed because Spook is not loaded, like while it
 * reloads. Worth telling apart: it is not broken, and asking again later
 * works.
 */
export const isNotLoaded = (error: unknown): boolean =>
  typeof error === "object" &&
  error !== null &&
  (error as Partial<WebSocketError>).code === ERR_NOT_LOADED;
