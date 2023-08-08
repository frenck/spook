---
subject: Reference
title: Glossary
subtitle: What does this even mean?
thumbnail: images/social.png
description: Glossary of terms used by Spook & Home Assistant, just to add a little context to this all.
date: 2023-06-30T20:36:04+02:00
---

% TODO:
% automation trigger
% condition
% jinja2
% list of strings
% state
% mapping
% datetime string?

:::{glossary}
Action
: An action in {term}`Home Assistant` is a single task that is performed when an {term}`automation <automation>` or {term}`script <script>` is executed. For example, an action can be to turn on a light, or to send a notification to your phone. There are many different types of actions, most notably the action to {term}`call a service <service call>`; they can be combined to create powerful automations and scripts.
: A sequental list of actions, is also known as a {term}`script sequence <sequence>`.
: [Learn more about all available actions in the official Home Assistant documentation](https://www.home-assistant.io/docs/scripts)
:::

:::{glossary}
Area
: An area in {term}`Home Assistant` is a logical grouping of {term}`devices <device>` and {term}`entities <entity>` that are meant to match areas (or rooms) the physical world: your home. Areas are used to group devices and entities together in, for example, the living room. Areas give a better overview of your home and can be used to target {term}`service calls <service call>` to a specific area, like turning off all the lights in the living room.
:::

:::{glossary}
Automation
: An automation in {term}`Home Assistant` is a set of triggers and {term}`actions <action>` that are automatically performed when a trigger fires. For example, an automation can be created to automatically turn on the lights when a motion sensor detects motion. Automations are the heart of Home Assistant, it is what makes Home Assistant an home automation platform. It is the glue that binds all the other {term}`integrations <integration>` together, it is what makes your home smart and comfortable. Automations can be shared in the community in the form of a {term}`blueprint`.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/getting-started/concepts-terminology/#automations)
:::

:::{glossary}
Blueprint
: A blueprint in {term}`Home Assistant` is a reusable {term}`automation <automation>` or {term}`script <script>`, shared and created by the community, that can be imported into your Home Assistant instance. They are a great way to learn how to automate your home and an inspiration for new automation ideas, or just an easy way to get started. Blueprints are a great method to share your automation creations with others, so that others can apply them to their own homes.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/docs/blueprint/)
:::

:::{glossary}
Boolean
: A boolean is a data type that can only have two values: `true` or `false`.
: You mostly come across this term in {term}`Home Assistant` when you are working with {term}`YAML`. In YAML, boolean values can also be written as `yes` or `no`, however, it is recommended to stick with just `true` or `false`.
: Because `yes` and `no` are boolean values in YAML, they might cause confusion when you meant to use a {term}`string value <string>`. For example, `yes` is a boolean value, but `"yes"` is a string value.
:::

:::{glossary}
Dashboard
: A dashboard in {term}`Home Assistant` is a user interface that is used to display information and control {term}`entities <entity>` in your home. Dashboards are used to create a user interface that is used to control your home, for example, to turn on the lights, or to see the current temperature. Dashboards are fully customizable and can be created in many different ways. There is a vibrant community that shares their dashboards, so you can get inspiration and ideas for your own dashboard.
: You might come across the term "Lovelace", which the codename originally used for dashboards.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/getting-started/concepts-terminology/#dashboards)
:::

:::{glossary}
Developer tools
: The developer tools in {term}`Home Assistant` are a set of tools that can be used to inspect, debug and play with your Home Assistant instance. It may sound very technical, but don't let that scare you. The developer tools can be used to, for example, inspect the state of {term}`entities <entity>`, experiment with {term}`calling services <service call>`, or test and debug your {term}`templates <template>`.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/docs/tools/dev-tools/)
:::

