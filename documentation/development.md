---
subject: About the project
title: Development & Contributing
short_title: Development
subtitle: Be the change. Contribute. Be Spook 👻.
thumbnail: images/social.png
description: Spook is an open-source project, and contributions are welcome! Here is how you can contribute to Spook.
date: 2023-08-09T21:29:00+02:00
---

There are many ways you can contribute to the development of Spook.

## Reporting issues and submitting feature requests

Please report the bug on the [Spook issue tracker on GitHub](https://github.com/frenck/spook/issues). You can also submit a pull request with a fix. That would be even more awesome! 🤩

If you have a feature request, please share your idea on the [Spook discussion forum on GitHub](https://github.com/frenck/spook/discussions), or build it yourself and submit a feature request! 🤩

## Translating Spook

Spook is available in multiple languages; however, our beloved Spook is actually not that good in speaking multiple languages. So, he needs your help translating Spook into your language!

Translating Spook is relatively easy and doesn't require any coding skills. Just translate the sentences [straight from your browser!](https://hosted.weblate.org/engage/spook/)!

Missing translations in a language will automatically fall back to the English version. If you see English text, it means it is not translated yet.

[![Translation status](https://hosted.weblate.org/widgets/spook/-/integration/287x66-black.png)](https://hosted.weblate.org/engage/spook/)

🌎 [Start helping to translate Spook into your language!](https://hosted.weblate.org/engage/spook/)

Spook supports all languages that Home Assistant supports. If you are missing your language, add it, or please [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

The current status of all translations:

[![Translation status](https://hosted.weblate.org/widgets/spook/-/integration/multi-auto.svg)](https://hosted.weblate.org/engage/spook/)

## Improving the documentation

Spook is already scary enough for many, so the documentation should be as good as possible.

The documentation is written in [MyST](https://mystmd.org/guide), which is just [Markdown](https://www.markdownguide.org/) but with some added functionality.

The source code of the documentation can be found in the `documentation` folder of our GitHub Repository:

<https://github.com/frenck/spook/tree/main/documentation>

To run the documentation locally, you'll need to clone the Spook repository locally, and from the `documentation` folder, run:

```bash
npx --package mystmd myst start
```

This will start a local webserver on `http://localhost:3000` and will automatically update when you make changes to the documentation.

## Developing Spook

There isn't much fundamental structure for developing Spook. Hopefully, this can be improved in the future.

You can find the source code of Spook on GitHub: <https://github.com/frenck/spook>

Here are some hints to get you going at least:

- As Spook is a custom integration, it can be developed in a regular Home Assistant development environment, as described [here](https://developers.home-assistant.io/docs/development_environment). Just place the `spook` folder from the `custom_components` folder in the `custom_components` folder of your development environment config folder.
- If you develop Home Assistant in a virtual environment, you could clone Spook's repository in any folder and next symlink the `spook` folder from the `custom_components` folder in the `custom_components` folder of your development environment config folder.

Any help improving the development situation for Spook is welcome! For example, a nice and easy-to-use devcontainer would be amazing, or a good structure for unit tests.

### Opening a pull request

If you want to open a pull request, go ahead! 🤩

Please be sure to test your changes before you open the PR to ensure the changes work as expected. Motivate/describe the change you provide in the PR so we don't have to figure that out from code change.

Also, please make sure to update the documentation if needed. I know this isn't the most fun part, but it is important for users to understand how to use the awesome changes you've made.
