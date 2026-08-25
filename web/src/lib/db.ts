import "server-only";
import postgres, { type Sql } from "postgres";

/**
 * Postgres client.
 *
 * The Python collector and index worker own writes; this app only reads.
 *
 * The connection is created lazily, on first query. That matters for
 * deployment: Next.js imports every route module during the build to collect
 * page data, and a client constructed at module scope would throw there and
 * fail the build on any machine without DATABASE_URL — including a CI runner
 * that legitimately has no database. Nothing connects until a request runs.
 *
 * The pool is deliberately small and short-idle. Serverless instances are many
 * and short-lived, and a large pool per instance is how a serverless app
 * exhausts a Postgres connection limit. On Neon, point DATABASE_URL at the
 * *pooled* connection string.
 */

declare global {
  // Reused across hot reloads in dev so we don't leak connections.
  var __apixSql: Sql | undefined;
}

function create(): Sql {
  const url = process.env.DATABASE_URL;
  if (!url) {
    throw new Error(
      "DATABASE_URL is not set. Copy web/.env.example to web/.env.local and point " +
        "it at your Postgres instance, then run `npm run db:migrate`.",
    );
  }
  return postgres(url, {
    max: 3,
    idle_timeout: 20,
    connect_timeout: 10,
    // Pooled connections (pgbouncer, Neon pooler) do not support prepared statements.
    prepare: false,
    types: {
      // Return DATE columns as plain `YYYY-MM-DD` strings rather than JS Dates.
      // A Date is an instant: it would be parsed as UTC midnight and rendered in
      // the viewer's local zone, showing the previous day to anyone west of UTC.
      // Every date here is a calendar date, so it stays text end to end.
      date: {
        to: 1082,
        from: [1082],
        serialize: (x: string) => x,
        parse: (x: string) => x,
      },
    },
  });
}

let client: Sql | undefined;

/** The lazily-created client. Throws only when a query is actually attempted. */
export function db(): Sql {
  if (globalThis.__apixSql) return globalThis.__apixSql;
  client ??= create();
  if (process.env.NODE_ENV !== "production") globalThis.__apixSql = client;
  return client;
}

/**
 * Tagged-template proxy so call sites keep reading ``sql`SELECT ...` `` while
 * connection creation stays deferred to the first call.
 */
export const sql = new Proxy((() => undefined) as unknown as Sql, {
  apply(_target, _thisArg, args: Parameters<Sql>) {
    return Reflect.apply(db() as unknown as (...a: unknown[]) => unknown, undefined, args);
  },
  get(_target, prop, receiver) {
    return Reflect.get(db() as unknown as object, prop, receiver);
  },
}) as Sql;
