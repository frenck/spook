/**
 * The screenshots on the website, one test per shot.
 *
 * Each runs once for every language and theme in playwright.config.ts. A
 * shot opens a page, gets it into the state worth showing, and optionally
 * names what to crop to. Adding one is adding an entry to `shots`.
 *
 * Nothing here looks for English words: labels come from the frontend's own
 * translations, Spook's text from Spook's, and the names of the home from
 * seed/names, all in the language of the run.
 */
import { mkdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test, type Locator, type Page } from "@playwright/test";
import sharp from "sharp";
import { parse } from "yaml";
import { OWNER, readState } from "./home-assistant";
import { names } from "./names";

const here = dirname(fileURLToPath(import.meta.url));
const output = join(here, "..", "public", "images", "screenshots");

interface Shot {
  name: string;
  // A page, or a function for one that is only known once Home Assistant
  // runs, like the page of a device.
  path: string | (() => string);
  prepare?: (page: Page, language: string) => Promise<void>;
  // What the picture is about: one element, or several to show together.
  // Without one, it is the whole window.
  target?: (page: Page, language: string) => Locator | Locator[];
  // Where the picture can stop, for a target that is mostly empty below.
  until?: (page: Page) => Locator;
  // How much of the page around the target stays in. A dialog looks good
  // with some of the dimmed page around it; part of a page has its own
  // whitespace, and a margin would only pull in the header next to it.
  padding?: number;
  // Cut a dialog or card out along its own rounded edge, with nothing of
  // Home Assistant around it, so the website can put it on a backdrop of its
  // own. Where `until` cuts it short, it fades out instead.
  cutout?: boolean;
  // A window of another size, for a page that stretches out on a wide
  // screen and would end up with tiny text in a picture on the site.
  viewport?: { width: number; height: number };
  // A theme to wear instead of Home Assistant's own, by its name in the
  // theme picker. In light and in dark, like every shot.
  theme?: string;
}

// How much of the page around a target stays in the picture, by default.
const PADDING = 24;

// How far below `until` a cut-out keeps going, to fade out in.
const FADE = 48;

/** Spook's own translations, in the language of the run. */
function spook(language: string) {
  const file = join(
    here,
    "..",
    "..",
    "custom_components",
    "spook",
    "translations",
    `${language}.json`,
  );
  return JSON.parse(readFileSync(file, "utf-8"));
}

/** Spook's actions, with the fields they take. */
function services(): Record<string, any> {
  const file = join(
    here,
    "..",
    "..",
    "custom_components",
    "spook",
    "services.yaml",
  );
  return parse(readFileSync(file, "utf-8"));
}

/**
 * Spook's text for a repair, to find it on the page. Several repairs start
 * the same, like the unknown entities of an automation and of a script, so
 * naming what it is about finds the one meant.
 */
function repairTitle(language: string, key: string, subject?: string): string {
  const title: string = spook(language).issues[key].title;
  return subject
    ? title.replace(/\{[^}]+\}/, subject)
    : title.split("{")[0].trim();
}

/** A label of the frontend, in the language it is showing. */
function localize(page: Page, key: string): Promise<string> {
  return page.evaluate(
    (key) =>
      (document.querySelector("home-assistant") as any).hass.localize(key),
    key,
  );
}

/** Ring the thing the steps on the page tell you to select. */
async function highlight(locator: Locator): Promise<void> {
  await locator.evaluate((element) => {
    element.style.outline = "3px solid #00b8c4";
    element.style.outlineOffset = "-3px";
    element.style.borderRadius = "8px";
  });
}

/**
 * Open the dialog a button opens, and search it for Spook's ghost. These
 * dialogs put the cursor in their search field themselves, so typing is
 * enough, the same as it is for a person.
 */
async function searchForTheGhost(page: Page, button: string) {
  await page
    .getByRole("button", { name: await localize(page, button), exact: true })
    .click();
  await page.getByRole("dialog").waitFor();
  await page.waitForTimeout(300);
  await page.keyboard.type("👻");
}

/** What a search for the ghost turns up in a picker. */
function spookOptions(page: Page): Locator {
  return page.getByRole("option", { name: /👻/ });
}

/**
 * What an action is filled in with. Values only known once Home Assistant
 * runs are looked up in the browser: `{ deviceOf: "sun" }` is the device of
 * the integration entry of a domain, `{ entry: "radio_browser" }` the entry
 * itself. By domain, not by name: a name can change with the language. A
 * user has nothing but a name: `{ user: name("user.babysitter") }`.
 */
interface Fill {
  target?: object;
  data?: Record<string, unknown>;
}

/** The name of something in the home, like `area.attic`, in a language. */
type Name = (path: string) => string;

/**
 * One of Spook's actions in the Actions tool, picked and filled in, the way
 * "Try this action" on the website opens it. Named after the action, like
 * `action-homeassistant-create-area`. Anything typed in that people read
 * comes from seed/names: hand a function that takes `name` for those.
 */
function action(
  service: string,
  filled: Fill | ((name: Name) => Fill) = {},
  // A window of another size, for a form too long for the usual one.
  viewport = { width: 1000, height: 1800 },
): Shot {
  return {
    name: `action-${service.replace(/[._]/g, "-")}`,
    path: "/config/tools/action",
    async prepare(page, language) {
      const fill = asLists(
        service,
        typeof filled === "function" ? filled(names(language).name) : filled,
      );

      // The tool remembers the last action in the browser, so the action
      // goes there, and the page opens again to pick it up.
      await page.evaluate(
        async ({ service, fill }) => {
          const hass = (document.querySelector("home-assistant") as any).hass;
          const entries: any[] = await hass.callWS({
            type: "config_entries/get",
          });
          const users: any[] = await hass.callWS({ type: "config/auth/list" });
          const resolve = (value: any): any => {
            if (Array.isArray(value)) {
              return value.map(resolve);
            }
            if (value && typeof value === "object") {
              if ("deviceOf" in value) {
                const entry = entries.find(
                  (entry) => entry.domain === value.deviceOf,
                );
                return (Object.values(hass.devices) as any[]).find((device) =>
                  device.config_entries.includes(entry?.entry_id),
                )?.id;
              }
              if ("entry" in value) {
                return entries.find((entry) => entry.domain === value.entry)
                  ?.entry_id;
              }
              if ("user" in value) {
                return users.find((user) => user.name === value.user)?.id;
              }
              return Object.fromEntries(
                Object.entries(value).map(([key, inner]) => [
                  key,
                  resolve(inner),
                ]),
              );
            }
            return value;
          };
          localStorage.setItem(
            "panel-dev-action-state-service-data",
            JSON.stringify({
              action: service,
              target: resolve(fill.target ?? {}),
              data: resolve(fill.data ?? {}),
            }),
          );
          localStorage.setItem("panel-dev-action-state-yaml-mode", "false");
        },
        { service, fill },
      );
      await open(page, "/config/tools/action", language);
      // The first card is the action's own. An action with a condition in
      // it has cards of its own inside.
      await page.locator("tools-action ha-card").first().waitFor();
    },
    target: (page) => page.locator("tools-action ha-card").first(),
    cutout: true,
    // Tall enough for most forms, narrow enough to read on the site.
    viewport,
  };
}

