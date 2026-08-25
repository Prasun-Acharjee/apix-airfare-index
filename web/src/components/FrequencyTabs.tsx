"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";
import { FREQUENCIES, type Frequency } from "@/lib/types";

const LABEL: Record<Frequency, string> = {
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
};

export function FrequencyTabs({ active }: { active: Frequency }) {
  const router = useRouter();
  const params = useSearchParams();
  const [pending, startTransition] = useTransition();

  const select = (f: Frequency) => {
    const next = new URLSearchParams(params.toString());
    next.set("frequency", f);
    startTransition(() => router.push(`/?${next.toString()}`, { scroll: false }));
  };

  return (
    <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Index frequency">
      {FREQUENCIES.map((f) => {
        const on = f === active;
        return (
          <button
            key={f}
            type="button"
            role="tab"
            aria-selected={on}
            onClick={() => select(f)}
            disabled={pending}
            className={
              "cursor-pointer rounded-full border px-3 py-1 text-[13px] transition-opacity " +
              (on
                ? "border-[var(--s1)] bg-[var(--s1)] text-white"
                : "border-[var(--border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]") +
              (pending ? " opacity-60" : "")
            }
          >
            {LABEL[f]}
          </button>
        );
      })}
    </div>
  );
}
