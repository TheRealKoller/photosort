import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { PinError, loadPins, verifyPins } from "../src/pins.js";

async function mitModell(rumpf) {
  const verzeichnis = mkdtempSync(join(tmpdir(), "eye-eval-pins-"));
  try {
    writeFileSync(join(verzeichnis, "eye.tflite"), "gewichtsdaten");
    writeFileSync(join(verzeichnis, "eye_meta.json"), "{}");
    return await rumpf(verzeichnis);
  } finally {
    rmSync(verzeichnis, { recursive: true, force: true });
  }
}

const sha256 = (text) => createHash("sha256").update(text).digest("hex");

function pins() {
  return {
    revision: "v1.0.0",
    commit: "0123456789abcdef0123456789abcdef01234567",
    files: {
      "eye.tflite": sha256("gewichtsdaten"),
      "eye_meta.json": sha256("{}"),
    },
  };
}

test("stimmige Gewichte bestehen die Prüfung", () =>
  mitModell(async (verzeichnis) => {
    const ergebnis = await verifyPins({ directory: verzeichnis, pins: pins() });
    assert.equal(ergebnis.ok, true);
    assert.deepEqual(ergebnis.checked.sort(), ["eye.tflite", "eye_meta.json"]);
  }));

test("ein geänderter Hash bricht vor dem Laden ab", () =>
  mitModell(async (verzeichnis) => {
    const falsch = pins();
    falsch.files["eye.tflite"] = sha256("etwas anderes");
    await assert.rejects(() => verifyPins({ directory: verzeichnis, pins: falsch }), (error) => {
      assert.ok(error instanceof PinError);
      assert.match(error.message, /eye\.tflite/);
      assert.match(error.message, /SHA-256/);
      return true;
    });
  }));

test("eine fehlende Gewichtsdatei bricht ab", () =>
  mitModell(async (verzeichnis) => {
    const ohne = pins();
    ohne.files["eye.mlmodelc"] = sha256("fehlt");
    await assert.rejects(() => verifyPins({ directory: verzeichnis, pins: ohne }), /fehlt/);
  }));

test("ohne pins.json gibt es keinen Lauf", () =>
  mitModell(async (verzeichnis) => {
    await assert.rejects(
      () => loadPins(verzeichnis),
      (error) => {
        assert.ok(error instanceof PinError);
        assert.match(error.message, /pins\.json/);
        return true;
      },
    );
  }));

test("pins.json wird gelesen", () =>
  mitModell(async (verzeichnis) => {
    writeFileSync(join(verzeichnis, "pins.json"), JSON.stringify(pins()));
    const gelesen = await loadPins(verzeichnis);
    assert.equal(gelesen.revision, "v1.0.0");
  }));

test("ohne Revision oder Commit-SHA gibt es keinen Lauf (S20)", () =>
  mitModell(async (verzeichnis) => {
    for (const feld of ["revision", "commit"]) {
      const ohne = pins();
      delete ohne[feld];
      await assert.rejects(
        () => verifyPins({ directory: verzeichnis, pins: ohne }),
        (error) => {
          assert.ok(error instanceof PinError);
          assert.match(error.message, new RegExp(feld));
          return true;
        },
      );
    }
  }));

test("ein Commit-SHA, der kein 40-stelliger Hexwert ist, bricht ab", () =>
  mitModell(async (verzeichnis) => {
    for (const falsch of ["", "v1.0.0", "0123456789abcdef", "0123456789ABCDEF0123456789abcdef01234567", "z".repeat(40)]) {
      const kaputt = pins();
      kaputt.commit = falsch;
      await assert.rejects(() => verifyPins({ directory: verzeichnis, pins: kaputt }), PinError);
    }
    const falscheRevision = pins();
    falscheRevision.revision = "";
    await assert.rejects(() => verifyPins({ directory: verzeichnis, pins: falscheRevision }), /revision/);
  }));

test("die geprüfte Revision und der Commit stehen im Ergebnis", () =>
  mitModell(async (verzeichnis) => {
    const ergebnis = await verifyPins({ directory: verzeichnis, pins: pins() });
    assert.equal(ergebnis.revision, "v1.0.0");
    assert.equal(ergebnis.commit, "0123456789abcdef0123456789abcdef01234567");
  }));
