/**
 * A throwaway Home Assistant in Docker, onboarded and spooked, for the
 * screenshots on the website.
 *
 * Talks to Home Assistant the way the frontend does: the onboarding API to
 * create the user, and the websocket API for everything after that.
 */
import { execFileSync } from "node:child_process";
import {
  cpSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { areaIds, entityIds, names } from "./names";

const here = dirname(fileURLToPath(import.meta.url));

export const CONTAINER = "spook-screenshots";
export const IMAGE =
  process.env.HA_IMAGE ?? "ghcr.io/home-assistant/home-assistant:stable";
export const PORT = Number(process.env.HA_PORT ?? 18123);
export const BASE_URL = `http://127.0.0.1:${PORT}`;

// The language of this run. run.ts sets it, one language after the other.
export const LANGUAGE = process.env.SCREENSHOTS_LANGUAGE ?? "en";

// The person in the screenshots. Their GitHub avatar becomes the picture
// of the Home Assistant user, so the sidebar shows a real face.
export const OWNER = {
  name: process.env.HA_OWNER_NAME ?? "Franck Nijhof",
  username: process.env.HA_OWNER_USERNAME ?? "frenck",
  github: process.env.HA_OWNER_GITHUB ?? "frenck",
};

// Handed from the setup to the screenshots, never committed.
const STATE_FILE = join(here, ".state", "home-assistant.json");

const SEED = join(here, "seed");
const NAMES = join(SEED, "names");
// The seed with the names of one language filled in, never committed.
const FILLED_SEED = join(here, ".state", "seed");

// The seed files Home Assistant can reload while it runs, so the entities in
// them can get the names of the language after their IDs are set.
const RELOADABLE = [
  "configuration.yaml",
  "automations.yaml",
  "scripts.yaml",
  "scenes.yaml",
];
const RELOAD_DOMAINS = [
  "input_boolean",
  "input_number",
  "input_select",
  "template",
  "group",
  "automation",
  "script",
  "scene",
];

export interface Tokens {
  hassUrl: string;
  clientId: string;
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  expires: number;
}

function docker(...args: string[]): string {
  return execFileSync("docker", args, { encoding: "utf-8" }).trim();
}

/**
 * Fill the names of a language into a copy of the seed. The names files
 * themselves stay out: Home Assistant has no use for them.
 */
function fillSeed(language: string, options: { asIds: boolean }): void {
  const { fill } = names(language);
  rmSync(FILLED_SEED, { recursive: true, force: true });
  cpSync(SEED, FILLED_SEED, {
    recursive: true,
    filter: (source) => !source.startsWith(NAMES),
  });

  for (const file of readdirSync(FILLED_SEED, { recursive: true })) {
    const path = join(FILLED_SEED, String(file));
    if (statSync(path).isFile()) {
      writeFileSync(path, fill(readFileSync(path, "utf-8"), options));
    }
  }
}

/**
 * Start a fresh Home Assistant with the seed config and Spook in it, in a
 * language from the very start: Home Assistant names the entities of an
 * integration in the language it has when that integration sets up, and
 * never again after.
 */
export function startContainer(language: string): void {
  docker("rm", "--force", CONTAINER);
  docker("pull", "--quiet", IMAGE);
  docker(
    "create",
    "--name",
    CONTAINER,
    "--publish",
    `127.0.0.1:${PORT}:8123`,
    "--env",
    "TZ=Europe/Amsterdam",
    // Spook skips the waits that keep it patient in a real home, like the
    // first look for blueprint updates, so they show up during the run.
    "--env",
    "SPOOK_SCREENSHOT_HOME=1",
    IMAGE,
  );

  // Copied in rather than mounted: Home Assistant runs as root in the
  // container, and a mounted folder would fill up with files you need root
  // to delete afterwards. Its config, with the language in it, is part of
  // the seed. The entities in the YAML start out named after their IDs, see
  // nameEverything().
  fillSeed(language, { asIds: true });
  docker("cp", `${FILLED_SEED}/.`, `${CONTAINER}:/config/`);
  // Into the folder the seed may already have made, next to the small
  // integrations of its own.
  docker(
    "cp",
    `${join(here, "..", "..", "custom_components")}/.`,
    `${CONTAINER}:/config/custom_components`,
  );

  // The manifest in the repository says 0.0.0 until a release stamps it.
  // Home Assistant blocks Spook below 4.0.0, so the copy gets the version
  // of the latest release.
  const manifestPath = join(
    here,
    "..",
    "..",
    "custom_components",
    "spook",
    "manifest.json",
  );
  const manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
  manifest.version = execFileSync("git", ["describe", "--tags", "--abbrev=0"], {
    encoding: "utf-8",
  })
    .trim()
    .replace(/^v/, "");
  const stamped = join(here, ".state", "manifest.json");
  mkdirSync(dirname(stamped), { recursive: true });
  writeFileSync(stamped, JSON.stringify(manifest, null, 2));
  docker(
    "cp",
    stamped,
    `${CONTAINER}:/config/custom_components/spook/manifest.json`,
  );

  docker("start", CONTAINER);
}

export function stopContainer(): void {
  docker("rm", "--force", CONTAINER);
}

export function homeAssistantVersion(): string {
  return docker(
    "exec",
    CONTAINER,
    "python3",
    "-c",
    "import homeassistant.const as c; print(c.__version__)",
  );
}

async function waitFor<T>(
  what: string,
  check: () => Promise<T | undefined>,
  timeout = 180_000,
): Promise<T> {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try {
      const result = await check();
      if (result !== undefined) {
        return result;
      }
    } catch {
      // Not there yet. Home Assistant refuses connections while it starts.
    }
    await new Promise((resolve) => setTimeout(resolve, 1_000));
  }
  throw new Error(`Gave up waiting for ${what}`);
}

