import { BaselineError, assertReadOnly, readOnlyQueryOptions } from "./baseline.js";

/**
 * Die einzige Stelle, die Postgres berührt. `pg` wird erst hier dynamisch geladen, damit der
 * Unit-Test-Lauf ohne installierte Abhängigkeiten und ohne Datenbank auskommt.
 *
 * Die Verbindung trägt `default_transaction_read_only=on` im Startpaket und wird danach per
 * `SHOW` geprüft (S13). Fehlermeldungen werden ohne DSN ausgegeben (S15): die URL enthält das
 * Passwort der Anwendungsrolle.
 */
export function redactDsn(text) {
  return String(text)
    .replace(/postgres(?:ql)?:\/\/\S+/gi, "<dsn>")
    .replace(/password=\S+/gi, "password=<redacted>");
}

function camelize(row) {
  const ziel = {};
  for (const [schluessel, wert] of Object.entries(row)) {
    ziel[schluessel.replace(/_([a-z0-9])/g, (_, zeichen) => zeichen.toUpperCase())] = wert;
  }
  return ziel;
}

export async function connectReadOnly(databaseUrl) {
  if (typeof databaseUrl !== "string" || databaseUrl.trim() === "") {
    throw new BaselineError("EYE_EVAL_DATABASE_URL fehlt; ohne Datenbank gibt es keinen Maßstab.");
  }
  const { Client } = await import("pg");
  const client = new Client({
    connectionString: databaseUrl,
    options: readOnlyQueryOptions(),
  });
  try {
    await client.connect();
  } catch (error) {
    throw new BaselineError(
      `Verbindung zur Datenbank fehlgeschlagen: ${redactDsn(error.message)}`,
    );
  }
  const { rows } = await client.query("SHOW default_transaction_read_only");
  assertReadOnly(rows[0]?.default_transaction_read_only);
  return client;
}

export async function runQuery(client, { sql, params }) {
  const { rows } = await client.query(sql, params);
  return rows.map(camelize);
}
