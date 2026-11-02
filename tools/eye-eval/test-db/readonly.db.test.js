import assert from "node:assert/strict";
import { test } from "node:test";

import { queriesForProjects } from "../src/baseline.js";
import { cacheExistsIn } from "../src/cache.js";
import { connectReadOnly, runQuery } from "../src/db.js";

/**
 * Opt-in-Integrationstest (Spec 0606, `## Teststrategie`): Read-only-Verbindung und
 * Etag/Cache-Abgleich gegen die echte Datenbank auf dem Heimserver.
 *
 * Nicht Teil von `npm test`. Ein fehlendes `EYE_EVAL_TEST_DATABASE_URL` ist ein LAUTER Fehlschlag
 * und kein stiller Skip — sonst wäre „der Test lief" nicht vom Gegenteil unterscheidbar.
 */
const DSN = process.env.EYE_EVAL_TEST_DATABASE_URL;
const CACHE = process.env.EYE_EVAL_TEST_PHOTO_CACHE_DIR;

if (!DSN) {
  throw new Error(
    "EYE_EVAL_TEST_DATABASE_URL ist nicht gesetzt. Dieser Test ist opt-in (`npm run test:db`) und braucht die echte Datenbank; ein Skip wäre kein Nachweis.",
  );
}
if (!CACHE) {
  throw new Error(
    "EYE_EVAL_TEST_PHOTO_CACHE_DIR ist nicht gesetzt (Pfad zum `photo_cache`-Volume, schreibgeschützt eingebunden).",
  );
}

test("die Verbindung ist read-only, geprüft und nicht angenommen", async (t) => {
  const client = await connectReadOnly(DSN);
  try {
    const { rows } = await client.query("SHOW default_transaction_read_only");
    assert.equal(rows[0].default_transaction_read_only, "on");

    await assert.rejects(
      () => client.query("UPDATE projects SET name = name WHERE false"),
      /read-only transaction/i,
      "ein Schreibversuch muss scheitern",
    );
    t.diagnostic("Integrationstest lief: Read-only-Verbindung und Schreibversuch geprüft.");
  } finally {
    await client.end();
  }
});

test("der Etag/Cache-Abgleich findet die display-Datei zum aktuellen etag", async (t) => {
  const client = await connectReadOnly(DSN);
  try {
    const projektZeilen = await runQuery(client, {
      sql: "SELECT id FROM projects ORDER BY id LIMIT 2",
      params: [],
    });
    assert.ok(projektZeilen.length >= 1, "mindestens ein Projekt muss existieren");

    const [kandidaten] = queriesForProjects(projektZeilen.map((row) => row.id));
    const rows = await runQuery(client, kandidaten);
    t.diagnostic(
      `Kandidaten mit Cloud-Grundlage und Albumtauglichkeit: ${rows.length} (gezählt, nicht benannt).`,
    );

    const vorhanden = cacheExistsIn(CACHE);
    let treffer = 0;
    for (const row of rows.slice(0, 200)) {
      if (vorhanden(row.photoId, row.etag)) treffer += 1;
    }
    t.diagnostic(
      `Etag/Cache-Abgleich über ${Math.min(rows.length, 200)} Fotos: ${treffer} stimmig.`,
    );
    assert.ok(rows.length === 0 || treffer > 0, "mindestens eine display-Datei muss passen");
  } finally {
    await client.end();
  }
});