/**
 * A field that takes several values shows nothing for a single one, so
 * those get a list, the way the field itself would hand it over.
 */
function asLists(service: string, fill: Fill): Fill {
  const fields = services()[service.replace(".", "_")]?.fields ?? {};
  const data = Object.fromEntries(
    Object.entries(fill.data ?? {}).map(([key, value]) => {
      const selector = Object.values(fields[key]?.selector ?? {})[0] as any;
      return [
        key,
        selector?.multiple && !Array.isArray(value) ? [value] : value,
      ];
    }),
  );
  return { ...fill, data };
}

/**
 * The Add action dialog of the automation editor, searched for a word. The
 * word is per language, under `search` in seed/names: a language without
 * one skips the shot, rather than searching German actions for an English
 * word.
 */
function actionSearch(name: string, topic: string): Shot {
  return {
    name: `actions-search-${name}`,
    path: "/config/automation/edit/new",
    async prepare(page, language) {
      const query = names(language).search(topic);
      test.skip(!query, `No word to search for in ${language}`);

      const addAction = await localize(
        page,
        "ui.panel.config.automation.editor.actions.add",
      );
      await page
        .locator("manual-automation-editor")
        .getByRole("button", { name: addAction, exact: true })
        .click();
      const dialog = page.locator("add-automation-element-dialog");
      await dialog.locator("ha-input-search input").fill(query!);
      await dialog
        .locator("ha-automation-add-search ha-list-item-button")
        .nth(3)
        .waitFor();
    },
    target: (page) =>
      page.locator("add-automation-element-dialog").getByRole("dialog"),
    cutout: true,
  };
}

/**
 * A repair Spook raised for the seed home, opened. The subject is what it is
 * about, by its place in seed/names, like `script.goodnight`. Something
 * that is the same in every language, like the address of a dashboard
 * resource, is handed as a function. A repair of which there is only ever
 * one goes without.
 */
function repair(
  name: string,
  key: string,
  subject?: string | (() => string),
): Shot {
  return {
    name: `repair-${name}`,
    path: "/config/repairs",
    async prepare(page, language) {
      const about =
        typeof subject === "function"
          ? subject()
          : subject && names(language).name(subject);
      await page
        .getByText(repairTitle(language, key, about))
        .first()
        .click();
      await page.getByRole("dialog").waitFor();
    },
    target: (page) => page.getByRole("dialog"),
    cutout: true,
  };
}

/** One of Spook's helpers, being set up, at its first step. */
async function startHelper(page: Page, language: string, helper: string) {
  await searchForTheGhost(page, "ui.panel.config.helpers.picker.create_helper");

  // The helper is listed by its translated name, like "Omgekeerd 👻".
  const title: string = helperTranslations(helper, language).title;
  await spookOptions(page)
    .filter({ hasText: title.replace("👻", "").trim() })
    .click();
  await page.locator("dialog-data-entry-flow").getByRole("dialog").waitFor();
  await page.waitForTimeout(500);
}

/** Spook's inverse helper, being set up, at its first step. */
function startInverse(page: Page, language: string) {
  return startHelper(page, language, "spook_inverse");
}

/**
 * One of Spook's helpers that sets up in one step, its form filled in the
 * way the steps on its page say. Named after the helper, like
 * `helper-calibration`.
 */
function helperForm(
  helper: string,
  data: (name: Name) => Record<string, unknown>,
): Shot {
  return {
    name: `helper-${helper.replace(/^spook_/, "").replace(/_/g, "-")}`,
    path: "/config/helpers",
    async prepare(page, language) {
      await startHelper(page, language, helper);
      const form = page.locator("dialog-data-entry-flow step-flow-form");
      await form.locator("ha-form").waitFor();

      // What a person would have typed and picked, handed to the form the
      // way its fields hand it over.
      await form.evaluate(
        (element: any, data) => {
          element._stepData = { ...element._stepData, ...data };
        },
        data(names(language).name),
      );
      await page.waitForTimeout(500);
    },
    target: flowDialog,
    cutout: true,
  };
}

/**
 * The page of a device, without the activity column: what it is, and what
 * it has.
 */
function devicePage(page: Page): Locator[] {
  const device = page.locator("ha-config-device-page");
  // Not the header: it runs the whole width, over the activity column too.
  return [device.locator(".column").nth(0), device.locator(".column").nth(1)];
}

/**
 * The first visit to the Marketplace asks you to read a notice and agree.
 * Agree, the way a person does: the checkbox, then on to its button, which
 * comes right after "Go back". By keyboard, so it works in any language.
 */
async function agreeToTheMarketplace(page: Page) {
  const agree = page.getByRole("checkbox");
  if (!(await agree.count())) {
    return;
  }
  await agree.first().click({ force: true });
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");
  await agree.first().waitFor({ state: "detached" });
}

// Spook in the Marketplace, by the ID of its repository on GitHub.
const MARKETPLACE_SPOOK = "/marketplace/repository/605635573";

/** The helper of an integration's setup or options flow, as a dialog. */
function flowDialog(page: Page): Locator {
  return page.locator("dialog-data-entry-flow").getByRole("dialog");
}

/** Spook's helpers' own translations, in the language of the run. */
function helperTranslations(helper: string, language: string) {
  const file = join(
    here,
    "..",
    "..",
    "custom_components",
    "spook",
    "integrations",
    helper,
    "translations",
    `${language}.json`,
  );
  return JSON.parse(readFileSync(file, "utf-8"));
}

