/**
 * A contact sheet: screenshots stacked into one PNG, to look over a run.
 *
 * Opening forty WebP files one by one to spot the one with an English word
 * in it, or a dialog that did not open, takes a while. One tall picture of
 * them all is quicker to scroll, and easier to hand to somebody else.
 *
 *   npm run screenshots:sheet -- <out.png> <shot.webp> [<shot.webp> ...]
 *   npm run screenshots:sheet -- /tmp/nl.png public/images/screenshots/nl/light/*.webp
 */
import sharp from "sharp";

const WIDTH = 700;
const GAP = 20;
const BACKGROUND = "#8899aa";

const [output, ...shots] = process.argv.slice(2);
if (!output || !shots.length) {
  console.error(
    "Usage: npm run screenshots:sheet -- <out.png> <shot.webp> [<shot.webp> ...]",
  );
  process.exit(2);
}

// Every shot at the same width, one under the other, with a gap between.
const parts: sharp.OverlayOptions[] = [];
let top = 0;
for (const shot of shots) {
  const { data, info } = await sharp(shot)
    .resize({ width: WIDTH })
    .png()
    .toBuffer({ resolveWithObject: true });
  parts.push({ input: data, top, left: 0 });
  top += info.height + GAP;
}

await sharp({
  create: { width: WIDTH, height: top, channels: 4, background: BACKGROUND },
})
  .composite(parts)
  .png()
  .toFile(output);

console.log(`${shots.length} shot(s) on ${output}`);
