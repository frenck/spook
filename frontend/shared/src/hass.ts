/**
 * The parts of Home Assistant's `hass` object that Spook reads.
 *
 * Written by hand, and only what Spook uses. Home Assistant publishes no
 * types for it, and a copy of the frontend's would go stale without anybody
 * noticing. Add a field here when a frontend of Spook starts reading it.
 */

/** Values filled into the placeholders of a translated string. */
export type LocalizeValues = Record<string, string | number | null | undefined>;

/** Looks up a translated string by its key. An unknown key gives "". */
export type LocalizeFunc = (key: string, values?: LocalizeValues) => string;

/** One entity, as `hass.states` holds it. */
export interface HassEntity {
  entity_id: string;
  state: string;
  attributes: Record<string, unknown>;
  last_changed: string;
  last_updated: string;
}

export interface HomeAssistant {
  /** The language the frontend shows, like `en` or `pt-BR`. */
  language: string;

  /** Every entity, by its ID. */
  states: Record<string, HassEntity>;

  /** Who is looking. */
  user?: {
    id: string;
    name: string;
    is_admin: boolean;
  };

  /** Whether the frontend is dark right now. */
  themes: {
    darkMode: boolean;
  };

  /** Sends a websocket command, and resolves with its result. */
  callWS<Result>(message: {
    type: string;
    [key: string]: unknown;
  }): Promise<Result>;

  localize: LocalizeFunc;

  /**
   * Loads one category of the backend's translations into `localize`. Cheap
   * after the first call: the frontend keeps what it loaded.
   */
  loadBackendTranslation(
    category: string,
    integration?: string | string[],
    configFlow?: boolean,
  ): Promise<LocalizeFunc>;
}
