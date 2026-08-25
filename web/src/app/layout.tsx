import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "APIx — Real-time Airfare Price Index",
  description:
    "Prototype airfare price index for the CPI Transport & Communication sub-group: " +
    "compliant collection, matched-model index construction, and published provenance.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">
        <div className="mx-auto max-w-[1180px] px-5 pt-7 pb-16">
          <header className="mb-1">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h1 className="text-[23px] font-semibold tracking-[-0.01em]">
                APIx — Real-time Airfare Price Index
              </h1>
              <nav className="flex gap-4 text-[13.5px] text-[var(--text-secondary)]">
                <Link className="hover:text-[var(--s1)]" href="/">
                  Dashboard
                </Link>
                <Link className="hover:text-[var(--s1)]" href="/compliance">
                  Compliance
                </Link>
                <Link className="hover:text-[var(--s1)]" href="/methodology">
                  Methodology
                </Link>
                <Link className="hover:text-[var(--s1)]" href="/api/health">
                  API
                </Link>
              </nav>
            </div>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