// Spook's actions, filled in with the home in seed/: its areas, floors,
// labels, lamps and helpers. IDs as they are, they are the same in every
// language; what people read through `name`, from seed/names.
const actions: Shot[] = [
  // Areas.
  action("homeassistant.create_area", (name) => ({
    data: {
      name: name("examples.new_area"),
      icon: "mdi:ghost",
      aliases: [name("examples.new_area_alias")],
    },
  })),
  action("homeassistant.delete_area", { data: { area_id: "attic" } }),
  action("homeassistant.add_alias_to_area", (name) => ({
    data: { area_id: "living_room", alias: [name("examples.area_alias")] },
  })),
  action("homeassistant.remove_alias_from_area", (name) => ({
    data: { area_id: "living_room", alias: [name("examples.area_alias")] },
  })),
  action("homeassistant.set_area_aliases", (name) => ({
    data: {
      area_id: "living_room",
      aliases: [name("examples.area_alias"), name("examples.other_area_alias")],
    },
  })),
  action("homeassistant.add_device_to_area", {
    data: { area_id: "living_room", device_id: { deviceOf: "sun" } },
  }),
  action("homeassistant.remove_device_from_area", {
    data: { device_id: { deviceOf: "sun" } },
  }),
  action("homeassistant.add_entity_to_area", {
    data: { area_id: "kitchen", entity_id: "number.kitchen_fan_speed" },
  }),
  action("homeassistant.remove_entity_from_area", {
    data: { entity_id: "light.hallway_light" },
  }),

  // Floors.
  action("homeassistant.create_floor", (name) => ({
    data: {
      name: name("examples.new_floor"),
      icon: "mdi:home-floor-2",
      level: 2,
      aliases: [name("examples.new_floor_alias")],
    },
  })),
  action("homeassistant.delete_floor", { data: { floor_id: "basement" } }),
  action("homeassistant.add_alias_to_floor", (name) => ({
    data: { floor_id: "ground_floor", alias: [name("examples.floor_alias")] },
  })),
  action("homeassistant.remove_alias_from_floor", (name) => ({
    data: { floor_id: "ground_floor", alias: [name("examples.floor_alias")] },
  })),
  action("homeassistant.set_floor_aliases", (name) => ({
    data: {
      floor_id: "ground_floor",
      aliases: [
        name("examples.floor_alias"),
        name("examples.other_floor_alias"),
      ],
    },
  })),
  action("homeassistant.add_area_to_floor", {
    data: { floor_id: "first_floor", area_id: "attic" },
  }),
  action("homeassistant.remove_area_from_floor", {
    data: { area_id: "attic" },
  }),

  // Labels.
  action("homeassistant.create_label", (name) => ({
    data: {
      name: name("examples.new_label"),
      description: name("examples.new_label_description"),
      icon: "mdi:ghost",
      color: "purple",
    },
  })),
  action("homeassistant.delete_label", { data: { label_id: "christmas" } }),
  action("homeassistant.add_label_to_area", {
    data: { label_id: "christmas", area_id: "living_room" },
  }),
  action("homeassistant.remove_label_from_area", {
    data: { label_id: "christmas", area_id: "living_room" },
  }),
  action("homeassistant.add_label_to_device", {
    data: { label_id: "christmas", device_id: { deviceOf: "sun" } },
  }),
  action("homeassistant.remove_label_from_device", {
    data: { label_id: "christmas", device_id: { deviceOf: "sun" } },
  }),
  action("homeassistant.add_label_to_entity", {
    data: { label_id: "christmas", entity_id: "light.living_room_lamp" },
  }),
  action("homeassistant.remove_label_from_entity", {
    data: { label_id: "night_light", entity_id: "light.hallway_light" },
  }),

  // Devices and entities.
  action("homeassistant.disable_device", {
    data: { device_id: { deviceOf: "sun" } },
  }),
  action("homeassistant.enable_device", {
    data: { device_id: { deviceOf: "sun" } },
  }),
  action("homeassistant.disable_entity", {
    data: { entity_id: "light.bedroom_lamp" },
  }),
  action("homeassistant.enable_entity", {
    data: { entity_id: "light.bedroom_lamp" },
  }),
  action("homeassistant.hide_entity", {
    data: { entity_id: "input_boolean.bedroom_lamp" },
  }),
  action("homeassistant.unhide_entity", {
    data: { entity_id: "input_boolean.bedroom_lamp" },
  }),
  action("homeassistant.rename_entity", (name) => ({
    data: {
      entity_id: "light.hallway_light",
      name: name("examples.new_entity_name"),
    },
  })),
  action("homeassistant.update_entity_id", {
    data: { entity_id: "light.hallway_light", new_entity_id: "light.hall" },
  }),
  action("homeassistant.list_orphaned_database_entities"),
  action("homeassistant.delete_all_orphaned_entities"),

  // Integrations.
  action("homeassistant.disable_config_entry", {
    data: { config_entry_id: { entry: "radio_browser" } },
  }),
  action("homeassistant.enable_config_entry", {
    data: { config_entry_id: { entry: "radio_browser" } },
  }),
  action("homeassistant.disable_polling", {
    data: { config_entry_id: { entry: "radio_browser" } },
  }),
  action("homeassistant.enable_polling", {
    data: { config_entry_id: { entry: "radio_browser" } },
  }),
  action("homeassistant.ignore_all_discovered"),
  action("homeassistant.restart"),

  // Helpers and numbers.
  action("input_number.create", (name) => ({
    data: {
      name: name("examples.new_input_number"),
      min: 20,
      max: 32,
      step: 0.5,
      initial: 26,
      mode: "slider",
      unit_of_measurement: "°C",
      icon: "mdi:pool",
    },
  })),
  action("input_number.delete", {
    data: { entity_id: "input_number.bedroom_temperature" },
  }),
  action("input_number.increment", {
    target: { entity_id: "input_number.bedroom_temperature" },
    data: { amount: 0.5 },
  }),
  action("input_number.decrement", {
    target: { entity_id: "input_number.bedroom_temperature" },
    data: { amount: 0.5 },
  }),
  action("input_number.max", {
    target: { entity_id: "input_number.bedroom_temperature" },
  }),
  action("input_number.min", {
    target: { entity_id: "input_number.bedroom_temperature" },
  }),
  action("input_select.random", {
    target: { entity_id: "input_select.movie_night" },
  }),
  action("input_select.shuffle", {
    target: { entity_id: "input_select.movie_night" },
  }),
  action("input_select.sort", {
    target: { entity_id: "input_select.movie_night" },
  }),
  action("number.increment", {
    target: { entity_id: "number.kitchen_fan_speed" },
    data: { amount: 1 },
  }),
  action("number.decrement", {
    target: { entity_id: "number.kitchen_fan_speed" },
    data: { amount: 1 },
  }),
  action("number.max", { target: { entity_id: "number.kitchen_fan_speed" } }),
  action("number.min", { target: { entity_id: "number.kitchen_fan_speed" } }),

  // People and places.
  action("person.add_device_tracker", {
    data: {
      entity_id: "person.franck_nijhof",
      device_tracker: "device_tracker.new_phone",
    },
  }),
  action("person.remove_device_tracker", {
    data: {
      entity_id: "person.franck_nijhof",
      device_tracker: "device_tracker.old_phone",
    },
  }),
  action("zone.create", (name) => ({
    data: {
      name: name("examples.new_zone"),
      icon: "mdi:briefcase",
      latitude: 52.0907,
      longitude: 5.1214,
      radius: 100,
    },
  })),
  action("zone.update", {
    data: { entity_id: "zone.gym", radius: 200 },
  }),
  action("zone.delete", { data: { entity_id: "zone.gym" } }),

  // Repairs and the recorder.
  action("repairs.create", (name) => ({
    data: {
      title: name("examples.new_repair"),
      description: name("examples.new_repair_description"),
      issue_id: "hungry_ghost",
      severity: "warning",
      persistent: true,
    },
  })),
  action("repairs.remove", { data: { issue_id: "hungry_ghost" } }),

  // The odd ones out.
  action("blueprint.import", {
    data: {
      url: "https://github.com/home-assistant/core/blob/dev/homeassistant/components/automation/blueprints/motion_light.yaml",
    },
  }),
  action("select.random", { target: { entity_id: "select.ghost_mood" } }),
  action("spook.boo"),
  action("spook.random_fail"),
  action("repairs.ignore_all"),
  action("repairs.unignore_all"),
  action("recorder.import_statistics", (name) => ({
    data: {
      statistic_id: "sensor.energy_meter",
      name: name("sensor.energy_meter"),
      source: "recorder",
      unit_of_measurement: "kWh",
      has_mean: false,
      has_sum: true,
      stats: [
        { start: "2025-01-01T00:00:00+00:00", state: 1520.5, sum: 1520.5 },
      ],
    },
  })),
  // More of the same, for the topics above.
  action("homeassistant.update_area", {
    data: {
      area_id: "living_room",
      floor_id: "ground_floor",
      icon: "mdi:sofa",
      temperature_entity_id: "sensor.living_room_thermometer",
    },
  }),
  action("homeassistant.update_floor", (name) => ({
    data: {
      floor_id: "first_floor",
      aliases: [name("examples.new_floor_alias")],
      icon: "mdi:home-floor-1",
      level: 1,
    },
  })),
  action("homeassistant.update_label", (name) => ({
    data: {
      label_id: "night_light",
      name: name("examples.renamed_label"),
      color: "amber",
    },
  })),
  action("homeassistant.update_device", (name) => ({
    data: {
      device_id: { deviceOf: "sun" },
      name_by_user: name("examples.device_name"),
    },
  })),

  // Categories.
  action("homeassistant.create_category", (name) => ({
    data: {
      scope: "automation",
      name: name("examples.new_category"),
      icon: "mdi:shield-home",
    },
  })),
  action("homeassistant.update_category", (name) => ({
    data: {
      scope: "automation",
      category_id: "lighting",
      name: name("examples.renamed_category"),
    },
  })),
  action("homeassistant.delete_category", {
    data: { scope: "automation", category_id: "lighting" },
  }),
  action("homeassistant.add_category_to_entity", {
    data: { category_id: "lighting", entity_id: "automation.movie_night" },
  }),
  action("homeassistant.remove_category_from_entity", {
    data: {
      category_id: "lighting",
      entity_id: "automation.hallway_light_at_sunset",
    },
  }),

  // Entities, and the assistants that see them.
  action("homeassistant.expose_entity", {
    data: {
      entity_id: "light.living_room_lamp",
      assistants: ["conversation"],
    },
  }),
  action("homeassistant.unexpose_entity", {
    data: { entity_id: "light.bedroom_lamp", assistants: ["conversation"] },
  }),
  action("homeassistant.set_entity_icon", {
    data: { entity_id: "light.hallway_light", icon: "mdi:ceiling-light" },
  }),
  action("homeassistant.add_alias_to_entity", (name) => ({
    data: {
      entity_id: "light.living_room_lamp",
      alias: [name("examples.entity_alias")],
    },
  })),
  action("homeassistant.remove_alias_from_entity", (name) => ({
    data: {
      entity_id: "light.living_room_lamp",
      alias: [name("examples.entity_alias")],
    },
  })),
  action("homeassistant.set_entity_aliases", (name) => ({
    data: {
      entity_id: "light.living_room_lamp",
      aliases: [
        name("examples.entity_alias"),
        name("examples.other_entity_alias"),
      ],
    },
  })),

  // Users.
  action("homeassistant.disable_user", (name) => ({
    data: { user_id: { user: name("user.babysitter") } },
  })),
  action("homeassistant.enable_user", (name) => ({
    data: { user_id: { user: name("user.babysitter") } },
  })),

  // Making and removing helpers.
  action("input_boolean.create", (name) => ({
    data: {
      name: name("examples.new_input_boolean"),
      icon: "mdi:palm-tree",
      initial: false,
    },
  })),
  action("input_boolean.delete", {
    data: { entity_id: "input_boolean.guest_mode" },
  }),
  action("input_button.create", (name) => ({
    data: { name: name("examples.new_input_button"), icon: "mdi:cookie" },
  })),
  action("input_button.delete", {
    data: { entity_id: "input_button.doorbell" },
  }),
  action("input_datetime.create", (name) => ({
    data: {
      name: name("examples.new_input_datetime"),
      has_date: false,
      has_time: true,
      initial: "07:00:00",
      icon: "mdi:alarm",
    },
  })),
  action("input_datetime.delete", {
    data: { entity_id: "input_datetime.alarm_clock" },
  }),
  action("input_number.set_range", {
    target: { entity_id: "input_number.bedroom_temperature" },
    data: { min: 16, max: 24, step: 0.5 },
  }),
  action("input_select.create", (name) => ({
    data: {
      name: name("examples.house_mode.name"),
      options: [
        name("examples.house_mode.options.home"),
        name("examples.house_mode.options.away"),
        name("examples.house_mode.options.night"),
      ],
      icon: "mdi:home-switch",
    },
  })),
  action("input_select.delete", {
    data: { entity_id: "input_select.movie_night" },
  }),
  action("input_select.reverse", {
    target: { entity_id: "input_select.movie_night" },
  }),
  action("input_text.create", (name) => ({
    data: {
      name: name("examples.new_input_text"),
      max: 100,
      mode: "text",
      icon: "mdi:note-text",
    },
  })),
  action("input_text.delete", {
    data: { entity_id: "input_text.welcome_message" },
  }),
  action("counter.create", (name) => ({
    data: {
      name: name("examples.new_counter"),
      initial: 0,
      minimum: 0,
      step: 1,
      restore: true,
      icon: "mdi:cookie",
    },
  })),
  action("counter.delete", { data: { entity_id: "counter.coffee_cups" } }),
  action("timer.create", (name) => ({
    data: {
      name: name("examples.new_timer"),
      duration: { hours: 0, minutes: 12, seconds: 0 },
      restore: true,
      icon: "mdi:pizza",
    },
  })),
  action("timer.delete", { data: { entity_id: "timer.laundry" } }),
  action("timer.set_duration", {
    target: { entity_id: "timer.laundry" },
    data: { duration: "01:30:00" },
  }),
  action("schedule.create", (name) => ({
    data: {
      name: name("examples.new_schedule"),
      icon: "mdi:sprinkler",
      monday: [{ from: "06:00:00", to: "06:30:00" }],
      thursday: [{ from: "06:00:00", to: "06:30:00" }],
    },
  })),
  action("schedule.delete", { data: { entity_id: "schedule.heating" } }),
  action("schedule.set_day", {
    target: { entity_id: "schedule.heating" },
    data: { day: "saturday", blocks: [{ from: "09:00:00", to: "23:00:00" }] },
  }),

  // Lights.
  action("light.set_brightness", {
    target: { entity_id: "light.living_room_lamp" },
    data: { brightness_pct: 40, transition: 2 },
  }),
  action("light.increase_brightness", {
    target: { entity_id: "light.kitchen_lights" },
    data: { step_pct: 10 },
  }),
  action("light.decrease_brightness", {
    target: { entity_id: "light.bedroom_lamp" },
    data: { step_pct: 10 },
  }),
  action("light.set_color", {
    target: { entity_id: "light.living_room_lamp" },
    data: { rgb_color: [255, 136, 0] },
  }),
  action("light.set_color_temperature", {
    target: { entity_id: "light.bedroom_lamp" },
    data: { kelvin: 2700 },
  }),
  action("light.set_effect", {
    target: { entity_id: "light.living_room_lamp" },
    data: { effect: "colorloop" },
  }),

  // Up and down, a step at a time.
  action("climate.increase_temperature", {
    target: { entity_id: "climate.bedroom_thermostat" },
    data: { step: 0.5 },
  }),
  action("climate.decrease_temperature", {
    target: { entity_id: "climate.bedroom_thermostat" },
    data: { step: 0.5 },
  }),
  action("water_heater.increase_temperature", {
    target: { entity_id: "water_heater.boiler" },
    data: { step: 5 },
  }),
  action("water_heater.decrease_temperature", {
    target: { entity_id: "water_heater.boiler" },
    data: { step: 5 },
  }),
  action("cover.increase_position", {
    target: { entity_id: "cover.living_room_blinds" },
    data: { step: 10 },
  }),
  action("cover.decrease_position", {
    target: { entity_id: "cover.living_room_blinds" },
    data: { step: 10 },
  }),
  action("valve.increase_position", {
    target: { entity_id: "valve.garden_tap" },
    data: { step: 25 },
  }),
  action("valve.decrease_position", {
    target: { entity_id: "valve.garden_tap" },
    data: { step: 25 },
  }),
  action("humidifier.increase_humidity", {
    target: { entity_id: "humidifier.basement_dehumidifier" },
    data: { step: 5 },
  }),
  action("humidifier.decrease_humidity", {
    target: { entity_id: "humidifier.basement_dehumidifier" },
    data: { step: 5 },
  }),
  action("media_player.increase_volume", {
    target: { entity_id: "media_player.kitchen_speaker" },
    data: { step: 5 },
  }),
  action("media_player.decrease_volume", {
    target: { entity_id: "media_player.kitchen_speaker" },
    data: { step: 5 },
  }),

  // Groups.
  action("group.add_members", {
    data: {
      group: "group.downstairs_lights",
      members: ["light.hallway_light"],
    },
  }),
  action("group.remove_members", {
    data: {
      group: "group.downstairs_lights",
      members: ["light.kitchen_lights"],
    },
  }),
  action("group.set_members", {
    data: {
      group: "group.downstairs_lights",
      members: [
        "light.living_room_lamp",
        "light.kitchen_lights",
        "light.hallway_light",
      ],
    },
  }),

  // Calendars and lists.
  action("calendar.delete_event", (name) => ({
    target: { entity_id: "calendar.family" },
    data: {
      summary: name("examples.calendar_event"),
      start_date_time: "2026-12-03 15:00:00",
    },
  })),
  action(
    "calendar.update_event",
    (name) => ({
      target: { entity_id: "calendar.family" },
      data: {
        summary: name("examples.calendar_event"),
        shift: { hours: 1, minutes: 0, seconds: 0 },
      },
    }),
    // The longest form of them all: the shift is at the very bottom.
    { width: 1000, height: 2600 },
  ),
  action("todo.move_item", (name) => ({
    target: { entity_id: "todo.shopping_list" },
    data: { item: name("examples.todo_item"), position: "top" },
  })),

  // And the rest.
  action("automation.turn_on_for", {
    target: { entity_id: "automation.movie_night" },
    data: { duration: { hours: 2, minutes: 0, seconds: 0 } },
  }),
  action("sensor.set_display_precision", {
    data: { entity_id: "sensor.living_room_thermometer", display_precision: 1 },
  }),
  action("repairs.list", {
    data: { include_ignored: true, domain: "spook" },
  }),
  action("spook.wait_for_condition", {
    data: {
      condition: {
        condition: "state",
        entity_id: "binary_sensor.front_door",
        state: "off",
      },
      timeout: { hours: 0, minutes: 5, seconds: 0 },
    },
  }),
];

