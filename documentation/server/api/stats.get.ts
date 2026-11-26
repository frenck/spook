/**
 * Numbers about Spook from outside these docs, for the home page.
 *
 * Fetched once while the site is built and saved as a static file. A source
 * that cannot be reached leaves its number out, rather than failing the build
 * or showing a stale or made-up one.
 */

interface Stats {
  // Installations reported through Home Assistant's opt-in analytics. Only
  // those that share analytics are counted, so the real number is higher.
  installations: number | null;
  stars: number | null;
  // The newest release, so a visitor can see Spook is alive and kicking.
  release: { version: string; date: string } | null;
}

async function installations(): Promise<number | null> {
  try {
    const data = await $fetch<Record<string, { total?: number }>>(
      "https://analytics.home-assistant.io/custom_integrations.json",
    );
    return data.spook?.total ?? null;
  } catch {
    return null;
  }
}

async function stars(): Promise<number | null> {
  try {
    const data = await $fetch<{ stargazers_count?: number }>(
      "https://api.github.com/repos/frenck/spook",
      { headers: { Accept: "application/vnd.github+json" } },
    );
    return data.stargazers_count ?? null;
  } catch {
    return null;
  }
}

async function release(): Promise<Stats["release"]> {
  try {
    const data = await $fetch<{ tag_name?: string; published_at?: string }>(
      "https://api.github.com/repos/frenck/spook/releases/latest",
      { headers: { Accept: "application/vnd.github+json" } },
    );
    if (!data.tag_name || !data.published_at) {
      return null;
    }
    return { version: data.tag_name, date: data.published_at };
  } catch {
    return null;
  }
}

export default defineCachedEventHandler(
  async (): Promise<Stats> => ({
    installations: await installations(),
    stars: await stars(),
    release: await release(),
  }),
  { maxAge: 60 * 60 },
);
