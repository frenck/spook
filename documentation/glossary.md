---
subject: Reference
title: Glossary
subtitle: What does this even mean?
thumbnail: images/social.png
description: Glossary of terms used by Spook & Home Assistant, just to add a little context to this all.
date: 2024-01-09T17:14:53+01:00
---

% TODO:
% automation trigger
% condition
% jinja2
% state
% mapping
% datetime string?
% binary sensor
% switch
% returns
% return type
% None
% zone

:::{glossary}
Action
: A action in {term}`Home Assistant` is a method that can be {term}`performed <performing actions>`. Actions are, for example, used to control {term}`devices <device>` and {term}`entities <entity>`. For example, the `light.turn_on` action is used to turn on a light and the `media_player.play_media` action plays a media file on a media player entity.
: Actions are not limited to controlling devices and entities. They can also be used to perform other things, like sending a notification, to start a script, or to query a service for information responding with data back.
: A sequential list of actions is also known as a {term}`script sequence <sequence>`.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/docs/scripts/service-calls/)
:::

:::{glossary}
Action name
: A action name is the name of a {term}`action <action>` that can be {term}`performed <performing actions>` to do an {term}`action <action>`. For example, the `light.turn_on` action is used to turn on a light and the `media_player.play_media` action plays a media file on a media player entity.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/docs/scripts/service-calls/)
:::

:::{glossary}
Action response
: An action response is a response that is returned by an {term}`action <action>` when it is {term}`performed <performing actions>`. The response can contain data that is returned by the action. There are three types of actions: one that will return no response (the most common), one that has an optional response, and one that always has a response.
This is important to know, as for the ones without response, you are not allowed to set the `response_variable` option, while for the optional, that is allowed, and for the ones that always have a response, it is required.
:::

:::{glossary}
Action targets
: Action targets are the {term}`devices <device>`, {term}`entities <entity>`, or {term}`areas <area>` that are targeted by a {term}`performing an action <performing actions>`. The `target` action parameter is used for that. For example, calling the `light.turn_off` with the living room as a target to turn off all the lights in the living room area. {term}`Home Assistant` will figure out which entities it needs to turn off based on the area that is targeted.
: Not all action work with targets.
:::

:::{glossary}
Area
: An area in {term}`Home Assistant` is a logical grouping of {term}`devices <device>` and {term}`entities <entity>` that are meant to match areas (or rooms) in the physical world: your home. Areas are used to group devices and entities together in, for example, the living room. Areas give a better overview of your home and can be used to target {term}`actions <action>` to a specific area, like turning off all the lights in the living room.
: [Learn more about areas in the official Home Assistant documentation](https://www.home-assistant.io/docs/organizing/areas/)
:::

:::{glossary}
Automation
: An automation in {term}`Home Assistant` is a set of triggers and {term}`actions <action>` that are automatically performed when a trigger fires. For example, an automation can be created to automatically turn on the lights when a motion sensor detects motion. Automations are the heart of Home Assistant; it is what makes Home Assistant a home automation platform. It is the glue that binds all the other {term}`integrations <integration>` together, it is what makes your home smart and comfortable. Automations can be shared in the community in the form of a {term}`blueprint`.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/getting-started/concepts-terminology/#automations)
:::

:::{glossary}
Blueprint
: A blueprint in {term}`Home Assistant` is a reusable {term}`automation <automation>` or {term}`script <script>`, shared and created by the community, that can be imported into your Home Assistant instance. They are a great way to learn how to automate your home and an inspiration for new automation ideas, or just an easy way to get started. Blueprints are a great method to share your automation creations with others so that others can apply them to their own homes.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/docs/blueprint/)
:::

:::{glossary}
Boolean
: A boolean is a data type that can only have two values: `true` or `false`.
: You mostly come across this term in {term}`Home Assistant` when working with {term}`YAML`. In YAML, boolean values can also be written as `yes` or `no`; however, it is recommended to stick with just `true` or `false`.
: Because `yes` and `no` are boolean values in YAML, they might cause confusion when you meant to use a {term}`string value <string>`. For example, `yes` is a boolean value, but `"yes"` is a string value.
:::

:::{glossary}
Config entry
: A config entry in {term}`Home Assistant` is a configuration for an {term}`integration <integration>`. It is a technical term from the developer sources leaking into the user space, which may sometimes sound confusing. In short, it is the configuration you see on the integrations page. Most integrations can be set up multiple times (like adding two Hue bridges or multiple ESPHome devices). Each such "integration instance" is a config entry.
: This is sometimes referred to as "integration instance" or "integration entry".
:::