// What Spook adds per topic, as the Add action dialog finds it. The words
// to search for are under `search` in seed/names.
const searches: Shot[] = [
  actionSearch("area", "area"),
  actionSearch("floor", "floor"),
  actionSearch("label", "label"),
  actionSearch("input-number", "input_number"),
  actionSearch("number", "number"),
  actionSearch("input-select", "input_select"),
  actionSearch("person", "person"),
  actionSearch("zone", "zone"),
  actionSearch("repairs", "repairs"),
];

// What Spook finds in the seed home, one repair at a time.
const repairs: Shot[] = [
  repair("orphaned-statistics", "orphaned_statistics"),
  repair(
    "duplicate-resources",
    "lovelace_duplicate_resources",
    () => "/local/ghost-card.js",
  ),
  repair(
    "person-unknown-device-trackers",
    "person_unknown_device_trackers",
    () => OWNER.name,
  ),
  repair("energy-unknown-references", "energy_unknown_references"),
  repair("unknown-icons", "unknown_icons"),
  repair(
    "unused-blueprints",
    "unused_blueprints",
    "blueprints.doorbell_flash.name",
  ),
  repair(
    "automation-unknown-areas",
    "automation_unknown_area_references",
    "automation.garage_lights_off_at_night.name",
  ),
  repair(
    "automation-unknown-devices",
    "automation_unknown_device_references",
    "automation.doorbell_flash.name",
  ),
  repair(
    "script-unknown-entities",
    "script_unknown_entity_references",
    "script.goodnight",
  ),
  repair(
    "script-unknown-areas",
    "script_unknown_area_references",
    "script.goodnight",
  ),
  repair(
    "script-unknown-devices",
    "script_unknown_device_references",
    "script.goodnight",
  ),
  repair(
    "scene-unknown-entities",
    "scene_unknown_entity_references",
    "scene.cozy_evening",
  ),
  repair(
    "dashboard-unknown-entities",
    "lovelace_unknown_entity_references",
    "dashboard.overview",
  ),
  repair(
    "group-unknown-members",
    "group_unknown_members",
    "group.downstairs_lights",
  ),
];