async function post(path: string, body: unknown, token?: string): Promise<any> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`${path}: ${response.status} ${await response.text()}`);
  }
  return response.json();
}

/** A websocket connection, the way the frontend talks to Home Assistant. */
export async function connect(accessToken: string) {
  const socket = new WebSocket(
    `${BASE_URL.replace(/^http/, "ws")}/api/websocket`,
  );
  const pending = new Map<
    number,
    { resolve: (value: any) => void; reject: (error: Error) => void }
  >();
  let lastId = 0;

  await new Promise<void>((resolve, reject) => {
    socket.onerror = () => reject(new Error("Websocket failed"));
    socket.onmessage = (event) => {
      const message = JSON.parse(String(event.data));

      if (message.type === "auth_required") {
        socket.send(
          JSON.stringify({ type: "auth", access_token: accessToken }),
        );
      } else if (message.type === "auth_ok") {
        resolve();
      } else if (message.type === "auth_invalid") {
        reject(new Error(message.message));
      } else if (message.type === "result") {
        const call = pending.get(message.id);
        pending.delete(message.id);
        if (message.success) {
          call?.resolve(message.result);
        } else {
          call?.reject(new Error(JSON.stringify(message.error)));
        }
      }
    };
  });

  return {
    call<T = any>(type: string, data: object = {}): Promise<T> {
      const id = ++lastId;
      return new Promise((resolve, reject) => {
        pending.set(id, { resolve, reject });
        socket.send(JSON.stringify({ id, type, ...data }));
      });
    },
    close: () => socket.close(),
  };
}

/**
 * Walk through onboarding in a language, and hand back tokens for the owner.
 * Home Assistant creates its first rooms in that language here.
 */
async function onboard(language: string): Promise<Tokens> {
  const clientId = `${BASE_URL}/`;

  await waitFor("Home Assistant to start", async () => {
    const response = await fetch(`${BASE_URL}/api/onboarding`);
    return response.ok ? true : undefined;
  });

  const { auth_code } = await post("/api/onboarding/users", {
    client_id: clientId,
    name: OWNER.name,
    username: OWNER.username,
    // Nobody logs in with it: the container is gone after the run.
    password: crypto.randomUUID(),
    language,
  });

  const response = await fetch(`${BASE_URL}/auth/token`, {
    method: "POST",
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code: auth_code,
      client_id: clientId,
    }),
  });
  const token = await response.json();

  await post("/api/onboarding/core_config", {}, token.access_token);
  await post("/api/onboarding/analytics", {}, token.access_token);
  await post(
    "/api/onboarding/integration",
    { client_id: clientId, redirect_uri: `${BASE_URL}/?auth_callback=1` },
    token.access_token,
  );

  return {
    hassUrl: BASE_URL,
    clientId,
    access_token: token.access_token,
    refresh_token: token.refresh_token,
    token_type: token.token_type,
    expires_in: token.expires_in,
    expires: Date.now() + token.expires_in * 1000,
  };
}

