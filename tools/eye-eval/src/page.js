import { assignSides } from "./ab.js";
import { readFileSync } from "node:fs";

const SESSION_QUELLE = readFileSync(new URL("./session.js", import.meta.url), "utf8").replace(
  /^export /gm,
  "",
);


/**
 * Erzeugt die Wegwerf-Vergleichsseite als reinen String — kein Framework, kein Build, keine
 * externe Ressource. Eine Wahl landet über den lokalen Läufer (`POST decisions`) in der
 * Entscheidungsdatei; ohne Läufer (Aufruf über `file://`) im `localStorage` des Browsers.
 *
 * Blindheit entsteht hier und nicht im Aufrufer: die Seite bekommt je Foto zwei neutrale Texte
 * und entscheidet selbst, welcher links steht. Welcher Text von welcher Seite kommt, steht
 * ausschließlich im zurückgegebenen `assignments` und wird in eine eigene Datei geschrieben —
 * nie ins Markup, nie in einen Kommentar.
 */
const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (zeichen) => ESCAPES[zeichen]);
}

function jsonFuerSkript(value) {
  return JSON.stringify(value).replace(/</g, "\\u003c").replace(/\u2028|\u2029/g, "");
}

function seitenText(seite) {
  return `${seite.verdict}\n${seite.reason}`.trim();
}

