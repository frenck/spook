/**
 * How a card, card feature or badge of Spook tells the frontend it exists.
 *
 * Every file in `elements/` has a default export made with one of the three
 * `define*` functions below. The entry finds those files by itself and hands
 * them to `registerAll`. Nothing else knows the list.
 *
 * The tag is what people write in their dashboards, after `custom:`. So it
 * is forever once shipped, and the types hold it to the rule: `spook-`
 * first, what it is last. See "Naming" in `frontend/README.md`.
 */
import type { HassEntity, HomeAssistant } from "@spook/shared/hass";

type CardTag = `spook-${string}-card`;
type CardFeatureTag = `spook-${string}-feature`;
type BadgeTag = `spook-${string}-badge`;

/** What the card picker and the badge picker offer for an entity. */
interface Suggestion {
  label?: string;
  config: { type: string; [key: string]: unknown };
}

type GetEntitySuggestion = (
  hass: HomeAssistant,
  entityId: string,
) => Suggestion | Suggestion[] | null;

/**
 * An entry of `window.customCards`, the card picker. The same shape for
 * `window.customBadges`, the badge picker.
 */
interface PickerEntry {
  type: string;
  name: string;
  description?: string;
  preview?: boolean;
  documentationURL?: string;
  getEntitySuggestion?: GetEntitySuggestion;
}

/** What a card feature is attached to. The area card passes an area, no entity. */
export interface CardFeatureContext {
  entity_id?: string;
  area_id?: string;
}

/** An entry of `window.customCardFeatures`, the features editor. */
interface CardFeatureEntry {
  type: string;
  name: string;
  isSupported?: (hass: HomeAssistant, context: CardFeatureContext) => boolean;
  configurable?: boolean;
}

declare global {
  interface Window {
    customCards?: PickerEntry[];
    customCardFeatures?: CardFeatureEntry[];
    customBadges?: PickerEntry[];
  }
}

interface ElementDefinition<Tag extends string> {
  tag: Tag;
  element: CustomElementConstructor;
  name: string;
}

interface PickerDefinition<Tag extends string> extends ElementDefinition<Tag> {
  description?: string;
  preview?: boolean;
  documentationURL?: string;
  getEntitySuggestion?: GetEntitySuggestion;
}

export interface CardDefinition extends PickerDefinition<CardTag> {
  kind: "card";
}

export interface CardFeatureDefinition extends ElementDefinition<CardFeatureTag> {
  kind: "feature";
  isSupported?: (hass: HomeAssistant, context: CardFeatureContext) => boolean;
  configurable?: boolean;
}

export interface BadgeDefinition extends PickerDefinition<BadgeTag> {
  kind: "badge";
}

export type SpookElementDefinition =
  CardDefinition | CardFeatureDefinition | BadgeDefinition;

export const defineCard = (
  definition: Omit<CardDefinition, "kind">,
): CardDefinition => ({ ...definition, kind: "card" });

export const defineCardFeature = (
  definition: Omit<CardFeatureDefinition, "kind">,
): CardFeatureDefinition => ({ ...definition, kind: "feature" });

export const defineBadge = (
  definition: Omit<BadgeDefinition, "kind">,
): BadgeDefinition => ({ ...definition, kind: "badge" });

/** The entity a card feature sits on, if it sits on one. */
export const contextEntity = (
  hass: HomeAssistant,
  context: CardFeatureContext,
): HassEntity | undefined =>
  context.entity_id ? hass.states[context.entity_id] : undefined;

const pickerEntry = ({
  tag,
  name,
  description,
  preview,
  documentationURL,
  getEntitySuggestion,
}: CardDefinition | BadgeDefinition): PickerEntry => ({
  type: tag,
  name,
  description,
  preview,
  documentationURL,
  getEntitySuggestion,
});

const addOnce = <Entry extends { type: string }>(
  list: Entry[],
  entry: Entry,
): void => {
  if (!list.some((existing) => existing.type === entry.type)) {
    list.push(entry);
  }
};

/**
 * Defines the element and lists it where the frontend looks.
 *
 * Safe to run twice. The bundle can end up on a page twice, like from an
 * extra module and from a dashboard resource for Cast, and defining a tag
 * that is already defined throws.
 */
export const register = (definition: SpookElementDefinition): void => {
  if (!customElements.get(definition.tag)) {
    customElements.define(definition.tag, definition.element);
  }

  switch (definition.kind) {
    case "card":
      addOnce((window.customCards ??= []), pickerEntry(definition));
      break;

    case "badge":
      addOnce((window.customBadges ??= []), pickerEntry(definition));
      break;

    case "feature":
      addOnce((window.customCardFeatures ??= []), {
        type: definition.tag,
        name: definition.name,
        isSupported: definition.isSupported,
        configurable: definition.configurable,
      });
      break;
  }
};

/**
 * Registers every element found by `import.meta.glob`, keyed by file.
 *
 * One element that fails to register does not take the others down with it.
 */
export const registerAll = (
  elements: Record<string, SpookElementDefinition>,
): void => {
  for (const [file, definition] of Object.entries(elements)) {
    try {
      register(definition);
    } catch (error) {
      console.error(`Spook could not register ${file}`, error);
    }
  }
};
