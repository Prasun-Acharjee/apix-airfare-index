import type { ReactNode } from "react";
import type { Quality } from "@/lib/types";

export function Card({
  title,
  note,
  children,
  actions,
}: {
  title: string;
  note?: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section className="my-4 rounded-[10px] border border-[var(--border)] bg-[var(--surface-1)] px-[18px] pt-4 pb-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-[15px] font-semibold">{title}</h2>
          {note ? <p className="mt-0.5 text-[12.5px] text-[var(--text-muted)]">{note}</p> : null}
        </div>
        {actions}
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

export function Tile({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub: ReactNode;
}) {
  return (
    <div className="rounded-[10px] border border-[var(--border)] bg-[var(--surface-1)] px-4 py-3.5">
      <div className="text-xs uppercase tracking-[0.05em] text-[var(--text-muted)]">{label}</div>
      <div className="tabular mt-1.5 text-[27px] font-semibold tracking-[-0.02em]">{value}</div>
      <div className="mt-1 text-[12.5px] text-[var(--text-secondary)]">{sub}</div>
    </div>
  );
}

const QUALITY_CLASS: Record<Quality, string> = {
  ok: "text-[var(--good)]",
  warn: "text-[var(--warning)]",
  fail: "text-[var(--critical)]",
};

export function QualityPill({ quality, children }: { quality: Quality; children?: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] px-2 py-0.5 text-[11.5px] ${QUALITY_CLASS[quality]}`}
    >
      {children ?? quality}
    </span>
  );
}

export function Banner({ children }: { children: ReactNode }) {
  return (
    <div
      className="my-[18px] flex items-start gap-2.5 rounded-lg border px-3.5 py-2.5 text-[13.5px]"
      style={{
        background: "color-mix(in srgb, var(--warning) 11%, var(--surface-1))",
        borderColor: "color-mix(in srgb, var(--warning) 45%, transparent)",
      }}
    >
      <span className="font-bold" aria-hidden="true">
        ⚠
      </span>
      <span>{children}</span>
    </div>
  );
}