export function renderComparisonPage({
  purpose,
  purposeLabel,
  seed,
  items,
  startIndex = 0,
  total,
}) {
  if (!Array.isArray(items) || items.length === 0) {
    throw new Error("Die Seite braucht mindestens ein Foto.");
  }
  for (const item of items) {
    if (seitenText(item.first) === "" || seitenText(item.second) === "") {
      throw new Error(
        `Foto ${item.photoId}: beide Seiten müssen besetzt sein; eine leere Seite ist keine Wahl.`,
      );
    }
  }

  const assignments = [];
  const schritte = items.map((item) => {
    const links = assignSides({ seed, purpose, photoId: item.photoId });
    assignments.push({ photoId: item.photoId, left: links });
    const linksText = links === "first" ? item.first : item.second;
    const rechtsText = links === "first" ? item.second : item.first;
    return {
      photoId: item.photoId,
      image: item.image,
      textA: seitenText(linksText),
      textB: seitenText(rechtsText),
    };
  });

  const gesamt = total ?? items.length;
  const daten = {
    purpose,
    seed,
    startIndex,
    total: gesamt,
    steps: schritte,
  };

  const html = `<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vergleich – ${escapeHtml(purposeLabel)}</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; font: 16px/1.5 system-ui, sans-serif; background: #121212; color: #f2f2f2; }
  main { max-width: 980px; margin: 0 auto; padding: 16px; }
  h1 { font-size: 20px; margin: 0 0 8px; }
  .meta { display: flex; gap: 16px; align-items: center; justify-content: space-between; }
  .stage { background: #1c1c1c; border-radius: 8px; padding: 12px; margin: 12px 0; }
  .photo { display: block; width: 100%; max-height: 62vh; object-fit: contain; background: #000; }
  .photo.zoom { max-height: none; width: auto; max-width: none; }
  .scroll { overflow: auto; max-height: 62vh; }
  .placeholder { padding: 32px; text-align: center; color: #b9b9b9; }
  .sides { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .side { background: #232323; border-radius: 8px; padding: 12px; min-height: 96px; }
  .side h2 { margin: 0 0 6px; font-size: 16px; }
  .verdict { margin: 0 0 4px; font-weight: 600; }
  .reason { margin: 0; font-size: 14px; color: #dddddd; white-space: pre-line; }
  .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
  button { min-height: 44px; min-width: 44px; padding: 10px 14px; font: inherit; border-radius: 8px;
    border: 1px solid #666; background: #2a2a2a; color: #f2f2f2; cursor: pointer; }
  button[aria-pressed="true"] { background: #3d5afe; border-color: #3d5afe; }
  button:disabled { opacity: 0.5; cursor: default; }
  button:focus-visible, a:focus-visible { outline: 3px solid #ffd54f; outline-offset: 2px; }
  #status { color: #9ccc65; min-height: 1.5em; }
  #error { color: #ff8a80; min-height: 1.5em; }
  #done { display: none; }
</style>
</head>
<body data-start="${startIndex}">
<main>
  <h1>${escapeHtml(purposeLabel)}</h1>
  <div class="meta">
    <p id="progress" aria-live="polite">Foto ${startIndex + 1} von ${gesamt}</p>
    <button id="zoom" type="button" aria-pressed="false">ganzes Bild</button>
  </div>

  <section id="card">
    <div class="stage scroll">
      <p class="placeholder" id="placeholder">Bild wird geladen …</p>
      <img class="photo" id="photo" alt="Foto" hidden>
    </div>
    <div class="sides">
      <section class="side" aria-labelledby="label-a">
        <h2 id="label-a">A</h2>
        <p class="verdict" id="a-verdict"></p>
        <p class="reason" id="a-reason"></p>
      </section>
      <section class="side" aria-labelledby="label-b">
        <h2 id="label-b">B</h2>
        <p class="verdict" id="b-verdict"></p>
        <p class="reason" id="b-reason"></p>
      </section>
    </div>
    <p class="actions">
      <button type="button" data-choice="a">A trifft besser (A)</button>
      <button type="button" data-choice="same">beide gleich (=)</button>
      <button type="button" data-choice="b">B trifft besser (B)</button>
    </p>
    <p class="actions">
      <button type="button" id="back">← zurück</button>
      <button type="button" id="next">Enter / → weiter</button>
      <button type="button" id="skip">S überspringen</button>
    </p>
    <p id="status" role="status"></p>
    <p id="error" role="alert"></p>
  </section>

  <section id="done">
    <h2>Fertig</h2>
    <p>Alle Fotos dieses Durchlaufs sind bearbeitet. Die Abschlussseite zeigt die Zählungen je
    Zweck; sie entsteht aus der Entscheidungsdatei.</p>
  </section>
</main>
<script type="application/json" id="data">${jsonFuerSkript(daten)}</script>
<script>
${SESSION_QUELLE}
(() => {
  "use strict";
  const DATA = JSON.parse(document.getElementById("data").textContent);
  const schluessel = "vergleich:" + DATA.purpose + ":" + DATA.seed;
  const gespeichert = JSON.parse(localStorage.getItem(schluessel) || "{}");
  const laeufer = location.protocol === "http:" || location.protocol === "https:";
  const session = createSession({
    photoIds: DATA.steps.map((schritt) => schritt.photoId),
    startIndex: DATA.startIndex,
    saved: gespeichert,
  });
  const photo = document.getElementById("photo");
  const placeholder = document.getElementById("placeholder");
  const progress = document.getElementById("progress");
  const status = document.getElementById("status");
  const fehler = document.getElementById("error");
  const knopf = {
    back: document.getElementById("back"),
    next: document.getElementById("next"),
    skip: document.getElementById("skip"),
    zoom: document.getElementById("zoom"),
  };
  let gezeigt = null;

  function zeichne(zustand) {
    const fertig = zustand.fertig;
    const schritt = fertig ? null : DATA.steps[zustand.index];
    document.getElementById("card").style.display = fertig ? "none" : "block";
    document.getElementById("done").style.display = fertig ? "block" : "none";
    knopf.back.disabled = !zustand.backEnabled;
    knopf.next.disabled = !zustand.nextEnabled;
    knopf.skip.disabled = !zustand.skipEnabled;
    for (const button of document.querySelectorAll("[data-choice]")) {
      button.setAttribute("aria-pressed", String(button.dataset.choice === zustand.choice));
      button.disabled = !zustand.canChoose;
    }
    if (fertig) {
      progress.textContent = "Foto " + zustand.total + " von " + zustand.total;
      return;
    }

    progress.textContent = "Foto " + (zustand.index + 1) + " von " + zustand.total;
    const [urteilA, ...grundA] = schritt.textA.split("\\n");
    const [urteilB, ...grundB] = schritt.textB.split("\\n");
    document.getElementById("a-verdict").textContent = urteilA;
    document.getElementById("a-reason").textContent = grundA.join("\\n");
    document.getElementById("b-verdict").textContent = urteilB;
    document.getElementById("b-reason").textContent = grundB.join("\\n");

    if (gezeigt !== schritt.photoId) {
      gezeigt = schritt.photoId;
      photo.hidden = true;
      placeholder.hidden = false;
      placeholder.textContent = "Bild wird geladen …";
      fehler.textContent = "";
      photo.src = schritt.image;
    }
    if (zustand.bildKaputt) {
      photo.hidden = true;
      placeholder.hidden = false;
      placeholder.textContent = "Bild fehlt oder ist beschädigt – dieses Foto wird übersprungen.";
    }
    status.textContent = zustand.choice
      ? laeufer
        ? "Gespeichert"
        : "Gespeichert (nur in diesem Browser)"
      : "";
  }

  function speichern(photoId, wert) {
    gespeichert[photoId] = wert;
    try {
      localStorage.setItem(schluessel, JSON.stringify(gespeichert));
    } catch (problem) {
      fehler.textContent = "Die Wahl wurde nicht gespeichert: " + problem.message;
      return;
    }
    if (!laeufer) return;
    fetch("decisions", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ purpose: DATA.purpose, photoId: photoId, choice: wert, index: session.zustand().index + 1 }),
    })
      .then((antwort) => {
        if (!antwort.ok) throw new Error(String(antwort.status));
        fehler.textContent = "";
      })
      .catch((problem) => {
        fehler.textContent = "Die Wahl wurde nicht gespeichert: " + problem.message;
      });
  }

  function setzeWahl(wert) {
    const zustand = session.setzeWahl(wert);
    if (zustand.choice === wert) speichern(zustand.photoId, wert);
    zeichne(zustand);
  }

  function ueberspringen() {
    const photoId = session.aktuell();
    const zustand = session.ueberspringen();
    if (photoId !== null && laeufer) {
      fetch("decisions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ purpose: DATA.purpose, photoId: photoId, skip: true, index: zustand.index }),
      }).catch((problem) => {
        fehler.textContent = "Der Sprung wurde nicht gespeichert: " + problem.message;
      });
    }
    zeichne(zustand);
  }

  photo.onerror = () => {
    const zustand = session.bildFehler();
    zeichne(zustand);
    fehler.textContent = "Die Wahl wurde nicht gespeichert: kein Bild, kein Urteil.";
  };
  photo.onload = () => {
    placeholder.hidden = true;
    photo.hidden = false;
    fehler.textContent = "";
  };

  knopf.next.addEventListener("click", () => zeichne(session.weiter()));
  knopf.back.addEventListener("click", () => zeichne(session.zurueck()));
  knopf.skip.addEventListener("click", ueberspringen);
  knopf.zoom.addEventListener("click", () => {
    const an = photo.classList.toggle("zoom");
    knopf.zoom.setAttribute("aria-pressed", String(an));
    knopf.zoom.textContent = an ? "100 %" : "ganzes Bild";
  });
  for (const button of document.querySelectorAll("[data-choice]")) {
    button.addEventListener("click", () => setzeWahl(button.dataset.choice));
  }

  document.addEventListener("keydown", (event) => {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    // Ein fokussierter Knopf löst bei Enter bereits seinen Klick aus; ohne diese Sperre zählte
    // derselbe Tastendruck zweimal und überspränge ein Foto.
    if (event.key === "Enter" && event.target.closest && event.target.closest("button")) return;
    switch (event.key) {
      case "a":
        setzeWahl("a");
        break;
      case "b":
        setzeWahl("b");
        break;
      case "=":
        setzeWahl("same");
        break;
      case "Enter":
      case "ArrowRight":
        zeichne(session.weiter());
        break;
      case "ArrowLeft":
        zeichne(session.zurueck());
        break;
      case "s":
        ueberspringen();
        break;
      default:
        break;
    }
  });

  zeichne(session.zeige());
})();
</script>
</body>
</html>
`;

  return { html, assignments };
}

