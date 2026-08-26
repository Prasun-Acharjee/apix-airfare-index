/**
 * Apply db/migrations/*.sql to $DATABASE_URL.
 *
 * Uses the `postgres` driver the app already depends on, so a schema can be
 * created without a psql client installed — which the previous `psql -f`
 * script required, and which also expanded `$DATABASE_URL` only on POSIX
 * shells. Every statement is IF NOT EXISTS, so re-running is a no-op.
 */
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import postgres from "postgres";

const migrations = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "db", "migrations");

const url = process.env.DATABASE_URL;
if (!url) {
  console.error(
    "DATABASE_URL is not set. Set it in web/.env.local, or export it:\n" +
      '  PowerShell: $env:DATABASE_URL = "postgresql://..."\n' +
      '  bash:       export DATABASE_URL="postgresql://..."',
  );
  process.exit(1);
}

const sql = postgres(url, { max: 1, connect_timeout: 10, prepare: false });

try {
  const files = readdirSync(migrations).filter((f) => f.endsWith(".sql")).sort();
  for (const file of files) {
    // .simple() — the migration is a multi-statement script, which the
    // extended query protocol refuses.
    await sql.unsafe(readFileSync(join(migrations, file), "utf8")).simple();
    console.log(`migrate: applied ${file}`);
  }
  console.log(`migrate: ${files.length} migration(s) applied`);
} catch (error) {
  console.error(`migrate: failed — ${error instanceof Error ? error.message : error}`);
  process.exitCode = 1;
} finally {
  await sql.end();
}
