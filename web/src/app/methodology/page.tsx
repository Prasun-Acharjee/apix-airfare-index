import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { marked } from "marked";

export const metadata = {
  title: "Methodology — APIx",
  description:
    "Index construction, weighting, imputation, and what this project deliberately does not build.",
};

/**
 * The methodology document, rendered from the repository's own METHODOLOGY.md.
 * `scripts/sync-docs.mjs` copies it in before dev and build, so the page and the
 * repo cannot say different things.
 */
export default async function MethodologyPage() {
  const path = join(process.cwd(), "src", "content", "methodology.md");
  let markdown: string;
  try {
    markdown = await readFile(path, "utf8");
  } catch {
    markdown = "# Methodology\n\nDocument not available in this build.";
  }

  const html = await marked.parse(markdown, { gfm: true, breaks: false });

  return (
    <main className="prose-apix mt-4 max-w-[80ch]">
      <div dangerouslySetInnerHTML={{ __html: html }} />
    </main>
  );
}
