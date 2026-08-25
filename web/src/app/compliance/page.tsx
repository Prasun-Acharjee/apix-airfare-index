import Link from "next/link";
import { Card } from "@/components/Ui";
import { getCollectionLog, getSources } from "@/lib/queries";
import type { ComplianceStatus } from "@/lib/types";

// Rendered per request: a build must never require database access.
// Freshness is handled by CDN caching (see cacheHeaders / Cache-Control).
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Compliance — APIx",
  description: "Which sources this index collects from, and why the others are excluded.",
};

const STATUS_TONE: Record<ComplianceStatus, string> = {
  permitted: "text-[var(--good)]",
  permitted_with_delay: "text-[var(--good)]",
  blocked: "text-[var(--critical)]",
  blocked_partial: "text-[var(--critical)]",
  blocked_unverifiable: "text-[var(--critical)]",
};

export default async function CompliancePage() {
  const [sources, log] = await Promise.all([getSources(), getCollectionLog(50)]);
  const collected = sources.filter((s) => s.collectable);

  return (
    <main>
      <p className="mt-1 max-w-[70ch] text-[14px] text-[var(--text-secondary)]">
        Every outbound request passes a robots.txt gate that fails closed. There is no
        CAPTCHA solving, no proxy rotation and no fingerprint spoofing in this codebase —
        a 403, a 429 or a bot challenge is the operator declining us, and it is recorded
        as a non-response and handled by imputation rather than evaded.
      </p>

      <Card
        title={`Source registry — ${collected.length} of ${sources.length} collectable`}
        note="Verdicts come from the robots.txt audit stored in the database, not from a hard-coded list."
      >
        <div className="divide-y divide-[var(--border)]">
          {sources.map((s) => (
            <div key={s.id} className="grid gap-2 py-3 md:grid-cols-[300px_1fr]">
              <div>
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-flex rounded-full border border-[var(--border)] px-2 py-0.5 text-[11.5px] ${
                      s.collectable ? "text-[var(--good)]" : "text-[var(--critical)]"
                    }`}
                  >
                    {s.collectable ? "collected" : "excluded"}
                  </span>
                  <b className="text-[14px]">{s.name}</b>
                </div>
                <div className={`mt-1 text-[12px] ${STATUS_TONE[s.status]}`}>{s.status}</div>
                <div className="mt-0.5 text-[11.5px] text-[var(--text-muted)]">
                  {s.kind} · {s.carrierCodes.join(", ") || "—"}
                  {s.collectable ? ` · crawl-delay ${s.crawlDelayS}s` : ""}
                </div>
              </div>
              <p className="text-[12.5px] leading-relaxed text-[var(--text-secondary)]">
                {s.reason}
              </p>
            </div>
          ))}
        </div>
      </Card>

      <Card
        title="A robots.txt parser bug worth knowing about"
        note="Why this project does not use Python's standard library robots parser."
      >
        <p className="max-w-[80ch] text-[13.5px] leading-relaxed text-[var(--text-secondary)]">
          <code>urllib.robotparser</code> matches rules with{" "}
          <code>path.startswith(rule)</code>. It implements neither wildcards nor
          full-URL directives, and both failures are in the <b>permissive</b> direction.
        </p>
        <table className="tabular mt-3 w-full border-collapse text-[13px]">
          <thead>
            <tr>
              {["Directive", "stdlib verdict", "Correct verdict"].map((h) => (
                <th
                  key={h}
                  className="border-b border-[var(--border)] px-2.5 py-1.5 text-left text-[11.5px] font-medium uppercase tracking-[0.04em] text-[var(--text-muted)]"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[
              ["IndiGo — Disallow: /booking/*", "ALLOW", "DISALLOW"],
              ["SpiceJet — Disallow: https://www.spicejet.com/api/v1", "ALLOW", "DISALLOW"],
            ].map(([d, a, b]) => (
              <tr key={d}>
                <td className="border-b border-[var(--border)] px-2.5 py-1.5">
                  <code className="text-[12px]">{d}</code>
                </td>
                <td className="border-b border-[var(--border)] px-2.5 py-1.5 text-[var(--critical)]">
                  {a}
                </td>
                <td className="border-b border-[var(--border)] px-2.5 py-1.5 text-[var(--good)]">
                  {b}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-3 max-w-[80ch] text-[13.5px] leading-relaxed text-[var(--text-secondary)]">
          A collector built on the stdlib parser would believe it had permission to scrape
          IndiGo&rsquo;s entire booking tree and SpiceJet&rsquo;s fare API.{" "}
          <code>apix/compliance/rfc9309.py</code> implements RFC 9309 properly, and the
          difference is pinned by a test.
        </p>
      </Card>

      <Card
        title="Recent collection log"
        note="Blocks and failures are rows, not absences — this is what explains an imputed day."
      >
        {log.length === 0 ? (
          <p className="text-[13.5px] text-[var(--text-muted)]">
            No collection runs recorded yet. The log fills once{" "}
            <code>scripts/run_collection.py</code> has run against a live source.
          </p>
        ) : (
          <div className="max-h-[360px] overflow-auto">
            <table className="tabular w-full border-collapse text-[13px]">
              <tbody>
                {log.map((e) => (
                  <tr key={e.id}>
                    <td className="border-b border-[var(--border)] px-2.5 py-1.5">
                      {e.runAt.slice(0, 19).replace("T", " ")}
                    </td>
                    <td className="border-b border-[var(--border)] px-2.5 py-1.5">{e.sourceId}</td>
                    <td className="border-b border-[var(--border)] px-2.5 py-1.5">{e.outcome}</td>
                    <td className="border-b border-[var(--border)] px-2.5 py-1.5 text-[var(--text-muted)]">
                      {e.detail?.slice(0, 90) ?? ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <p className="mt-4 text-[13px] text-[var(--text-secondary)]">
        Full reasoning in{" "}
        <Link className="text-[var(--s1)] hover:underline" href="/methodology">
          the methodology
        </Link>
        , §6.
      </p>
    </main>
  );
}
