import assert from "node:assert/strict";
import { test } from "node:test";

import { createSession } from "../src/session.js";

const FOTO_IDS = [11, 12, 13];

test("ohne Wahl bleibt weiter gesperrt, mit Wahl ist es erlaubt", () => {
  const session = createSession({ photoIds: FOTO_IDS });
  let zustand = session.zeige();

  assert.equal(zustand.nextEnabled, false);
  assert.equal(zustand.canChoose, true);

  zustand = session.setzeWahl("a");
  assert.equal(zustand.choice, "a");
  assert.equal(zustand.nextEnabled, true);
  assert.equal(zustand.canChoose, true);
});

test("ein Bildfehler sperrt die Wahl, nicht das Weiterblättern", () => {
  const session = createSession({ photoIds: FOTO_IDS });
  session.zeige();
  const zustand = session.bildFehler();

  assert.equal(zustand.bildKaputt, true);
  assert.equal(zustand.canChoose, false);
  assert.equal(zustand.nextEnabled, true);
  assert.equal(session.setzeWahl("b").choice, null);

  assert.equal(session.weiter().index, 1);
});

test("weiter ohne Wahl bewegt nichts", () => {
  const session = createSession({ photoIds: FOTO_IDS });
  session.zeige();

  assert.equal(session.weiter().index, 0);
  assert.equal(session.zurueck().index, 0);
});

test("zurück zeigt die vorherige Wahl wieder", () => {
  const session = createSession({ photoIds: FOTO_IDS });
  session.zeige();
  session.setzeWahl("a");
  assert.equal(session.weiter().index, 1);
  session.setzeWahl("b");

  const zurueck = session.zurueck();
  assert.equal(zurueck.index, 0);
  assert.equal(zurueck.photoId, 11);
  assert.equal(zurueck.choice, "a");
  assert.equal(zurueck.nextEnabled, true);
});

test("überspringen geht ohne Wahl weiter und behält frühere Stimmen", () => {
  const session = createSession({ photoIds: FOTO_IDS });
  session.zeige();
  session.setzeWahl("same");

  const gesprungen = session.ueberspringen();
  assert.equal(gesprungen.index, 1);

  const zurueck = session.zurueck();
  assert.equal(zurueck.choice, "same");
});

test("Startindex und gespeicherte Wahl kommen beim Laden wieder", () => {
  const session = createSession({
    photoIds: FOTO_IDS,
    startIndex: 1,
    saved: { 12: "same" },
  });
  const zustand = session.zeige();

  assert.equal(zustand.index, 1);
  assert.equal(zustand.photoId, 12);
  assert.equal(zustand.choice, "same");
  assert.equal(zustand.nextEnabled, true);
});

test("am Ende ist die Seite fertig und alle Knöpfe sind aus", () => {
  const session = createSession({ photoIds: FOTO_IDS, startIndex: 3 });
  const zustand = session.zeige();

  assert.equal(zustand.fertig, true);
  assert.equal(zustand.photoId, null);
  assert.equal(zustand.nextEnabled, false);
  assert.equal(zustand.skipEnabled, false);
  assert.equal(zustand.backEnabled, true);
});