/**
 * Give the owner their GitHub avatar as the picture of their person. Their
 * person also still tracks a phone that is long gone, for Spook to find.
 */
async function setUpOwner(
  connection: Awaited<ReturnType<typeof connect>>,
  accessToken: string,
): Promise<void> {
  const avatar = await fetch(`https://github.com/${OWNER.github}.png?size=512`);
  const form = new FormData();
  form.append(
    "file",
    new Blob([await avatar.arrayBuffer()], { type: "image/png" }),
    "avatar.png",
  );

  const upload = await fetch(`${BASE_URL}/api/image/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` },
    body: form,
  });
  const image = await upload.json();

  const { storage } = await connection.call("person/list");
  const person = storage.find(
    (candidate: { name: string }) => candidate.name === OWNER.name,
  );
  await connection.call("person/update", {
    person_id: person.id,
    picture: `/api/image/serve/${image.id}/512x512`,
    device_trackers: ["device_tracker.old_phone"],
  });
}

/**
 * Give everything in the YAML of the seed its name in the language. Home
 * Assistant made the entity IDs out of the names they started with, their
 * object IDs, and keeps those IDs when a name changes after.
 */
async function nameEverything(
  connection: Awaited<ReturnType<typeof connect>>,
  language: string,
): Promise<void> {
  // Onboarding opens before everything is set up, and only what is set up
  // can reload.
  await waitFor("Home Assistant to finish starting", async () => {
    const config = await connection.call("get_config");
    return config.state === "RUNNING" ? true : undefined;
  });

  fillSeed(language, { asIds: false });
  for (const file of RELOADABLE) {
    docker("cp", join(FILLED_SEED, file), `${CONTAINER}:/config/${file}`);
  }
  for (const domain of RELOAD_DOMAINS) {
    await connection.call("call_service", { domain, service: "reload" });
  }

  // A second place to be, next to home. A zone in YAML gets its ID from its
  // name every time Home Assistant starts, so this one is made here, under
  // its ID first, and named after.
  const gym = {
    icon: "mdi:dumbbell",
    latitude: 52.3731,
    longitude: 4.8922,
    radius: 150,
  };
  const zone = await connection.call("zone/create", { name: "gym", ...gym });
  await connection.call("zone/update", {
    zone_id: zone.id,
    name: names(language).name("zone.gym"),
    ...gym,
  });

  // Helpers made in the UI, the only kind the actions that delete one can
  // remove. Made the same way as the gym: under their ID, named after.
  for (const [domain, helpers] of Object.entries(UI_HELPERS)) {
    for (const [objectId, fields] of Object.entries(helpers)) {
      const helper = await connection.call(`${domain}/create`, {
        name: objectId,
        ...fields,
      });
      await connection.call(`${domain}/update`, {
        [`${domain}_id`]: helper.id,
        name: names(language).name(`${domain}.${objectId}`),
        ...fields,
      });
    }
  }
}

// The helpers nameEverything() makes, by domain and object ID, with what
// they are set to.
const UI_HELPERS: Record<string, Record<string, Record<string, unknown>>> = {
  input_boolean: { guest_mode: { icon: "mdi:account-multiple" } },
  input_button: { doorbell: { icon: "mdi:doorbell" } },
  input_datetime: {
    alarm_clock: { has_date: false, has_time: true, icon: "mdi:alarm" },
  },
  input_text: {
    welcome_message: { min: 0, max: 100, mode: "text", icon: "mdi:message" },
  },
  counter: { coffee_cups: { initial: 0, step: 1, icon: "mdi:coffee" } },
  timer: { laundry: { duration: "01:15:00", icon: "mdi:washing-machine" } },
  schedule: {
    heating: {
      icon: "mdi:radiator",
      ...Object.fromEntries(
        ["monday", "tuesday", "wednesday", "thursday", "friday"].map((day) => [
          day,
          [
            { from: "06:30:00", to: "08:00:00" },
            { from: "17:00:00", to: "22:00:00" },
          ],
        ]),
      ),
      saturday: [{ from: "08:00:00", to: "23:00:00" }],
      sunday: [{ from: "08:00:00", to: "22:00:00" }],
    },
  },
};

