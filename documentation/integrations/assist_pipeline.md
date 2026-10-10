---
subject: Enhanced integrations
title: Assist pipeline
subtitle: Nobody home at the other end of the line.
description: Spook enhances Assist by reporting voice assistant pipelines that use a conversation agent or a speech, voice, or wake word engine that no longer exists.
date: 2026-09-30T16:00:00+02:00
---

```{image} https://brands.home-assistant.io/assist_pipeline/logo.png
:alt: The Home Assistant Assist pipeline logo
:width: 250px
:align: center
```

<br><br>

An Assist pipeline is a voice assistant in {term}`Home Assistant`: which conversation agent answers, which engine turns speech into text, which one speaks the reply, and which wake word it listens for. You set them up under Settings > Voice assistants.

Each of those is picked once, and nothing keeps the pipeline in step afterwards. Remove the integration behind one, and the pipeline keeps asking for it.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook does not provide action enhancements for this integration.

## Repairs

While Spook is floating around in your Home Assistant instance, it will raise repairs issues if it has found something that is not right.

### Unknown engines

Spook checks the conversation agent, speech-to-text, text-to-speech, and wake word engine of every pipeline, and raises a repair issue when one of them is an entity that does not exist anymore. Nothing else says so: the next voice command simply fails with an error about a missing provider or agent.

Only engines that are entities are checked. The same settings can also hold older provider names, like `cloud`, and there is no reliable way to tell whether one of those is still around, so Spook leaves them alone rather than guess.

This issue is not fixable from the issue itself, on purpose. Clearing the speech or voice engine would quietly change what the assistant does, and the conversation agent cannot be left empty at all. Which engine should take over is your call, so the issue sends you to the settings of that assistant instead. Spook will automatically remove the repair issue once it is fixed.

## Use cases

Some use cases for the enhancements Spook provides for this integration:

- Trying out a cloud AI as your conversation agent, then removing it again. The pipeline you made for it keeps pointing at an agent that is not there anymore.
- Moving from one speech engine to another, like a local Whisper and Piper setup to a different one, and forgetting the pipeline still names the old engines.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Feature requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
