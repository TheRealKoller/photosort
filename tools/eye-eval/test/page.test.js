import assert from "node:assert/strict";
import { test } from "node:test";

import { assignSides } from "../src/ab.js";
import { renderComparisonPage, renderCompletionPage } from "../src/page.js";

function item(photoId, ueber = {}) {
  return {
    photoId,
    image: `images/${photoId}.jpg`,
    first: { verdict: "Stufe 4", reason: "Motiv klar, Moment getroffen." },
    second: { verdict: "Stufe 3", reason: "Ordentlich, ohne Höhepunkt." },
    ...ueber,
  };
}

function seite(anzahl = 120, extra = {}) {
  return renderComparisonPage({
    purpose: "albumtauglichkeit",
    purposeLabel: "Albumtauglichkeit",
    seed: 20261102,
    items: Array.from({ length: anzahl }, (_, index) => item(index + 1)),
    startIndex: 36,
    ...extra,
  });
}

test("die Seite nennt nur A und B und verrät die Herkunft nicht", () => {
  const { html } = seite();
  const klein = html.toLowerCase();

  for (const verraeter of [
    "cloud",
    "eye",
    "anthropic",
    "mistral",
    "claude",
    "modell",
    "anbieter",
    "konfidenz",
    "confidence",
  ]) {
    assert.equal(klein.includes(verraeter), false, `„${verraeter}“ steht im Markup`);
  }
  assert.ok(html.includes(">A<"));
  assert.ok(html.includes(">B<"));
});

test("die A/B-Zuordnung ist je Foto zufällig, stabil und ohne feste Alternation", () => {
  const { assignments } = seite(120);
  const seiten = assignments.map((row) => row.left);

  assert.equal(seiten.length, 120);
  assert.ok(seiten.includes("first"));
  assert.ok(seiten.includes("second"));

  const ersteHaelfte = seiten.slice(0, 60);
  assert.ok(ersteHaelfte.filter((wert) => wert === "first").length >= 15);
  assert.ok(ersteHaelfte.filter((wert) => wert === "second").length >= 15);

  const alternierend = seiten.every((wert, index) => wert === (index % 2 === 0 ? "first" : "second"));
  assert.equal(alternierend, false, "feste Alternation ist ein Verräter");
});

test("dieselbe Saat liefert dieselbe Zuordnung, eine andere eine andere", () => {
  const gleich = seite().assignments;
  assert.deepEqual(seite().assignments, gleich);

  const anders = seite(120, { seed: 4711 }).assignments;
  assert.notDeepEqual(anders, gleich);
});

test("assignSides hängt vom Foto, nicht von der Position ab", () => {
  const a = assignSides({ seed: 1, purpose: "albumtauglichkeit", photoId: 10 });
  const b = assignSides({ seed: 1, purpose: "albumtauglichkeit", photoId: 10 });
  assert.equal(a, b);

  const viele = Array.from({ length: 200 }, (_, index) =>
    assignSides({ seed: 1, purpose: "albumtauglichkeit", photoId: index }),
  );
  assert.ok(viele.includes("first"));
  assert.ok(viele.includes("second"));
});

test("beide Seiten sind immer besetzt", () => {
  assert.throws(
    () =>
      renderComparisonPage({
        purpose: "albumtauglichkeit",
        purposeLabel: "Albumtauglichkeit",
        seed: 1,
        items: [item(1, { second: { verdict: "", reason: "" } })],
      }),
    /beide Seiten/,
  );
});

test("Inhalte werden maskiert", () => {
  const { html } = renderComparisonPage({
    purpose: "albumtauglichkeit",
    purposeLabel: "<Album>",
    seed: 1,
    items: [item(1, { first: { verdict: "<b>1</b>", reason: 'a & b "x"' } })],
  });

  assert.equal(html.includes("<b>1</b>"), false);
  assert.equal(html.includes("</script><script>"), false);
  assert.ok(html.includes("&lt;Album&gt;"), "die Überschrift wird maskiert");
  assert.ok(html.includes("\\u003cb>1\\u003c/b>"), "das JSON maskiert <");
  assert.ok(html.includes('a & b \\"x\\"'));
});