/**
 * One of Spook's triggers or conditions in the automation of the seed that
 * uses it, selected, so the sidebar of the editor shows what it is set to.
 * The position is which trigger or condition of the automation it is.
 */
function automationPart(
  kind: "trigger" | "condition",
  key: string,
  automation: string,
  position = 0,
): Shot {
  const row = (page: Page) =>
    page
      .locator("manual-automation-editor")
      .locator(`ha-automation-${kind}-row`)
      .nth(position);

  return {
    name: `${kind}-${key.replace(/_/g, "-")}`,
    path: `/config/automation/edit/${automation}`,
    async prepare(page) {
      // On the name in the header of the row, left of what it targets.
      await row(page).click({ position: { x: 90, y: 24 } });
      await page.locator("ha-automation-sidebar").waitFor();

      // Opening some of them tidies their config in the editor, which
      // then offers to save, though nobody changed a thing.
      await page
        .locator("manual-automation-editor .fab-positioner")
        .evaluate((element) => (element.style.visibility = "hidden"));
      await page.waitForTimeout(500);
    },
    // The automation, and what is selected opened next to it.
    target: (page) => [
      page.locator("manual-automation-editor"),
      page.locator("ha-automation-sidebar"),
    ],
    padding: 0,
  };
}

// Each of Spook's triggers and conditions, in the automation of the seed
// made for it, by its ID in seed/automations.yaml.
const triggers: Shot[] = [
  automationPart("trigger", "automation_turned_off", "1732000000010"),
  automationPart("trigger", "device_discovered", "1732000000011"),
  automationPart("trigger", "recovered", "1732000000012"),
  automationPart("trigger", "device_added", "1732000000013"),
  automationPart("trigger", "stale", "1732000000014"),
  automationPart("trigger", "integration_added", "1732000000015"),
  automationPart("trigger", "integration_failed", "1732000000016"),
  automationPart("trigger", "position_reached", "1732000000017"),
  automationPart("trigger", "repair_issue_created", "1732000000018"),
  automationPart("trigger", "repair_issue_removed", "1732000000018", 1),
  automationPart("trigger", "target_temperature_reached", "1732000000019"),
  automationPart("trigger", "update_installed", "1732000000021"),
  automationPart("trigger", "script_started", "1732000000022"),
  automationPart("trigger", "state_changed", "1732000000023"),
  automationPart("trigger", "user_added", "1732000000024"),
  automationPart("trigger", "all_of", "1732000000025"),
  automationPart("trigger", "debounce", "1732000000026"),
  automationPart("trigger", "sequence", "1732000000027"),
  automationPart("trigger", "while", "1732000000028"),
  automationPart("trigger", "watchdog", "1732000000029"),
  automationPart("trigger", "flapping", "1732000000030"),
  automationPart("trigger", "condition_met", "1732000000031"),
];

