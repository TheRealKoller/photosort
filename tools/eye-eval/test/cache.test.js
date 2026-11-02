import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import {
  cacheExistsIn,
  cacheKey,
  displayPath,
  displayVariantName,
} from "../src/cache.js";

test("der Cache-Schlüssel entspricht backend/src/photosort/thumbnails.py::cache_key", () => {
  // Feste Vektoren: sha256("<photo_id>:<etag>"). Ändert sich hier etwas, findet das Werkzeug die
  // Datei nicht mehr, die die Cloud bekommen hat.
  assert.equal(
    cacheKey(42, "etag-abc"),
    "0e3107e47daf27a0691ef838e55b452903eeafc5253b9701abf87ed5891dceaa",
  );
  assert.equal(
    cacheKey(1, "abc"),
    "fac4d75282e3de358e8a42f2e1166bfe879257cdfb0961daf46b42003058b1a8",
  );
});

test("der Dateiname der display-Variante trägt den Schlüssel und die Endung", () => {
  assert.equal(
    displayVariantName(42, "etag-abc"),
    "0e3107e47daf27a0691ef838e55b452903eeafc5253b9701abf87ed5891dceaa_display.jpg",
  );
  assert.equal(
    displayPath("/cache", 42, "etag-abc"),
    join(
      "/cache",
      "0e3107e47daf27a0691ef838e55b452903eeafc5253b9701abf87ed5891dceaa_display.jpg",
    ),
  );
});

test("cacheExistsIn zählt fehlende, leere und fremde etags als Ausfall", () => {
  const verzeichnis = mkdtempSync(join(tmpdir(), "eye-eval-cache-"));
  try {
    writeFileSync(displayPath(verzeichnis, 1, "abc"), "pixel");
    writeFileSync(displayPath(verzeichnis, 2, "abc"), "");
    const vorhanden = cacheExistsIn(verzeichnis);

    assert.equal(vorhanden(1, "abc"), true);
    assert.equal(vorhanden(1, "neu"), false, "abweichender etag ist ein Ausfall");
    assert.equal(vorhanden(2, "abc"), false, "leere Datei ist ein Ausfall");
    assert.equal(vorhanden(3, "abc"), false, "fehlende Datei ist ein Ausfall");
  } finally {
    rmSync(verzeichnis, { recursive: true, force: true });
  }
});
