#!/usr/bin/env sh
# A Home Assistant in Docker that runs Spook from this checkout, to look at
# the frontends in a real one.
#
# Spook is mounted, not copied: a build in `frontend/` lands in the running
# Home Assistant straight away. The configuration lives in a Docker volume,
# so it survives a restart and leaves no files owned by root behind.
#
#   npm run home-assistant                       start it, on port 18125
#   HA_IMAGE=...:beta npm run home-assistant     against the beta
#   docker volume rm spook-home-assistant        start over from scratch
set -eu

here=$(cd "$(dirname "$0")" && pwd)
spook="$here/../../custom_components/spook"
state="$here/../.home-assistant"

image="${HA_IMAGE:-ghcr.io/home-assistant/home-assistant:stable}"
port="${HA_PORT:-18125}"
name="spook-home-assistant"

# The manifest in the repository says 0.0.0 until a release stamps it, and
# Home Assistant blocks Spook below 4.0.0. The mounted copy gets the version
# of the latest release laid over it.
mkdir -p "$state"
version=$(git -C "$here" describe --tags --abbrev=0 | sed 's/^v//')
sed "s/\"version\": \"0.0.0\"/\"version\": \"$version\"/" \
  "$spook/manifest.json" > "$state/manifest.json"

docker rm --force "$name" > /dev/null 2>&1 || true
docker pull --quiet "$image" > /dev/null

echo "Home Assistant with Spook $version from this checkout: http://127.0.0.1:$port"
exec docker run --rm --name "$name" \
  --publish "127.0.0.1:$port:8123" \
  --env TZ="${TZ:-Europe/Amsterdam}" \
  --volume "$name:/config" \
  --volume "$spook:/config/custom_components/spook:ro" \
  --volume "$state/manifest.json:/config/custom_components/spook/manifest.json:ro" \
  "$image"