:::{glossary}
Dashboard
: A dashboard in {term}`Home Assistant` is a user interface that displays information and control {term}`entities <entity>` in your home. Dashboards are used to create a user interface to control your home, such as turning on the lights or seeing the current temperature. Dashboards are fully customizable and can be created in many different ways. There is a vibrant community that shares their dashboards so that you can get inspiration and ideas for your own dashboard.
: You might come across the term "Lovelace", which is the codename originally used for dashboards.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/getting-started/concepts-terminology/#dashboards)
:::

:::{glossary}
Developer tools
: The developer tools in {term}`Home Assistant` are a set of tools that can be used to inspect, debug and play with your Home Assistant instance. It may sound very technical, but don't let that scare you. The developer tools can be used to, for example, inspect the state of {term}`entities <entity>`, experiment with {term}`performing action <performing actions>`, or test and debug your {term}`templates <template>`.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/docs/tools/dev-tools/)
:::

:::{glossary}
Device
: A device in {term}`Home Assistant` represents a physical device in your home, but a device can also represent a web service, like one that provides weather information. Devices are a logical grouping for {term}`entities <entity>`. For example, a device that can measure temperature, humidity, and pressure will have three entities: a temperature sensor, a humidity sensor, and a pressure sensor. All three entities belong to the same device.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/getting-started/concepts-terminology/#devices--entities)
:::

