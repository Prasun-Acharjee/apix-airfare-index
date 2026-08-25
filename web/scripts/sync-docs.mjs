/**
 * Copy the repo's methodology document into the app so the site and the
 * repository cannot drift apart. Runs before dev and build.
 *
 * If the file is missing — e.g. the web directory was deployed on its own — the
 * page falls back to a stub rather than failing the build.
 */
import { copyFileSync, existsSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "..", "..");
const outDir = join(here, "..", "src", "content");
const out = join(outDir, "methodology.md");

mkdirSync(outDir, { recursive: true });

const source = join(repoRoot, "METHODOLOGY.md");
if (existsSync(source)) {
  copyFileSync(source, out);
  console.log("sync-docs: copied METHODOLOGY.md");
} else if (!existsSync(out)) {
  writeFileSync(
    out,
    "# Methodology\n\n`METHODOLOGY.md` was not found at the repository root when this " +
      "build ran. See the project repository for the full document.\n",
  );
  console.log("sync-docs: METHODOLOGY.md not found, wrote stub");
} else {
  console.log("sync-docs: source missing, keeping existing copy");
}