export function renderCompletionPage({ summaries }) {
  const zeilen = summaries
    .map(
      (summary) => `<tr>
      <th scope="row">${escapeHtml(summary.label)}</th>
      <td>${summary.counts.better}</td>
      <td>${summary.counts.same}</td>
      <td>${summary.counts.worse}</td>
      <td>${summary.counts.skipped}</td>
      <td>${summary.counts.total}</td>
    </tr>`,
    )
    .join("\n");

  return `<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Abschluss des Vergleichs</title>
<style>
  body { margin: 0; font: 16px/1.5 system-ui, sans-serif; background: #121212; color: #f2f2f2; }
  main { max-width: 880px; margin: 0 auto; padding: 16px; }
  table { width: 100%; border-collapse: collapse; margin-top: 12px; }
  th, td { text-align: left; padding: 8px; border-bottom: 1px solid #444; }
  td { text-align: right; }
  p { color: #dddddd; }
</style>
</head>
<body>
<main>
  <h1>Abschluss</h1>
  <p>Zählungen der Paarvergleiche je Zweck. Es gibt kein Gesamturteil über alle Zwecke; die
  Urteile entstehen aus diesen Zählungen je Zweck.</p>
  <table>
    <thead>
      <tr><th scope="col">Zweck</th><th scope="col">A trifft besser</th>
      <th scope="col">beide gleich</th><th scope="col">B trifft besser</th>
      <th scope="col">übersprungen</th><th scope="col">bearbeitet</th></tr>
    </thead>
    <tbody>
${zeilen}
    </tbody>
  </table>
</main>
</body>
</html>
`;
}
