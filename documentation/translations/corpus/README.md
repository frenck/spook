# How Spook's docs get translated

The docs are written in English, by people. Every other language is written by a machine, from the English and from the files in this directory.

So there are two rules:

1. **Nobody edits a translated page.** Not by hand, and not with an AI assistant. Everything under `documentation/translations/output/` is overwritten by the next run. A pull request that changes a file there is closed, however good the change is.
2. **A fix goes in here.** When a translation is wrong, the thing that made it wrong is in this directory: a missing glossary entry, a rule the style guide does not have, a sentence that needs pinning. Fix that, and the page is fixed, together with every other page that had the same problem.

## Something is wrong in a translation

[Open an issue](https://github.com/frenck/spook/issues/new/choose) and say which page, which sentence, and what it should say. You do not need to know how any of this works.

Want to fix it yourself? Then it is one of these:

| What is wrong                                                        | Where the fix goes                                            |
| -------------------------------------------------------------------- | ------------------------------------------------------------- |
| A button or menu has another name than Home Assistant shows          | `<language>/glossary.yml`, under `labels`, with the reason    |
| A word is used that Home Assistant users in your language do not use | `<language>/glossary.yml`, under `terms`                      |
| It reads stiff, formal, or like a translation                        | `<language>/style.md`, and a pair in `<language>/examples.md` |
| A sentence that repeats on many pages is worded differently          | `<language>/style.md`, under "Wording that repeats"           |
| The space before `:` or `?` is wrong, everywhere                     | `<language>/typography.yml`                                   |
| One sentence is wrong, and no rule covers it                         | `<language>/corrections.yml`                                  |
| A joke or hashtag has a better local version                         | `<language>/jokes.yml`                                        |
| Something was translated that is a name                              | `do-not-translate.yml`                                        |
| The English itself is unclear or wrong                               | The English page in `documentation/content/`                  |

If the label is wrong in Home Assistant or in Spook itself, the docs are right to copy it. Fix it where it comes from: Spook's own strings are translated on [Weblate](https://hosted.weblate.org/engage/spook/).

## What is in here

```text
translations/
  corpus/                      This directory. Written and reviewed by people.
    languages.yml              The languages, the models, the corpus version.
    do-not-translate.yml       Names that stay, and what is never written.
    style/_shared.md           The voice of the docs, for every language.
    prompt/translate.md        What the translating model is told.
    prompt/review.md           What the reviewing model is told.
    <language>/
      style.md                 Form of address, tone, typography, wording that repeats.
      typography.yml           Spaces around punctuation, put in by the machine. Optional.
      glossary.yml             By hand: prose terms, and overrides with a reason.
      glossary.generated.yml   Built from Spook's and Home Assistant's own strings.
      jokes.yml                Hashtags with a local version.
      examples.md              Good translations, from real pages.
      corrections.yml          Pinned sentences.
      stopwords.txt            Filler words, for the site's search.
  pipeline/                    The program that does the work.
  output/<language>/           What it writes. Never edited.
    content/                   The pages, file for file like documentation/content/.
    data/                      The text of the tour and the straight answers.
    locale.json                The site's own buttons and labels.
```

## How it works

A page is cut into sections: one heading and what is under it. Each section is translated on its own, and only when it has to be.

- **Masking.** Before a section goes to the model, everything that must not change is taken out and replaced by a token: code blocks, link targets, component names and their props. The model cannot break what it never sees.
- **Anchors.** Released versions of Spook link to headings like `/automation#snooze`. The pipeline writes that English anchor on every translated heading, so the link works in every language. The model never writes an anchor.
- **Labels.** Bold text in the docs is what Home Assistant shows on screen, like **Add action**. The pipeline looks every bold string up in the strings Home Assistant and Spook ship in that language, and the translation has to use exactly that. A bold string nothing matches stays English, and is listed under `unmatched` in `glossary.generated.yml`.
- **Checks.** A translated section is compared with the English one, line by line: the same headings, list items, table cells, components, links and code, the labels from the glossary, no leftover tokens. A second model then reads it for meaning. A page that fails a check is not written.
- **Only what changed.** A lock file next to every translated page holds a hash per section: of the English text, the glossary entries the section uses, and its pinned corrections. Same hash, and the section is copied from disk as it is. No model sees it, so it cannot be reworded.

One thing to know: a small edit to a style guide only reaches sections that are translated after it. Old and new sections can differ a little in style until everything is translated again. Raising `corpus_version` in `languages.yml` does that, on purpose and for money.

## Running it

From `documentation/`:

```bash
# What would be translated, without asking a model.
npm run translate -- sync --lang nl --dry-run

# Translate what changed. Needs ANTHROPIC_API_KEY.
npm run translate -- sync --lang nl
npm run translate -- sync --lang nl --page 04.enhanced-integrations/03.automation.md

# Which pages are behind the English.
npm run translate -- status

# Check every translated page against the English one.
npm run translate -- verify

# The tests of the pipeline itself.
npm run test:translate
```

A run that would send more sections than `budget_sections` in `languages.yml` stops, unless it gets `--full`.

### Translating by hand

`export` and `import` are the same run with a person in the place of the model. The first translations of Dutch and German were made this way.

```bash
npm run translate -- export --lang nl --page 09.guides/02.updating.md --work /tmp/translate
# Translate /tmp/translate/nl/09.guides/02.updating.en.md into 02.updating.nl.md, next to it.
npm run translate -- import --lang nl --page 09.guides/02.updating.md --work /tmp/translate
```

The import puts the translation through the same checks as a model run. The page is still generated: change the English or the corpus, and the affected sections are translated again.

### Changing words in a translation

To change a word in many sections, start from the translation that is there instead of from nothing. `--from-output` writes the work files with the current translation in them, masked with the same tokens a normal export has:

```bash
npm run translate -- export --lang es --page 04.enhanced-integrations/03.automation.md --from-output --work /tmp/translate
# Edit /tmp/translate/es/04.enhanced-integrations/03.automation.es.md: only the words you want.
npm run translate -- import --lang es --page 04.enhanced-integrations/03.automation.md --work /tmp/translate
```

Without `--section`, every translated section is in the work file. With one or more `--section <id>`, only those. The id is the English anchor, or `frontmatter` or `intro`.

What you leave alone comes back byte for byte, and its lock entry keeps the model and the date it had. Only the sections you changed are marked as yours. A section that is behind for a real reason is left out: its English changed, a glossary word it uses changed, it got a correction, or `corpus_version` went up. Its old translation is not a starting point. Translate that one with `sync`, or with a normal export. The one exception is a section behind only because a glossary entry it used was removed: the words it has are still right, so it is handed out like any other.

The tests run this round trip on every translated page.

This is a tool for when the corpus was wrong and the translation followed it. Fix the corpus first, so the next run does not bring the old word back.

### Typography

Some languages want a space before punctuation that is easy to get wrong, and impossible to see. French wants a non-breaking space before `:`, `;`, `!` and `?`, and inside « guillemets ». `<language>/typography.yml` lists those marks, and the assembler puts the space in every section it writes: a plain space is swapped, a missing one is added. Only in prose. Code, links, URLs, component props, image alt text, front matter keys and Home Assistant's own labels are left alone, and so is a mark with something right behind it, like the colon in `08:00`. A mark right after English the translation kept as it is, like "Boo!", keeps its English spacing.

A language without the file gets nothing done to it. After a change to the file, run it over what is already translated. Nothing goes to a model:

```bash
npm run translate -- normalize --lang fr
```

Bold and italic are fixed the same way, in every language, without a file. Markdown does not close `**` right after punctuation when a letter follows, so `**怎么修复：**从修复里` shows its asterisks. The assembler moves that punctuation out of the span (`**怎么修复**：从修复里`), puts a space in front of a span that starts with punctuation right after a letter (`选择 **+ 创建辅助元素**`), and turns `_` inside a word into `*`. A label ending in punctuation keeps it. Whatever is still not bold after that, `verify` reports: it renders each section and compares the `**` and `__` left as text with the English.

`normalize` also brings sections up to date that are behind only because a glossary entry they used went away, without changing a word of them.

### Rebuilding the glossary

```bash
npm run translate -- glossary --ha <directory>
```

The frontend's strings can also be downloaded: the [frontend repository](https://github.com/home-assistant/frontend) attaches its translations to its releases and nightly builds. That is the source to use in CI, where pulling the whole Home Assistant container for a few JSON files is a lot.

`<directory>` is a directory that has both `homeassistant` and `hass_frontend` in it, like a Python `site-packages`. The development environment of this repository has no frontend, so most buttons would have no match. The Home Assistant container has both, in two places: the frontend in `site-packages`, Home Assistant itself in `/usr/src/homeassistant`.

```bash
mkdir -p /tmp/ha-strings
docker run --rm --entrypoint sh ghcr.io/home-assistant/home-assistant:stable -c '
  cd /usr/local/lib/python3*/site-packages && tar cf - hass_frontend/static/translations
' | tar xf - -C /tmp/ha-strings
docker run --rm --entrypoint sh ghcr.io/home-assistant/home-assistant:stable -c '
  cd /usr/src/homeassistant && tar cf - homeassistant/components/*/translations homeassistant/const.py
' | tar xf - -C /tmp/ha-strings
npm run translate -- glossary --ha /tmp/ha-strings
```

Rebuild it when Home Assistant renames things, and when the English docs get new bold labels. Only the sections that use a changed label are translated again.

## Adding a language

1. Check that Spook itself is fully translated into it. Without that there is no glossary.
2. Add it to `languages.yml`, and copy the files of `nl/` into a directory of its own.
3. Write its `style.md` with somebody who speaks the language, and build its glossary.
4. Translate a few pages, have them read by that same somebody, and put what they change into the corpus, not into the pages.