const conditions: Shot[] = [
  automationPart("condition", "triggered_by_user", "1732000000010"),
  automationPart("condition", "not_triggered_by_user", "1732000000032"),
  automationPart("condition", "cooldown", "1732000000003"),
  automationPart("condition", "chance", "1732000000033"),
  automationPart("condition", "triggered_by_automation", "1732000000034"),
  automationPart("condition", "repair_issue_present", "1732000000035"),
  automationPart("condition", "is_at_target_temperature", "1732000000020"),
  automationPart("condition", "quota", "1732000000036"),
  automationPart("condition", "is_available", "1732000000037"),
];

// Spook's helpers that set up in one step, filled in.
const helpers: Shot[] = [
  helperForm("spook_calibration", (name) => ({
    name: name("examples.calibration"),
    entity_id: "sensor.living_room_thermometer",
    offset: -1.5,
    factor: 1,
  })),
  helperForm("spook_time_in_state", (name) => ({
    name: name("examples.time_in_state"),
    entity_id: "binary_sensor.front_door",
    states: ["off"],
  })),
];

/** The row of the blueprint update among the updates on the Settings page. */
function blueprintUpdateRow(page: Page, language: string): Locator {
  return page
    .locator("ha-config-updates")
    .locator("ha-list-item-button")
    .filter({ hasText: names(language).name("blueprints.door_light.name") })
    .first();
}

// The rest: things Spook adds to pages of Home Assistant, and pages the
// guides walk through.
const more: Shot[] = [
  {
    // Where a blueprint update shows up: at the top of Settings, with the
    // other updates.
    name: "blueprint-update-row",
    path: "/config/dashboard",
    async prepare(page, language) {
      await blueprintUpdateRow(page, language).waitFor();
    },
    target: (page) =>
      page
        .locator("ha-card.dashboard-alert-card")
        .filter({ has: page.locator("ha-config-updates") }),
    padding: 16,
    viewport: { width: 1000, height: 800 },
  },
  {
    // The update of a blueprint, opened: where it came from, what changed.
    name: "blueprint-update-dialog",
    path: "/config/dashboard",
    async prepare(page, language) {
      await blueprintUpdateRow(page, language).click();
      const dialog = page.locator("ha-more-info-dialog");
      await dialog.getByRole("dialog").waitFor();
      // The notes arrive after the dialog opens.
      await dialog.locator("ha-markdown").first().waitFor();
      await page.waitForTimeout(1500);
    },
    target: (page) => page.locator("ha-more-info-dialog").getByRole("dialog"),
    cutout: true,
    viewport: { width: 1000, height: 1600 },
  },
  {
    // The menu of Spook's entry, on its integration page: the row called
    // Your homie.
    name: "spook-entry-menu",
    path: "/config/integrations/integration/spook",
    async prepare(page) {
      const entry = page
        .locator("ha-config-entry-row")
        .filter({ hasText: /Your homie/ })
        .first();
      await entry.waitFor();
      // The first menu is the entry's own; the devices under it have theirs.
      const menu = entry.locator("ha-dropdown").first();
      await menu.locator("ha-icon-button[slot=trigger]").click();
      await menu.locator("ha-dropdown-item").last().waitFor();
      await page.waitForTimeout(500);
    },
    // The row, and its menu down to the last item.
    target: (page) => {
      const entry = page
        .locator("ha-config-entry-row")
        .filter({ hasText: /Your homie/ })
        .first();
      const items = entry
        .locator("ha-dropdown")
        .first()
        .locator("ha-dropdown-item");
      return [
        entry.locator("ha-row-item").first(),
        items.first(),
        items.last(),
      ];
    },
    padding: 8,
    viewport: { width: 1000, height: 800 },
  },
  {
    // The repairs list down to Movie night, the one the guides start with,
    // ringed.
    name: "repairs-list-movie-night",
    path: "/config/repairs",
    async prepare(page, language) {
      const row = movieNightRepair(page, language);
      await highlight(row);
      // Marked, so `until` finds it again without knowing the language.
      await row.evaluate((element) => element.setAttribute("data-shot", ""));
    },
    target: (page) =>
      page.locator("ha-config-repairs-dashboard").locator("ha-card").first(),
    until: (page) => page.locator("[data-shot]"),
    cutout: true,
    // Tall enough for Movie night, a dozen repairs down.
    viewport: { width: 1000, height: 1800 },
  },
  {
    // Movie night in the editor: the lamps it turns off are gone, and show
    // as their bare IDs.
    name: "automation-movie-night",
    path: "/config/automation/edit/1732000000002",
    target: (page) => page.locator("manual-automation-editor"),
    padding: 0,
    viewport: { width: 760, height: 800 },
  },
  {
    // A time in state sensor at work, with what it remembers.
    name: "time-in-state-sensor",
    path: "/config/entities",
    async prepare(page) {
      await page.evaluate(() =>
        document.querySelector("home-assistant")!.dispatchEvent(
          new CustomEvent("hass-more-info", {
            detail: { entityId: "sensor.front_door_closed_since" },
            bubbles: true,
            composed: true,
          }),
        ),
      );
      const dialog = page.locator("ha-more-info-dialog");
      await dialog.getByRole("dialog").waitFor();
      const attributes = dialog.locator("ha-attributes ha-expansion-panel");
      if (await attributes.count()) {
        await attributes.first().click();
      }
      await page.waitForTimeout(800);
    },
    target: (page) => page.locator("ha-more-info-dialog").getByRole("dialog"),
    cutout: true,
    viewport: { width: 1000, height: 1200 },
  },
];

/** The repair about Movie night in the list. */
function movieNightRepair(page: Page, language: string): Locator {
  return page
    .locator("ha-config-repairs-dashboard")
    .locator("ha-list-item-button")
    .filter({
      hasText: repairTitle(
        language,
        "automation_unknown_entity_references",
        names(language).name("automation.movie_night.name"),
      ),
    })
    .first();
}