// Entities that cannot reload, or come from a setup flow, so they get the
// name of the language through the entity registry instead.
const NAMED_IN_THE_REGISTRY = [
  "humidifier.basement_dehumidifier",
  "valve.garden_tap",
  "calendar.family",
  "todo.shopping_list",
];

/**
 * A family calendar and a shopping list, for the calendar and to-do
 * actions. Both only come from a setup flow, made under their ID like the
 * gym, and named in setUp() after.
 */
async function addCalendarAndList(accessToken: string): Promise<void> {
  for (const [handler, input] of [
    ["local_calendar", { calendar_name: "family" }],
    ["local_todo", { todo_list_name: "shopping_list" }],
  ] as const) {
    const flow = await post(
      "/api/config/config_entries/flow",
      { handler, show_advanced_options: false },
      accessToken,
    );
    await post(
      `/api/config/config_entries/flow/${flow.flow_id}`,
      input,
      accessToken,
    );
  }
}

async function nameInTheRegistry(
  connection: Awaited<ReturnType<typeof connect>>,
  language: string,
): Promise<void> {
  for (const entityId of NAMED_IN_THE_REGISTRY) {
    await waitFor(`${entityId} to show up`, async () => {
      const states: { entity_id: string }[] =
        await connection.call("get_states");
      return states.some((state) => state.entity_id === entityId)
        ? true
        : undefined;
    });
    await connection.call("config/entity_registry/update", {
      entity_id: entityId,
      name: names(language).name(entityId),
    });
  }
}

/**
 * Check the home came out the same in every language: every entity of the
 * names file under its own ID, and no room twice because onboarding named
 * one differently than the seed.
 */
async function checkTheHome(
  connection: Awaited<ReturnType<typeof connect>>,
): Promise<void> {
  const states: { entity_id: string }[] = await connection.call("get_states");
  const present = new Set(states.map((state) => state.entity_id));
  const missing = entityIds().filter((entityId) => !present.has(entityId));
  if (missing.length) {
    throw new Error(`Not in Home Assistant: ${missing.join(", ")}`);
  }

  const areas: unknown[] = await connection.call("config/area_registry/list");
  const expected = areaIds().length;
  if (areas.length !== expected) {
    throw new Error(
      `${areas.length} areas instead of ${expected}: onboarding created ` +
        "rooms of its own. Use its names for them in seed/names.",
    );
  }
}

/** Put the lamps of the seed config in their rooms, like a lived-in home. */
async function furnish(
  connection: Awaited<ReturnType<typeof connect>>,
  language: string,
): Promise<void> {
  const rooms: Record<string, string> = {
    "light.living_room_lamp": "living_room",
    "light.kitchen_lights": "kitchen",
    "light.hallway_light": "hallway",
    "light.bedroom_lamp": "bedroom",
    "binary_sensor.front_door": "hallway",
  };

  for (const [entityId, areaId] of Object.entries(rooms)) {
    await connection.call("config/entity_registry/update", {
      entity_id: entityId,
      area_id: areaId,
      labels: entityId === "light.hallway_light" ? ["night_light"] : [],
    });
  }

  // The lighting automations in their category, on the automations page.
  for (const entityId of [
    "automation.hallway_light_at_sunset",
    "automation.weekday_morning_lights",
  ]) {
    await connection.call("config/entity_registry/update", {
      entity_id: entityId,
      categories: { automation: "lighting" },
    });
  }

  // Somebody else in the house, for the user actions to turn off and on.
  await connection.call("config/auth/create", {
    name: names(language).name("user.babysitter"),
    group_ids: ["system-users"],
  });

  // A phone for the person actions to hand to someone. The old phone the
  // person still has on file is gone, which Spook should find.
  await connection.call("call_service", {
    domain: "device_tracker",
    service: "see",
    service_data: {
      dev_id: "new_phone",
      host_name: names(language).name("device_tracker.new_phone"),
    },
  });
}

