/**
 * Spook's strings in its frontends.
 *
 * They live in the integration's `translations/en.json`, under
 * `config_panel`, so Weblate has one file for everything Spook says. Home
 * Assistant hands out that section like any other, and it is the section
 * made for an integration's own panel.
 */
import type { HomeAssistant, LocalizeValues } from "./hass";

const DOMAIN = "spook";
const CATEGORY = "config_panel";

/**
 * Loads Spook's strings for the language of the frontend. Call it before
 * the first `localize`, and again when the language changes.
 */
export const loadTranslations = async (hass: HomeAssistant): Promise<void> => {
  await hass.loadBackendTranslation(CATEGORY, DOMAIN);
};

/**
 * One of Spook's strings, by its key under `config_panel`, like
 * `localize(hass, "repairs.title")`.
 *
 * Takes `hass` on every call rather than holding on to a function: the
 * frontend makes a new `localize` when the language changes.
 */
export const localize = (
  hass: HomeAssistant,
  key: string,
  values?: LocalizeValues,
): string => hass.localize(`component.${DOMAIN}.${CATEGORY}.${key}`, values);
