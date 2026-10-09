---
subject: Features
title: Assistants
subtitle: Ghost hunting, now with a sidekick. 🤖
date: 2026-10-09T12:00:00+02:00
---

Spook hands its knowledge to AI assistants. An assistant can ask Spook which ghosts are floating around your home, what they mean, where something is used, and whether a draft automation names things that don't exist. It can also ignore a ghost or fix one for you, if you let it.

These tools are only offered on Home Assistant's own administrator API, available from Home Assistant 2026.11. They are never handed to Assist, so nobody can clean up your repairs by talking to the kitchen speaker. Every tool checks the person asking is an administrator, and the ones that change something refuse when there is no user at all.

## Using them

There are two ways to get an assistant talking to Spook:

- **In Home Assistant**: open the settings of a conversation agent (like OpenAI, Anthropic or Ollama) and select the **Home Assistant** API under the options for controlling Home Assistant.
- **From outside Home Assistant**: point an MCP client (like Claude Desktop or Claude Code) at Home Assistant's [MCP server](https://www.home-assistant.io/integrations/mcp_server/) and select the **Home Assistant** API there.

Then just ask. "How is my house doing?", "Where is `light.kitchen` used?", or "Check this automation before I save it."

## The tools

```{list-table}
:header-rows: 1
* - Tool
  - What it does
* - `spook__overview`
  - A short summary: open and ignored ghosts per kind, and the oldest ones.
* - `spook__list_ghosts`
  - Lists Spook's open repair issues, optionally by kind, ignored ones on request.
* - `spook__explain_ghost`
  - Explains one issue: its full description, its fix options, and what Spook worked out (like a likely rename).
* - `spook__find_usages`
  - Finds where an entity, action, label, area or floor is used: automations, scripts, scenes, dashboards, helpers and template helpers.
* - `spook__check_references`
  - Checks a draft automation, script, scene or dashboard card for references to things that don't exist, before it is saved.
* - `spook__list_features`
  - Lists the triggers, conditions and actions Spook adds, so an assistant can use them when writing automations.
* - `spook__ignore_ghost`
  - Ignores an issue, like selecting ignore in the repairs dashboard.
* - `spook__unignore_ghost`
  - Stops ignoring an issue.
* - `spook__fix_ghost`
  - Runs one of the fix options of an issue, like removing an empty area. This can delete things, so a good assistant asks first.
```

A fix that needs more than a choice from a menu is left for you to finish in the {term}`repairs dashboard <repairs>`.

## An agent skill, too

Agents that manage Home Assistant from the outside, through Home Assistant's MCP server or a community MCP server like HA-MCP, can also learn Spook from its agent skill. It describes every action, trigger, condition and repair Spook has, so an agent does not have to read the documentation first. In Claude Code:

```{code-block} text
/plugin marketplace add frenck/spook
/plugin install spook@spook
```

The skill works with any Home Assistant version Spook supports; the tools above need 2026.11.