/**
 * Leave the traces Spook finds in a home that has been lived in for a while:
 * history of a meter that is gone, an energy dashboard still counting a
 * washing machine that is gone too, a dashboard resource added twice, and a
 * blueprint downloaded days ago that nothing uses.
 */
async function leaveTraces(
  connection: Awaited<ReturnType<typeof connect>>,
): Promise<void> {
  // Without a name, the way a sensor writes its own: Spook takes statistics
  // with a name for something an integration published on purpose.
  const twoHoursAgo = new Date(Date.now() - 2 * 3_600_000);
  twoHoursAgo.setMinutes(0, 0, 0);
  await connection.call("recorder/import_statistics", {
    metadata: {
      has_sum: true,
      mean_type: 0,
      name: null,
      source: "recorder",
      statistic_id: "sensor.old_gas_meter",
      unit_of_measurement: "m³",
    },
    stats: [{ start: twoHoursAgo.toISOString(), state: 1204.3, sum: 1204.3 }],
  });

  await connection.call("energy/save_prefs", {
    device_consumption: [
      { stat_consumption: "sensor.old_washing_machine_energy" },
    ],
  });

  for (let copy = 0; copy < 2; copy++) {
    await connection.call("lovelace/resources/create", {
      res_type: "module",
      url: "/local/ghost-card.js",
    });
  }

  // Spook leaves a blueprint alone for a day after it arrives.
  docker(
    "exec",
    CONTAINER,
    "python3",
    "-c",
    "import os, time; then = time.time() - 2 * 86400; " +
      "os.utime('/config/blueprints/automation/spook/doorbell_flash.yaml', (then, then))",
  );
}

/**
 * A time in state sensor that has been running, for its page to show what
 * one looks like. Made under its ID like the gym, named after.
 */
async function addTimeInState(
  connection: Awaited<ReturnType<typeof connect>>,
  accessToken: string,
  language: string,
): Promise<void> {
  const flow = await post(
    "/api/config/config_entries/flow",
    { handler: "spook_time_in_state", show_advanced_options: false },
    accessToken,
  );
  await post(
    `/api/config/config_entries/flow/${flow.flow_id}`,
    {
      name: "front_door_closed_since",
      entity_id: "binary_sensor.front_door",
      states: ["off"],
    },
    accessToken,
  );
  await waitFor("the time in state sensor", async () => {
    const states: { entity_id: string }[] = await connection.call("get_states");
    return states.some(
      (state) => state.entity_id === "sensor.front_door_closed_since",
    )
      ? true
      : undefined;
  });
  await connection.call("config/entity_registry/update", {
    entity_id: "sensor.front_door_closed_since",
    name: names(language).name("examples.time_in_state"),
  });
}

/**
 * Wait until Spook offers the update of the seed's blueprint, and give it
 * the entity ID the seed's Update installed automation targets. Spook names
 * it after the blueprint, which is in the language of the run.
 */
async function waitForBlueprintUpdate(
  connection: Awaited<ReturnType<typeof connect>>,
): Promise<void> {
  const entityId = await waitFor(
    "Spook to offer the blueprint update",
    async () => {
      const states: { entity_id: string; state: string }[] =
        await connection.call("get_states");
      return states.find(
        (state) =>
          state.entity_id.startsWith("update.") && state.state === "on",
      )?.entity_id;
    },
  );
  if (entityId !== "update.door_light") {
    await connection.call("config/entity_registry/update", {
      entity_id: entityId,
      new_entity_id: "update.door_light",
    });
  }

  // Until then, Spook rightly says that automation targets an update that
  // does not exist. It looks again by itself.
  await waitFor("Spook to find the blueprint update", async () => {
    const { issues } = await connection.call("repairs/list_issues");
    return issues.some((issue: { issue_id: string }) =>
      issue.issue_id.includes("automation.update_installed"),
    )
      ? undefined
      : true;
  });
}

/** Add Spook the way a user does: through its setup flow. */
async function addSpook(accessToken: string): Promise<void> {
  const flow = await post(
    "/api/config/config_entries/flow",
    { handler: "spook", show_advanced_options: false },
    accessToken,
  );
  await post(
    `/api/config/config_entries/flow/${flow.flow_id}`,
    {},
    accessToken,
  );
}