:::{glossary}
Device
: A device in {term}`Home Assistant` represents a physical device in your home, but a device can also represents a web service, like one that provides weather information. Devices are a logical grouping for {term}`entities <entity>`. For example, device that can mesure temperature, humidity and pressure, will have three entities: a temperature sensor, a humidity sensor and a pressure sensor. All three entities belong to the same device.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/getting-started/concepts-terminology/#devices--entities)
:::

:::{glossary}
Ectoplasm
: [Ectoplasm](<wiki:Ectoplasm_(paranormal)>) is a term used in spiritualism to denote a substance or spiritual energy "exteriorized" by physical mediums. Or the more popculture version: the green goo that ghosts leave behind, like in <wiki:Ghostbuster>.
: Spook uses ectoplasm to add new scary advanced behavior to the functionality of {term}`Home Assistant`. Internally in the [source code of Spook](https://github.com/frenck/spook), an ectoplasm is a module it can apply onto a Home Assistant {term}`integration <integration>`.
:::

:::{glossary}
Entity
: An entity in {term}`Home Assistant` represents a single data point or single function, in most cases, of a device. Entities are used to monitor physical properties or to control function of {term}`devices <device>`. Entities are the basic building blocks of Home Assistant.
: Entities have a state, providing information about the current condition of the entity (like on or off, open or closed, temperature, etc.).
: There are different types of entities. For example, a light entity is used to control a light, a switch entity is used to control a switch, and a sensor entity is used to display a sensor value.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/getting-started/concepts-terminology/#devices--entities)
:::

:::{glossary}
Entity ID
: An entity ID in {term}`Home Assistant` is an user definable identifier for an {term}`entity`. It is used to reference the actual entity in for example, {term}`automations <automation>`, {term}`scripts <script>`, and dashboards. The entity ID is automatically generated by Home Assistant when an entity is created the first time.
:::

:::{glossary}
Float
: A float is a datatype and is a more technical term for a number which can have a decimal point. For example, `2.5` is a float, but `2` is a valid float value as well.
: You mostly come across this term in {term}`Home Assistant` when you are working with {term}`YAML`. Floats (unlike {term}`strings <string>`) are not surrounded by quotes in YAML, and just written as is. For example, `2.5` is an float in YAML (thus handled as a numeric value), but `"2.5"` is a string in YAML (thus handled as text).
: Floats are often confused with {term}`integers <integer>`. They look very much alike, the difference is that floats can have a decimal point, while integers cannot. This also means that all integers are floats, but not all floats are integers.
:::

:::{glossary}
Helper
: A helper in {term}`Home Assistant` is an {term}`integration` that provides an user input (for example an input number, input boolean, input select, etc.), or consumes an existing {term}`entity` (or entities) as a data source to perform calculate with and return the result of that calculation as a new entity.
:::

:::{glossary}
Home Assistant
: Home Assistant is an amazing free and open-source home {term}`automation <automation>` platform.
Track and control all {term}`devices <device>` at home and automate control.
: Spook is a {term}`custom integration <integration>` for Home Assistant.
: [Visit the Home Assistant website](https://www.home-assistant.io/)
:::

:::{glossary}
Home Assistant Cloud
: The Home Assistant Cloud allows to effortlessly use your Home Assistant with various cloud services like Amazon Alexa and Google Assistant, but also provides remote access to your Home Assistant instance without having to deal with dynamic DNS, SSL certificates and opening ports on your router.  
: <br>The Home Assistant Cloud service is provided by [Nabu Casa](https://www.nabucasa.com). The earnings from the services provided are used to fund Home Assistant development and related projects in the open home community. Please consider subscribing to the Home Assistant Cloud service to support the development of Home Assistant. 🙏
: [Learn more on the Nabu Casa website](https://www.nabucasa.com/)
:::

:::{glossary}
HACS
: Home Assistant Community Store. A third-party {term}`integrations <integration>` store for {term}`Home Assistant`. It provides custom integrations for Home Assistant that are not available in a standard Home Assistant installation. These integrations are not supported by the Home Assistant project.
: As the Spook integration does unsupported things, it is only available through HACS.
: [Learn more on the HACS website](https://hacs.xyz)
:::

:::{glossary}
Integer
: An integer is a datatype and is a more technical term for a number without a decimal point. For example, `2` is an integer, but `2.5` is not.
: You mostly come across this term in {term}`Home Assistant` when you are working with {term}`YAML`. Integers (unlike {term}`strings <string>`) are not surrounded by quotes in YAML, and just written as is. For example, `2` is an integer in YAML (thus handled as a number), but `"2"` is a string in YAML (thus handled as text).
:::

:::{glossary}
Integration
: A integration in {term}`Home Assistant` is a component that allows you to integrate
a {term}`device <device>` or {term}`service <service>` with your Home Assistant installation. Home Assistant comes with well of a thousand integrations out of the box, but you can also install your own custom integrations.
: Custom integrations, however, are not supported by the Home Assistant project. They are not reviewed or tested by the Home Assistant development team, and thus may negatively impact the stability of your Home Assistant instance.
: Spook 👻 is a custom integration for Home Assistant that is available via {term}`HACS`.
:::

:::{glossary}
List
: A list is a datatype and is a more technical term for a collection of items. For example, a list of {term}`integers <integer>`: `[1, 2, 3]`.
: You mostly come across this term in {term}`Home Assistant` when you are working with {term}`YAML`. Synonyms for lists are arrays and sequenses. Although, a {term}`seqence <sequence>` in Home Assistant mostly refers to a list of {term}`actions <action>`.
: Lists can be written in YAML in two ways. One is the square bracket syntax, like `["one", "two", "three"]`. The other methods is the hyphen syntax, like `- "one"` (which is the same as `["one"]`). Having each item (prefix with a hyphen) on a new line. The latter is generally recommended, it is more expressive, but improves readability. For example:
`yaml
    example:
      - "one"
      - "two"
      - "three"
    `
:::

:::{glossary}
My Home Assistant
: My Home Assistant is a web service by the {term}`Home Assistant` project that allows the documentation and websites to link you to specific pages in your own Home Assistant instance. Learn more about it in the [My Home Assistant FAQ](https://my.home-assistant.io/faq/).
:::

:::{glossary}
Repairs
: The repairs dashboard in {term}`Home Assistant` is a place where detected issues with your Home Assistant instance are listed. It is recommended to check this dashboard regularly to ensure your Home Assistant instance is running smoothly. The provided issues are often accompanied with integrations or a link to the documentation to help you resolve the issue.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/integrations/repairs)
:::

:::{glossary}
Scene
: A scene in {term}`Home Assistant` is a collection of {term}`entities <entity>` and their states. Scenes are used to set a predefined state for a group of entities. For example, a scene can be used to set the lights in your living room to a specific color and brightness, or to set the volume of your media player to a specific level and all restored to that stored state when the scene is activated.
: Scenes are probably (one of) the most underused features of Home Assistant, but are actually really useful and can help a lot to reduce the complexity of your {term}`automations <automation>`.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/getting-started/concepts-terminology/#scenes)
:::

:::{glossary}
Script
: A script in {term}`Home Assistant` is a sequence of actions that are executed when the script started or called via start using a {term}`service call <service call>`. Scripts are similar to {term}`automations <automation>`, but are not automatically executed when a trigger fires. Scripts are a great way to group a sequence of actions together that can be executed on demand and reused in multiple automations.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/getting-started/concepts-terminology/#scripts)
:::

:::{glossary}
Service
: A service in {term}`Home Assistant` is a method that can be {term}`called <service call>` to perform an action. Services are, for example, used to control {term}`devices <device>` and {term}`entities <entity>`. For example, the `light.turn_on` service is used to turn on a light, and the `media_player.play_media` service is used to play a media file on a media player entity.
: Services are not limited to controlling devices and entities. They can also be used to perform other actions, like sending a notification, to start a script, or to query an service for information providing a response with data back.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/docs/scripts/service-calls/)
:::

:::{glossary}
Service call
: A service call is the action to execute a {term}`service <service>`. Service calls can be made from, for example, as an action in {term}`automation <automation>` or as part of a {term}`script <script>` sequence.
: Service calls are targeted towards specific {term}`devices <device>`, {term}`entities <entity>`, or {term}`areas <area>`. For example, the calling the `light.turn_off` service to turn of all the lights in the living room area.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/docs/scripts/service-calls/)
:::

:::{glossary}
Service name
: A service name is the name of a {term}`service <service>` that can be {term}`called <service call>` to perform an {term}`action <action>`. For example, the `light.turn_on` service is used to turn on a light, and the `media_player.play_media` service is used to play a media file on a media player entity.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/docs/scripts/service-calls/)
:::

:::{glossary}
Service response
: A service response is the response that is returned by a {term}`service <service>` when it is {term}`called <service call>`. The response can contain data that is returned by the service. There are three types of services, one that will return no response (the most common), ones that have an optional response, and ones that always have response.
This is important to know, as for the ones without response you are not allowed to set the `response_variable` option, while for the optional that is allowed, and for the ones that always have a response it is required.
:::

:::{glossary}
Service targets
: Service targets are the {term}`devices <device>`, {term}`entities <entity>`, or {term}`areas <area>` that are targeted by a {term}`service call <service call>`. The `target` service call parameters is used for that. For example, the calling the `light.turn_off` with the living room are as a target to turn of all the lights in the living room area. {term}`Home Assistant` will figure out which entities it needs to turn off based on the area that is targeted.
: Not all services work with targets.
:::

:::{glossary}
Sequence
: A sequence in {term}`Home Assistant` is a list of {term}`actions <action>` that are executed in order. Sequences are used in {term}`automations <automation>` and {term}`scripts <script>` to perform multiple actions in a specific order.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/docs/scripts)
:::

:::{glossary}
String
: A string is a datatype, which consists of a sequence of characters. Essentially, a string is a more technical term for: text.
: You mostly come across this term in {term}`Home Assistant` when you are working with {term}`YAML`. In YAML, the best practice for using string (text) is by always surrounding them using quotes. For example, `"Hello World"`. This is not required, but it is a good practice to follow as it avoid you running into issues with some special cases in YAML (for example, the text `off` without using quotes, will not be considered a string, but a {term}`boolean value <boolean>`).
:::

:::{glossary}
Spook's influence
: A term to indicate/describe the Spook's part in a particular feature of {term}`Home Assistant`. In some cases, Spook adds complete new, previously non-existing features; in other cases it might modify, extend, or improve existing features. Spook documents the influence he has, so you can easily see what features are available because of him.
:::

:::{glossary}
Template
: Templating is an advanced features of {term}`Home Assistant` that allows you to dynamically generate values using the [Jinja2](https://palletsprojects.com/p/jinja) template engine. The syntax used for templating comes very close to the concept of programming languages, and allows you to perform complex operations on data.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/docs/configuration/templating/)
:::

:::{glossary}
YAML
: The complex definition would be: <wiki:YAML> is a human-readable data-serialization language. But a more simplified explaination would be: It is a structure in which we can write configuration files, that are readble for both humans and machines.
: It is the format {term}`Home Assistant` uses to store its configuration and data. Opinions are divided on whether YAML is a good or bad format, or hard or easy to use. The fact remains, is that Home Assistant uses it a lot, and it definitly worth while learning it. YAML itself really isn't that complex, but it does have some quirks that you need to be aware of. The most complex part of using YAML with Home Assistant, is not YAML itself, but all the things you can do with it in Home Assistant.
: Don't let is scare you. You'll get the hang of it quickly.
: [Read a tutorial on YAML](https://spacelift.io/blog/yaml)
:::