const shots: Shot[] = [
  ...actions,
  ...triggers,
  ...conditions,
  ...helpers,
  ...more,
  ...searches,
  ...repairs,
  {
    // Installing: Spook found in the Marketplace.
    name: "marketplace-search",
    path: "/marketplace",
    async prepare(page) {
      await agreeToTheMarketplace(page);
      // The name of a product, the same in every language.
      await page
        .locator("search-input input, ha-input-search input")
        .first()
        .fill("Spook");
      await page
        .getByText(/Your homie/)
        .first()
        .waitFor();
    },
    // The page down to the row of Spook, which is all it found.
    target: (page) => page.locator("hass-tabs-subpage-data-table"),
    until: (page) => page.getByText(/Your homie/).first(),
    padding: 0,
    viewport: { width: 1000, height: 700 },
  },
  {
    // Installing: Spook's page in the Marketplace, with its Install button.
    name: "marketplace-spook",
    path: "/marketplace",
    async prepare(page, language) {
      await agreeToTheMarketplace(page);
      await open(page, MARKETPLACE_SPOOK, language);
      await page.locator("ha-card").nth(2).waitFor();
    },
    target: (page) => [
      page.locator("ha-card").nth(0),
      page.locator("ha-card").nth(1),
      page.locator("ha-card").nth(2),
    ],
    padding: 16,
    viewport: { width: 960, height: 900 },
  },
  {
    // Setting up: Spook in the list of integrations to add.
    name: "add-integration-spook",
    path: "/config/integrations/dashboard",
    async prepare(page) {
      await page
        .getByRole("button", {
          name: await localize(
            page,
            "ui.panel.config.integrations.add_integration",
          ),
        })
        .first()
        .click();
      const dialog = page.locator("dialog-add-integration");
      await dialog.getByRole("textbox").waitFor();
      await page.waitForTimeout(500);
      await page.keyboard.type("Spook");
      await dialog.getByRole("button", { name: "Spook" }).waitFor();
    },
    target: (page) =>
      page.locator("dialog-add-integration").getByRole("dialog"),
    // Spook and its helpers, not the empty rest of the list.
    until: (page) =>
      page
        .locator("dialog-add-integration")
        .getByRole("button")
        .filter({ hasText: "Inverse" }),
    cutout: true,
  },
  {
    // The devices Spook adds, as their pages show them.
    name: "device-home-assistant",
    path: () => `/config/devices/device/${readState().devices.homeassistant}`,
    target: devicePage,
    padding: 0,
  },
  {
    name: "device-cloud",
    path: () => `/config/devices/device/${readState().devices.cloud}`,
    target: devicePage,
    padding: 0,
  },
  {
    name: "device-repairs",
    path: () => `/config/devices/device/${readState().devices.repairs}`,
    target: devicePage,
    padding: 0,
  },
  {
    // Inverse, the first step: what to invert.
    name: "helper-inverse-menu",
    path: "/config/helpers",
    prepare: (page, language) => startInverse(page, language),
    target: flowDialog,
    cutout: true,
  },
  {
    // Inverse, a switch: the form to fill in.
    name: "helper-inverse-switch",
    path: "/config/helpers",
    async prepare(page, language) {
      await startInverse(page, language);
      const options = helperTranslations("spook_inverse", language).config.step
        .user.menu_options;
      await page.getByText(options.switch, { exact: true }).click();
      await page.locator("dialog-data-entry-flow ha-form").waitFor();
      await page.waitForTimeout(500);
    },
    target: flowDialog,
    cutout: true,
  },
  {
    name: "repairs",
    path: "/config/repairs",
  },
  {
    // Only the list, readable at the size of a picture on a page.
    name: "repairs-list",
    path: "/config/repairs",
    target: (page) =>
      page.locator("ha-config-repairs-dashboard").locator("ha-card").first(),
    // Six is plenty to make the point, and the rest fades out.
    until: (page) =>
      page
        .locator("ha-config-repairs-dashboard")
        .locator("ha-card")
        .first()
        .getByRole("button")
        .nth(5),
    cutout: true,
  },
  {
    name: "repair-unknown-entities",
    path: "/config/repairs",
    async prepare(page, language) {
      await page
        .getByText(
          repairTitle(
            language,
            "automation_unknown_entity_references",
            names(language).name("automation.movie_night.name"),
          ),
        )
        .first()
        .click();
      await page.getByRole("dialog").waitFor();
    },
    target: (page) => page.getByRole("dialog"),
    cutout: true,
  },
  {
    // A repair Spook can fix itself, with the choices it offers.
    name: "repair-fix-empty-area",
    path: "/config/repairs",
    async prepare(page, language) {
      await page
        .getByText(repairTitle(language, "empty_areas"))
        .first()
        .click();
      await page.getByRole("dialog").waitFor();
    },
    target: (page) => page.getByRole("dialog"),
    cutout: true,
  },
  {
    // Spook's trigger and condition in an automation, next to a core action.
    name: "automation-editor",
    path: "/config/automation/edit/1732000000003",
    target: (page) => page.locator("manual-automation-editor"),
    padding: 0,
    viewport: { width: 760, height: 800 },
  },
  {
    name: "automation-cron",
    path: "/config/automation/edit/1732000000003",
    async prepare(page, language) {
      await page
        .locator("manual-automation-editor")
        .getByText(spook(language).triggers.cron.name, { exact: true })
        .click();
      await page.locator("ha-automation-sidebar").waitFor();
    },
    // The automation and the trigger opened next to it, down to its field.
    target: (page) => [
      page.locator("manual-automation-editor"),
      page.locator("ha-automation-sidebar"),
    ],
    until: (page) =>
      page
        .locator("ha-automation-sidebar")
        .locator("ha-textfield, ha-input")
        .first(),
    padding: 0,
  },
  {
    // Everything Spook adds to automations: search for its ghost.
    name: "actions-ghost-search",
    path: "/config/automation/edit/new",
    async prepare(page) {
      await searchForTheGhost(
        page,
        "ui.panel.config.automation.editor.actions.add",
      );
      await page
        .locator("ha-automation-add-search ha-list-item-button")
        .nth(5)
        .waitFor();
    },
    target: (page) =>
      page.locator("add-automation-element-dialog").getByRole("dialog"),
    until: (page) =>
      page.locator("ha-automation-add-search ha-list-item-button").nth(5),
    cutout: true,
  },
  {
    // The same for helpers: Spook's own, all at once.
    name: "helpers-ghost-search",
    path: "/config/helpers",
    async prepare(page) {
      await searchForTheGhost(
        page,
        "ui.panel.config.helpers.picker.create_helper",
      );
      await spookOptions(page).nth(2).waitFor();
    },
    // The page has more dialogs, hidden ones: this is the helper dialog.
    target: (page) => page.locator("dialog-helper-detail").getByRole("dialog"),
    until: (page) => spookOptions(page).last(),
    cutout: true,
  },
  {
    // Your home, counted: the diagnostic sensors of Spook's Home Assistant
    // device.
    name: "home-assistant-numbers",
    path: () => `/config/devices/device/${readState().devices.homeassistant}`,
    // The diagnostic sensors come last, in a card of their own.
    target: (page) =>
      page.locator("ha-device-entities-card").last().locator("ha-card"),
    until: (page) =>
      page
        .locator("ha-device-entities-card")
        .last()
        .locator("state-badge")
        .nth(6),
    cutout: true,
  },
  {
    name: "spook-integration",
    path: "/config/integrations/integration/spook",
  },
  {
    // Step by step what the guide says: add an action, search for snooze.
    name: "action-snooze",
    path: "/config/automation/edit/new",
    async prepare(page, language) {
      const addAction = await localize(
        page,
        "ui.panel.config.automation.editor.actions.add",
      );
      await page
        .locator("manual-automation-editor")
        .getByRole("button", { name: addAction, exact: true })
        .click();

      const dialog = page.locator("add-automation-element-dialog");
      const snooze = spook(language).services.automation_snooze.name;
      await dialog.locator("ha-input-search input").fill(snooze);

      const result = dialog
        .locator("ha-automation-add-search ha-list-item-button")
        .filter({ hasText: snooze })
        .first();
      await result.waitFor();
      await highlight(result);
    },
    target: (page) =>
      page.locator("add-automation-element-dialog").getByRole("dialog"),
    until: (page) =>
      page
        .locator("add-automation-element-dialog")
        .locator("ha-automation-add-search ha-list-item-button")
        .first(),
    cutout: true,
  },
  {
    // The Spook theme, on a dashboard and in the automation editor.
    name: "theme-spook-dashboard",
    path: "/lovelace/0",
    theme: "Spook",
  },
  {
    name: "theme-spook-automations",
    path: "/config/automation/dashboard",
    theme: "Spook",
  },
];