/**
 * Wait until Spook raised the repairs the seed config is built to cause,
 * so no screenshot is taken of a repairs dashboard that is still filling up.
 */
async function waitForRepairs(
  connection: Awaited<ReturnType<typeof connect>>,
  expected: string[],
): Promise<void> {
  await waitFor("Spook to raise its repairs", async () => {
    const { issues } = await connection.call("repairs/list_issues");
    const raised = new Set(
      issues
        .filter((issue: { domain: string }) => issue.domain === "spook")
        .map((issue: { translation_key: string }) => issue.translation_key),
    );
    return expected.every((key) => raised.has(key)) ? true : undefined;
  });
}

/**
 * Ignore every repair that is not Spook's, like Home Assistant pointing out
 * the old way the seed makes its phone. The pictures are about Spook.
 */
async function ignoreOthers(
  connection: Awaited<ReturnType<typeof connect>>,
): Promise<void> {
  const { issues } = await connection.call("repairs/list_issues");
  for (const issue of issues) {
    if (issue.domain !== "spook" && !issue.ignored) {
      await connection.call("repairs/ignore_issue", {
        domain: issue.domain,
        issue_id: issue.issue_id,
        ignore: true,
      });
    }
  }
}

/**
 * Spook signs everything with a 👻. Without a color emoji font, Chrome on
 * Linux draws an empty box instead, in every screenshot.
 */
function checkEmojiFont(): void {
  let families: string;
  try {
    families = execFileSync("fc-list", [":", "family"], { encoding: "utf-8" });
  } catch {
    // No fontconfig, so not Linux: the system has emoji of its own.
    return;
  }
  if (!/color emoji/i.test(families)) {
    throw new Error(
      "No color emoji font found. Install one first, like Noto Color Emoji " +
        "(fonts-noto-color-emoji on Debian and Ubuntu).",
    );
  }
}

export async function setUp(language: string): Promise<void> {
  checkEmojiFont();
  startContainer(language);
  const tokens = await onboard(language);
  const connection = await connect(tokens.access_token);

  await nameEverything(connection, language);
  await addCalendarAndList(tokens.access_token);
  await nameInTheRegistry(connection, language);
  await setUpOwner(connection, tokens.access_token);
  await furnish(connection, language);
  await checkTheHome(connection);
  await leaveTraces(connection);

  // Last, so Spook finds the home with its names in the language already.
  await addSpook(tokens.access_token);
  await addTimeInState(connection, tokens.access_token, language);

  // One of each ghost hidden in the seed config.
  await waitForRepairs(connection, [
    "automation_unknown_entity_references",
    "lovelace_unknown_entity_references",
    "empty_areas",
    "empty_floors",
    "unused_labels",
    "unknown_area_sensors_temperature",
    "person_unknown_device_trackers",
    "automation_unknown_area_references",
    "automation_unknown_device_references",
    "script_unknown_entity_references",
    "script_unknown_area_references",
    "script_unknown_device_references",
    "scene_unknown_entity_references",
    "group_unknown_members",
    "orphaned_statistics",
    "lovelace_duplicate_resources",
    "energy_unknown_references",
    "unknown_icons",
    "unused_blueprints",
  ]);
  await waitForBlueprintUpdate(connection);
  await ignoreOthers(connection);

  // The seed has automations that tell you about new devices, users and
  // repairs, and setting all this up made plenty of those. Not in a picture.
  await connection.call("call_service", {
    domain: "persistent_notification",
    service: "dismiss_all",
  });

  // Spook's own devices, by what they are, for shots of their pages.
  const registry = await connection.call("config/device_registry/list");
  const devices = Object.fromEntries(
    registry.flatMap(
      (device: { id: string; identifiers: [string, string][] }) =>
        device.identifiers
          .filter(([domain]) => domain === "spook")
          .map(([, kind]) => [kind, device.id]),
    ),
  );
  connection.close();

  mkdirSync(dirname(STATE_FILE), { recursive: true });
  writeFileSync(
    STATE_FILE,
    JSON.stringify(
      { tokens, devices, version: homeAssistantVersion() },
      null,
      2,
    ),
  );
}

export function readState(): {
  tokens: Tokens;
  devices: Record<string, string>;
  version: string;
} {
  return JSON.parse(readFileSync(STATE_FILE, "utf-8"));
}
