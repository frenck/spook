#!/usr/bin/env bash
# Fails when generated translations changed without a cause.
#
# Everything under documentation/translations/output/ is written by the
# translation pipeline. A change there is only real when something the
# pipeline reads changed with it: the English source, the corpus, or the
# pipeline itself. Anything else is a hand edit, and the next run throws
# it away.
#
# Usage, from anywhere in the repository:
#
#   documentation/translations/pipeline/check-output-untouched.sh [base-ref]
#
# Compares the working tree against the point where it left the base ref
# (default: origin/main). Untracked files are not seen, so stage or commit
# new files first.
set -euo pipefail

base_ref="${1:-origin/main}"

output_directory="documentation/translations/output/"

# What can legitimately make the output change.
cause_directories=(
  "documentation/content/"
  "documentation/locales/"
  "documentation/translations/corpus/"
  "documentation/translations/pipeline/"
)

cd "$(git rev-parse --show-toplevel)"

if ! merge_base="$(git merge-base "${base_ref}" HEAD)"; then
  echo "Could not find where this branch left '${base_ref}'." >&2
  echo "Is the ref fetched? A shallow clone does not have it." >&2
  exit 2
fi

changed_output=()
has_cause=false

# NUL-separated, so a path with odd characters in it cannot dodge the match.
while IFS= read -r -d '' path; do
  if [[ "${path}" == "${output_directory}"* ]]; then
    changed_output+=("${path}")
    continue
  fi

  for cause_directory in "${cause_directories[@]}"; do
    if [[ "${path}" == "${cause_directory}"* ]]; then
      has_cause=true
    fi
  done
done < <(git diff --name-only --no-renames -z "${merge_base}")

if [[ "${#changed_output[@]}" -eq 0 ]]; then
  echo "No generated translations changed. Nothing to check."
  exit 0
fi

if [[ "${has_cause}" == true ]]; then
  echo "Generated translations changed, together with their source. Fine."
  exit 0
fi

if [[ "${GITHUB_ACTIONS:-}" == "true" ]]; then
  echo "::error title=Machine-translated files were edited by hand::See the log of this step for what to do instead."
fi

{
  echo
  echo "👻 This changes machine-translated files, and nothing they are made from:"
  echo

  for path in "${changed_output[@]}"; do
    # A file name is somebody else's text: keep control characters out of the log.
    echo "  - ${path//[[:cntrl:]]/?}"
  done

  cat <<'MESSAGE'

Thanks for wanting to make a translation better! Sadly, this is not the
way to do it. The files in documentation/translations/output/ are
machine-translated and regenerated whenever the English text changes.
An edit made there is overwritten on the next run, so it cannot be merged.

What does work:

  - Spotted a mistake? Report it, that takes a minute:
    https://github.com/frenck/spook/issues/new?template=translation.yml

  - Want to fix it for good? Change what the translator works from: the
    style guides, glossaries and corrections in
    documentation/translations/corpus/. The pipeline picks those up and
    regenerates the pages.

  - Is the English text itself wrong? Fix it in documentation/content/.

Please take the changes to documentation/translations/output/ out of
this pull request.
MESSAGE
} >&2

exit 1