test("die Tastaturbedienung deckt A/B/=, Enter/→, ← und S ab", () => {
  const { html } = seite();

  for (const taste of ["Enter", "ArrowRight", "ArrowLeft", "keydown"]) {
    assert.ok(html.includes(taste), taste);
  }
  assert.match(html, /case "a"/);
  assert.match(html, /case "b"/);
  assert.match(html, /case "="/);
  assert.match(html, /case "s"/);
  assert.match(html, /if \(!choice\) return/);
  assert.match(html, /closest\("button"\)/, "Enter auf einem Knopf darf nicht doppelt zählen");
  assert.ok(html.includes("44px"));
  assert.ok(html.includes("14px"));
  assert.ok(html.includes("outline"));
});

test("Fortschritt, Zurück und Überspringen sind sichtbar, ohne Zwischenstand der Urteile", () => {
  const { html } = seite();

  assert.match(html, /Foto \$\{index \+ 1\} von \$\{total\}/);
  assert.ok(html.includes("überspringen"));
  assert.ok(html.includes("zurück"));
  assert.equal(/Zwischenstand|Trefferquote|bisher \d/.test(html), false);
});

test("die Fortsetzung beginnt an der letzten Wahl", () => {
  const { html } = seite(120, { startIndex: 36 });
  assert.match(html, /"startIndex":36/);
  assert.match(html, /data-start="36"/);
});

test("jede Wahl bestätigt sichtbar und ein Schreibfehler ist deutlich", () => {
  const { html } = seite();
  assert.match(html, /role="status"/);
  assert.match(html, /role="alert"/);
  assert.match(html, /Gespeichert/);
  assert.match(html, /nicht gespeichert/);
  assert.match(html, /fetch\(/);
  assert.match(html, /localStorage/);
});

test("Bildzustände: Platzhalter, sichtbarer Sprung bei beschädigtem Bild", () => {
  const { html } = seite();
  assert.match(html, /Platzhalter|wird geladen/i);
  assert.match(html, /onerror/);
  assert.match(html, /übersprungen/);
});

test("Umschalter zwischen ganzem Bild und 100 %", () => {
  const { html } = seite();
  assert.ok(html.includes("ganzes Bild"));
  assert.ok(html.includes("100 %"));
});

test("die Seite bleibt statisch und lokal: keine externen Ressourcen", () => {
  const { html } = seite();

  assert.equal(html.includes("http://"), false);
  assert.equal(html.includes("https://"), false);
  assert.equal(html.includes("<link"), false);
  assert.equal(html.includes("data:"), false);
  assert.equal(/<script[^>]+src=/.test(html), false);
  assert.equal(html.includes("//cdn"), false);
});

test("Bildpfade sind relativ und tragen keinen Dateinamen", () => {
  const { html } = seite();
  assert.match(html, /images\/\d+\.jpg/);
  assert.equal(/\.heic|\.jpeg|\/home\/|\/Users\//.test(html), false);
});

test("die Abschlussseite zählt je Zweck und nennt kein Gesamturteil", () => {
  const html = renderCompletionPage({
    summaries: [
      {
        purpose: "albumtauglichkeit",
        label: "Albumtauglichkeit",
        counts: { better: 12, same: 30, worse: 8, skipped: 2, total: 52 },
      },
      {
        purpose: "ausschluss",
        label: "Ausschluss als Dokument oder Screenshot",
        counts: { better: 1, same: 40, worse: 3, skipped: 0, total: 44 },
      },
    ],
  });

  assert.ok(html.includes("Albumtauglichkeit"));
  assert.ok(html.includes("A trifft besser"));
  assert.ok(html.includes("beide gleich"));
  assert.ok(html.includes("B trifft besser"));
  assert.ok(html.includes(">12<"));
  assert.ok(html.includes(">30<"));
  assert.ok(html.includes("Gesamturteil"));
  assert.equal(html.includes("http"), false);
});
