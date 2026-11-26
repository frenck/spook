# Spook

Spook is a custom integration for Home Assistant: repairs, actions, triggers, conditions and helpers on top of what Home Assistant ships.
The integration lives in `custom_components/spook/`, its tests in `tests/`.
The website (<https://spook.boo>) lives in `documentation/`: Nuxt, Nuxt UI and Nuxt Content.

## Commands

The integration uses [uv](https://docs.astral.sh/uv/). From the repository root:

- `uv sync`: install everything.
- `uv run pytest`: run the tests.
- `uv run ruff check .` and `uv run ruff format .`: lint and format.
- `uv run prek run pylint --all-files`: pylint.
- `uv run prek run --all-files`: every hook in `.pre-commit-config.yaml`.
- `uv run zizmor .github/workflows/`: check the workflows.
- `uv run python script/generate_skill.py`: rebuild the agent skill references after adding or changing an action, trigger, condition or repair. A test fails when they are stale.

The website, from `documentation/`:

- `npm ci`: install.
- `npm run dev`: local site on `http://localhost:3000`.
- `npm run build`: the build CI runs.

## Rules

- English is the source. People edit `documentation/content/` and `documentation/locales/en.json`, nothing else of the website's text.
- Headings on documentation pages are a contract: their anchors are linked from the integration and from other sites. Do not rename an existing heading.
- `custom_components/spook/translations/en.json` is the only translation file of the integration edited by hand. Weblate owns the other languages.
- Write "Home Assistant" in full.

## Website translations

The website is machine-translated. Three directories, three rules:

- `documentation/translations/output/`: _generated_. Never edit a file in it, not even to fix a typo. The next pipeline run overwrites it.
- `documentation/translations/corpus/`: hand-edited. The style guides, glossaries and corrections the translator works from. A translation improvement goes here. The exception: files named `glossary.generated.yml` are generated too, leave them alone.
- `documentation/translations/pipeline/`: the scripts that turn English plus corpus into output.

A translation is wrong? Fix the English source or the corpus, and let the pipeline regenerate the output.

CI enforces this. A pull request that touches `documentation/translations/output/` without a change in `documentation/content/`, `documentation/locales/`, `documentation/translations/corpus/` or `documentation/translations/pipeline/` fails. Run the same check locally:

```bash
documentation/translations/pipeline/check-output-untouched.sh origin/main
```

People who spot a translation problem report it with the form: <https://github.com/frenck/spook/issues/new?template=translation.yml>
