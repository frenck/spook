/** `spook/info`: which Spook is running. Administrators only. */
import type { HomeAssistant } from "../hass";
import { callSpookCommand } from "./command";

export interface SpookInfo {
  /** The version of Spook, `0.0.0` when it runs from a checkout. */
  version: string;
}

export const fetchSpookInfo = (hass: HomeAssistant): Promise<SpookInfo> =>
  callSpookCommand<SpookInfo>(hass, "spook/info");