:::{glossary}
Ectoplasm
: [Ectoplasm](<wiki:Ectoplasm_(paranormal)>) is a term used in spiritualism to denote a substance or spiritual energy "exteriorized" by physical mediums. Or the more pop-culture version: the green goo that ghosts leave behind, like in <wiki:Ghostbuster>.
: Spook uses ectoplasm to add new scary advanced behavior to the functionality of {term}`Home Assistant`. Internally in the [source code of Spook](https://github.com/frenck/spook), an ectoplasm is a module it can apply to a Home Assistant {term}`integration <integration>`.
:::

:::{glossary}
Entity
: An entity in {term}`Home Assistant` represents a single data point or single function, in most cases, of a device. Entities are used to monitor physical properties or to control the functions of {term}`devices <device>`. Entities are the basic building blocks of Home Assistant.
: Entities have a state, providing information about the current condition of the entity (like on or off, open or closed, temperature, etc.).
: There are different types of entities. For example, a light entity is used to control a light, a switch entity is used to control a switch, and a sensor entity is used to display a sensor value.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/getting-started/concepts-terminology/#devices--entities)
:::

:::{glossary}
Entity ID
: An entity ID in {term}`Home Assistant` is a user-definable identifier for an {term}`entity`. It is used to reference the actual entity in, for example, {term}`automations <automation>`, {term}`scripts <script>`, and dashboards. The entity ID is automatically generated by Home Assistant when an entity is created for the first time.
:::

:::{glossary}
Float
: A float is a datatype and is a more technical term for a number that can have a decimal point. For example, `2.5` is a float, but `2` is a valid float value as well.
: You mostly come across this term in {term}`Home Assistant` when working with {term}`YAML`. Floats (unlike {term}`strings <string>`) are not surrounded by quotes in YAML and are just written as is. For example, `2.5` is a float in YAML (thus handled as a numeric value), but `"2.5"` is a string in YAML (thus handled as text).
: Floats are often confused with {term}`integers <integer>`. They look very much alike; the difference is that floats can have a decimal point, while integers cannot. This also means that all integers are floats, but not all floats are integers.
:::

:::{glossary}
Floor
: A floor in {term}`Home Assistant` is a logical grouping of {term}`areas <area>` that are meant to match floors (or levels) in the physical world: your home. Floors are used to group areas together that are on the same floor in your home. Floors give a better overview of your home and can be used to target {term}`actions <performing actions>` to a specific floor, like turning off all the lights on the first floor.
: [Learn more about floors in the official Home Assistant documentation](https://www.home-assistant.io/docs/organizing/floors/)
:::

:::{glossary}
Helper
: A helper in {term}`Home Assistant` is an {term}`integration` that provides a user input (for example, an input number, input boolean, input select, etc.) or consumes an existing {term}`entity` (or entities) as a data source to perform calculations with and return the result of that calculation as a new entity.
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
: The Home Assistant Cloud allows you to effortlessly use your Home Assistant with various cloud services like Amazon Alexa and Google Assistant but also provides remote access to your Home Assistant instance without having to deal with dynamic DNS, SSL certificates, and opening ports on your router.  
: <br>The Home Assistant Cloud service is provided by [Nabu Casa](https://www.nabucasa.com). The earnings from the services provided are used to fund Home Assistant development and related projects in the open home community. Please consider subscribing to the Home Assistant Cloud service to support the development of Home Assistant. 🙏
: [Learn more on the Nabu Casa website](https://www.nabucasa.com/)
:::

:::{glossary}
HACS
: Home Assistant Community Store. A third-party {term}`integrations <integration>` store for {term}`Home Assistant`. It provides custom integrations for Home Assistant that are not available in a standard Home Assistant installation. The Home Assistant project does not support these integrations.
: As the Spook integration does unsupported things, it is only available through HACS.
: [Learn more on the HACS website](https://hacs.xyz)
:::

:::{glossary}
Integer
: An integer is a datatype and is a more technical term for a number without a decimal point. For example, `2` is an integer, but `2.5` is not.
: You mostly come across this term in {term}`Home Assistant` when working with {term}`YAML`. Integers (unlike {term}`strings <string>`) are not surrounded by quotes in YAML and are just written as is. For example, `2` is an integer in YAML (thus handled as a number), but `"2"` is a string in YAML (thus handled as text).
:::

:::{glossary}
Integration
: An integration in {term}`Home Assistant` is a component that allows you to integrate
a {term}`device <device>` or {term}`action <action>` with your Home Assistant installation. Home Assistant comes with well over a thousand integrations out of the box, but you can also install your own custom integrations.
: Custom integrations, however, are not supported by the Home Assistant project. They are not reviewed or tested by the Home Assistant development team and thus may negatively impact the stability of your Home Assistant instance.
: Spook 👻 is a custom integration for Home Assistant that is available via {term}`HACS`.
:::

:::{glossary}
Label
: A label in {term}`Home Assistant` can be freely created / be made up by you and used to create your own organizational structure by tagging {term}`devices <device>`, {term}`entities <entity>`, or {term}`areas <area>` with one or more labels. Labels can be used to filter items shows in tables in the user interface, or to target {term}`actions <performing actions>` in for example {term}`automations <automation>`, or {term}`scripts <script>`.
: [Learn more about labels in the official Home Assistant documentation](https://www.home-assistant.io/docs/organizing/labels/)
:::

:::{glossary}
List
: A list is a datatype and is a more technical term for a collection of items. For example, a list of {term}`integers <integer>`: `[1, 2, 3]`.
: You mostly come across this term in {term}`Home Assistant` when working with {term}`YAML`. Synonyms for lists are arrays and sequences. Although, a {term}`sequence <sequence>` in Home Assistant mostly refers to a list of {term}`actions <action>`.
: Lists can be written in YAML in two ways. One is the square bracket syntax, like `["one", "two", "three"]`. The other method is the hyphen syntax, like `- "one"` (which is the same as `["one"]`). Having each item (prefix with a hyphen) on a new line. The latter is generally recommended; it is more expressive but improves readability. For example:

    ```yaml
    brackets: ["one", "two", "three"]
    newlines:
      - "one"
      - "two"
      - "three"
    ```

:::

:::{glossary}
My Home Assistant
: My Home Assistant is a web service by the {term}`Home Assistant` project that allows documentation and websites to link you to specific pages in your own Home Assistant instance. Learn more about it in the [My Home Assistant FAQ](https://my.home-assistant.io/faq/).
:::

:::{glossary}
Performing actions
: {term}`Actions <action>` can be performed. Actions can be performed from, for example, as part of an {term}`automation <automation>` or a {term}`script <script>` sequence.
: Actions are targeted toward specific {term}`devices <device>`, {term}`entities <entity>`, or {term}`areas <area>`. For example, the calling the `light.turn_off` action to turn off all the lights in the living room area.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/docs/scripts/service-calls/)
:::

:::{glossary}
Repairs
: The repairs dashboard in {term}`Home Assistant` is a place where detected issues with your Home Assistant instance are listed. It is recommended to check this dashboard regularly to ensure your Home Assistant instance is running smoothly. The provided issues are often accompanied with integrations or a link to the documentation to help you resolve the issue.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/integrations/repairs)
:::

:::{glossary}
Scene
: A scene in {term}`Home Assistant` is a collection of {term}`entities <entity>` and their states. Scenes are used to set a predefined state for a group of entities. For example, a scene can be used to set the lights in your living room to a specific color and brightness or to set your media player's volume to a specific level and all restored to that stored state when the scene is activated.
: Scenes are probably (one of) the most underused features of Home Assistant, but they are actually really useful and can help a lot to reduce the complexity of your {term}`automations <automation>`.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/getting-started/concepts-terminology/#scenes)
:::

:::{glossary}
Script
: A script in {term}`Home Assistant` is a sequence of actions that are executed when the script is started or called via start by {term}`performing an action <performing actions>`. Scripts are similar to {term}`automations <automation>` but are not automatically executed when a trigger fires. Scripts are a great way to group a sequence of actions together that can be executed on demand and reused in multiple automations.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/getting-started/concepts-terminology/#scripts)
:::

:::{glossary}
Service
: A service in {term}`Home Assistant` was an ambigous term in Home Assistant. It has been fully replaced by the {term}`action`.
:::

:::{glossary}
Service call
: A service call in Home Assistant has been renamed ans is now called {term}`performing an action <performing actions>`.
:::

:::{glossary}
Sequence
: A sequence in {term}`Home Assistant` is a list of {term}`actions <action>` that are executed in order. Sequences are used in {term}`automations <automation>` and {term}`scripts <script>` to perform multiple actions in a specific order.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/docs/scripts)
:::

:::{glossary}
String
: A string is a datatype that consists of a sequence of characters. Essentially, a string is a more technical term for: text.
: You mostly come across this term in {term}`Home Assistant` when working with {term}`YAML`. In YAML, the best practice for using strings (text) is by always surrounding them using quotes. For example, `"Hello World"`. This is not required, but it is a good practice to follow as it prevents you from running into issues with some special cases in YAML (for example, the text `off` without using quotes will not be considered a string but a {term}`boolean value <boolean>`).
:::

:::{glossary}
Influence of Spook
: A term to indicate/describe the Spook's part in a particular feature of {term}`Home Assistant`. In some cases, Spook adds completely new, previously non-existing features; in other cases, it might modify, extend, or improve existing features. Spook documents his influence, so you can easily see what features are available because of him.
:::

:::{glossary}
Template
: Templating is an advanced feature of {term}`Home Assistant` that allows you to dynamically generate values using the [Jinja2](https://palletsprojects.com/p/jinja) template engine. The syntax used for templating comes very close to the concept of programming languages and will enable you to perform complex operations on data.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/docs/configuration/templating/)
:::

:::{glossary}
Template engine
: The template engine in {term}`Home Assistant` is a [Jinja2](https://palletsprojects.com/p/jinja) template engine, enrichted with an Home Assistant-specific extension. The engine is used to take a {term}`template <template>`, process it, and return the resulting value from it.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/docs/configuration/templating/)
:::

:::{glossary}
Template filter function
: Filters are a special type of {term}`template function <template function>` that can be used to modify the output of a {term}`template <template>`. For example, the `lower` filter can be used to convert a string to lowercase. For the syntax of filters, inspiration was probably taken from <wiki:UNIX>. The the idea is that you "pipe" a value, by adding a pipe character `|`, through some filters to do something with it. For example, `{{ "SPOOK" | lower }}` will output `spook`. You can also chain filters, for example, `{{ "SPOOK" | lower | capitalize }}` will output `Spook`.
: Most {term}`template functions <template function>` can be used used as a filter as well.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/docs/configuration/templating/)
: [Learn more in the Jinja2 documentation](https://jinja.palletsprojects.com/en/3.0.x/templates/#filters)
:::

:::{glossary}
Template function
: A template function is a function that can be used in a {term}`template <template>`. Template functions are used to perform operations on data. For example, the `now()` function returns the current date and time, and the `is_state()` function checks if an {term}`entity <entity>` is in a specific state.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/docs/configuration/templating/)
:::

:::{glossary}
Template function return type
: When a {term}`template function <template function>` is used/called, it returns {term}`a value <template function return value>`. The returned value can be of different types. For example, if it returns a numeric value, its return type might be a {term}`float <float>`. If it returns a true or false result, that would be a {term}`boolean value <boolean>`. There are many different types of values that can be returned.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/docs/configuration/templating/)
:::

:::{glossary}
Template function return value
: A template function return value is the value that is returned by a {term}`template function <template function>` when it was called/used. The return value can next be used in a next step, for example, to use as an in put for another template function. For example, the `now()` function returns the current date and time, and the `is_state()` function returns a {term}`boolean value <boolean>` indicating if an {term}`entity <entity>` is in a specific state.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/docs/configuration/templating/)
:::

:::{glossary}
Template test function
: Test functions are a special type of {term}`template function <template function>` that can be used to check if a condition is true or false. Inside a template they use the `is` operator. For example `3 is odd` will return `True` and `3 is even` will return `False`.
: [Learn more in the official Home Assistant documentation](https://www.home-assistant.io/docs/configuration/templating/)
: [Learn more in the Jinja2 documentation](https://jinja.palletsprojects.com/en/3.0.x/templates/#tests)
:::

:::{glossary}
YAML
: The complex definition would be: <wiki:YAML> is a human-readable data-serialization language. But a more simplified explanation would be: It is a structure in which we can write configuration files that are readable for both humans and machines.
: It is the format {term}`Home Assistant` uses to store its configuration and data. Opinions are divided on whether YAML is a good or bad format or hard or easy to use. The fact remains, is that Home Assistant uses it a lot, and it definitly worth while learning it. YAML itself really isn't that complex, but it does have some quirks that you need to be aware of. The most complex part of using YAML with Home Assistant is not YAML itself but all the things you can do with it in Home Assistant.
: Don't let it scare you. You'll get the hang of it quickly.
: [Read a tutorial on YAML](https://spacelift.io/blog/yaml)
:::
