/**
 * The Markdown copies of the pages (`/raw/*.md`, `llms-full.txt`) in plain
 * Markdown, without the components of the site. See `plainMarkdown`.
 */
export default defineNitroPlugin((nitroApp) => {
  nitroApp.hooks.hook("agent-discovery:document", (_event, page) => {
    if (!Array.isArray(page?.body?.value)) {
      return;
    }

    page.body.value = plainMarkdown(page.body.value, { page: page.path });
  });
});
