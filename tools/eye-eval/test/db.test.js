import assert from "node:assert/strict";
import { test } from "node:test";

import { redactDsn } from "../src/db.js";

test("Fehlermeldungen geben die Datenbank-URL ohne Zugangsdaten aus", () => {
  const meldung =
    "connect ECONNREFUSED for postgresql://photosort:geheim@db:5432/photosort password=geheim";
  const redigiert = redactDsn(meldung);

  assert.equal(redigiert.includes("geheim"), false);
  assert.equal(redigiert.includes("postgresql://"), false);
  assert.match(redigiert, /<dsn>/);
  assert.match(redigiert, /ECONNREFUSED/);
});