/** The part of the window around a target, to crop the picture to. */
async function around(
  page: Page,
  target: Locator | Locator[],
  until: Locator | undefined,
  padding: number,
) {
  const window = page.viewportSize();
  const boxes = await Promise.all(
    [target].flat().map((locator) => locator.boundingBox()),
  );
  if (!window || boxes.some((box) => !box)) {
    throw new Error("Nothing to crop to: the target is not on the page");
  }

  // One box around everything the shot is about.
  const found = boxes as {
    x: number;
    y: number;
    width: number;
    height: number;
  }[];
  const x = Math.min(...found.map((box) => box.x));
  const y = Math.min(...found.map((box) => box.y));
  const box = {
    x,
    y,
    width: Math.max(...found.map((box) => box.x + box.width)) - x,
    height: Math.max(...found.map((box) => box.y + box.height)) - y,
  };

  let end = box.y + box.height + padding;
  let cut = false;
  if (until) {
    const stop = await until.boundingBox();
    // The fade needs room of its own, below what the shot is about.
    const room = Math.max(padding, FADE);
    if (stop && stop.y + stop.height + room < end) {
      end = stop.y + stop.height + room;
      cut = true;
    }
  }

  const left = Math.max(0, box.x - padding);
  const top = Math.max(0, box.y - padding);
  const right = Math.min(window.width, box.x + box.width + padding);
  const bottom = Math.min(window.height, end);
  return {
    clip: { x: left, y: top, width: right - left, height: bottom - top },
    cut,
  };
}

/**
 * Keep only what is inside the rounded edge of the target, and make the
 * rest transparent. A target cut short by `until` has no bottom edge in the
 * picture, so it fades out there instead of ending on a hard line.
 */
async function cutOut(
  picture: Buffer,
  radius: number,
  fade: number,
): Promise<Buffer> {
  const { width = 0, height = 0 } = await sharp(picture).metadata();
  const cut = fade > 0;

  // At a cut, the shape runs on below the picture: no rounded corners there.
  const shapeHeight = cut ? height + radius : height;
  const shape = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">
    <defs>
      <linearGradient id="fade" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="${height}">
        <stop offset="0" stop-color="#fff"/>
        <stop offset="${(height - fade) / height}" stop-color="#fff"/>
        <stop offset="1" stop-color="#fff" stop-opacity="${cut ? 0 : 1}"/>
      </linearGradient>
    </defs>
    <rect width="${width}" height="${shapeHeight}" rx="${radius}" fill="url(#fade)"/>
  </svg>`;

  return sharp(picture)
    .ensureAlpha()
    .composite([{ input: Buffer.from(shape), blend: "dest-in" }])
    .toBuffer();
}

/** Open a page and wait until Home Assistant has fully drawn it. */
async function open(page: Page, path: string, language: string) {
  await page.goto(path);
  await page.waitForFunction((expected) => {
    const hass = (document.querySelector("home-assistant") as any)?.hass;
    return hass?.connected && hass.language === expected && hass.localize;
  }, language);
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);
}

test.beforeEach(async ({ context }, testInfo) => {
  const { language, theme } = testInfo.project.metadata;
  const { tokens } = readState();
  const shot = shots.find((candidate) => candidate.name === testInfo.title);

  // What the frontend would have stored after logging in and picking a
  // theme and a language in the profile. One script for all of it: the
  // order Playwright runs several in is not defined.
  await context.addInitScript(
    ({ tokens, language, name, dark }) => {
      localStorage.setItem("hassTokens", JSON.stringify(tokens));
      localStorage.setItem(
        "selectedTheme",
        JSON.stringify({ theme: name, dark }),
      );
      localStorage.setItem("selectedLanguage", JSON.stringify(language));
    },
    {
      tokens,
      language,
      name: shot?.theme ?? "default",
      dark: theme === "dark",
    },
  );
});

for (const shot of shots) {
  test(shot.name, async ({ page }, testInfo) => {
    const { language, theme } = testInfo.project.metadata;

    if (shot.viewport) {
      await page.setViewportSize(shot.viewport);
    }
    const path = typeof shot.path === "function" ? shot.path() : shot.path;
    await open(page, path, language);
    if (shot.theme) {
      // Home Assistant puts the theme on after the page is drawn.
      await page.waitForFunction(
        (name) =>
          (document.querySelector("home-assistant") as any)?.hass?.themes
            ?.theme === name,
        shot.theme,
      );
    }
    await shot.prepare?.(page, language);

    // No hover effect on whatever the mouse last touched, and a moment for
    // ripples, toasts and lazy images to settle before the picture.
    await page.mouse.move(0, 0);
    await page.waitForTimeout(500);

    const crop = shot.target
      ? await around(
          page,
          shot.target(page, language),
          shot.until?.(page),
          shot.cutout ? 0 : (shot.padding ?? PADDING),
        )
      : undefined;
    let picture = await page.screenshot({
      clip: crop?.clip,
      animations: "disabled",
      caret: "hide",
    });

    if (shot.cutout && shot.target && crop) {
      const element = [shot.target(page, language)].flat()[0];
      const radius = await element.evaluate((node) =>
        parseFloat(getComputedStyle(node).borderTopLeftRadius),
      );
      const { width = 0 } = await sharp(picture).metadata();
      const scale = width / crop.clip.width;
      picture = await cutOut(
        picture,
        (radius || 0) * scale,
        crop.cut ? FADE * scale : 0,
      );
    }

    // Lossless WebP: the same pixels as the PNG, at about a third of the
    // size, and it keeps the transparency of a cut-out.
    const folder = join(output, language, theme);
    mkdirSync(folder, { recursive: true });
    await sharp(picture)
      .webp({ lossless: true, effort: 6 })
      .toFile(join(folder, `${shot.name}.webp`));
  });
}
