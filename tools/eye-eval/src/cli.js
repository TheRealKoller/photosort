#!/usr/bin/env node
import { existsSync } from "node:fs";
import { copyFile, mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

import { ArgsError, parseArgs, usage } from "./args.js";
import { assembleBaseline, queriesForPhotos, queriesForProjects } from "./baseline.js";
import { cacheExistsIn, displayPath } from "./cache.js";
import { countCalls } from "./calls.js";
import { buildItems, PURPOSE_ORDER } from "./compare.js";
import { connectReadOnly, runQuery } from "./db.js";
import {
  DecisionStoreError,
  countChoices,
  createState,
  loadState,
  recordChoice,
  recordSkip,
  saveState,
} from "./decisions.js";
import { analyzeDisplayFile, assertLicenseEnvironment, openModel } from "./eye.js";
import { EYE_PURPOSE_MAPPING, EYE_PURPOSE_MAPPING_HASH, assertMappingHash } from "./mapping.js";
import { renderComparisonPage, renderCompletionPage } from "./page.js";
import { repoRootFromModule, resolveWorkDir, toolRootFromModule } from "./paths.js";
import { checkReport, formatFindings } from "./report.js";
import { parseRun } from "./runfile.js";
import { selectSample } from "./sample.js";
import { computeSavings } from "./savings.js";
import { ladeAbMap, mapVotes } from "./votes.js";

const RUN_FILE = "run.json";
const INPUT_FILE = "projects.json";
const NAMES_FILE = "names.json";
const DECISIONS_FILE = "decisions.json";
const IMAGES_DIR = "images";
const ANALYSIS_DIR = "analysis";
const SUMMARY_FILE = "summary.json";
const AB_MAP_FILE = "ab-map.json";
const RUNTIME_FILE = "runtime.json";

const TOOL_ROOT = toolRootFromModule(import.meta.url);
const REPO_ROOT = repoRootFromModule(import.meta.url);
const IST_CHECKOUT = existsSync(join(REPO_ROOT, "backend")) || existsSync(join(REPO_ROOT, ".git"));
const STATISCH = /^\/?(page-[a-z]+\.html|images\/\d+\.jpg)$/;

function umgebung(name) {
  const wert = process.env[name];
  if (!wert) {
    throw new Error(`${name} fehlt; nur dieser eine Wert verlässt die .env (S15), siehe README.`);
  }
  return wert;
}

async function leseJson(pfad) {
  return JSON.parse(await readFile(pfad, "utf8"));
}

async function schreibeJson(pfad, wert) {
  await writeFile(pfad, `${JSON.stringify(wert, null, 2)}\n`);
}

async function ladeRun(workDir) {
  const pfad = join(workDir, RUN_FILE);
  if (!existsSync(pfad)) {
    throw new Error(`${pfad} fehlt. Zuerst \`prepare\` laufen lassen.`);
  }
  const run = parseRun(await readFile(pfad, "utf8"), pfad);
  assertMappingHash(run.mappingHash);
  return run;
}

function fotoIds(sample) {
  return sample.projects.flatMap((projekt) => projekt.photos.map((foto) => foto.photoId));
}

function zwecke(args) {
  return args.purpose ? [args.purpose] : PURPOSE_ORDER;
}

export function prepareZiel(workDir, { force = false, zeit = new Date().toISOString() } = {}) {
  if (!force) return workDir;
  return `${workDir}-lauf-${zeit.replace(/[:.]/g, "-")}`;
}

export async function prepare(args, workDir, deps = {}) {
  const { connect = connectReadOnly, query = runQuery, copy = copyFile } = deps;
  const ziel = prepareZiel(workDir, { force: args.force });
  if (existsSync(join(ziel, RUN_FILE))) {
    throw new Error(
      `${join(ziel, RUN_FILE)} existiert bereits. Ein zweites \`prepare\` würde Stichprobe, Analysen und Wahlen mischen; mit --force entsteht ein neues Arbeitsverzeichnis (${prepareZiel(workDir, { force: true })}).`,
    );
  }
  const projektePfad = join(workDir, INPUT_FILE);
  if (!existsSync(projektePfad)) {
    throw new Error(
      `${projektePfad} fehlt. Dort stehen die Projekt-Ids mit ihrer Art, z. B. [{"projectId": 3, "kind": "familie"}, {"projectId": 5, "kind": "reise"}] — die Datenbank kennt keine Projektart, und zwei gleiche Arten brechen ab.`,
    );
  }
  const projekte = await leseJson(projektePfad);
  const cacheVerzeichnis = args.photoCache ?? process.env.EYE_EVAL_PHOTO_CACHE_DIR;
  if (typeof cacheVerzeichnis !== "string" || cacheVerzeichnis.trim() === "") {
    throw new Error(
      "Bildcache fehlt: --photo-cache übergeben oder EYE_EVAL_PHOTO_CACHE_DIR setzen (im Container /cache).",
    );
  }
  const dsn = args.databaseUrl ?? umgebung("EYE_EVAL_DATABASE_URL");

  await mkdir(join(ziel, IMAGES_DIR), { recursive: true });
  const client = await connect(dsn);
  try {
    const [kandidatenAbfrage, laeufeAbfrage, kriteriumAbfrage] = queriesForProjects(
      projekte.map((projekt) => projekt.projectId),
    );
    const kandidaten = await query(client, kandidatenAbfrage);
    const laeufe = await query(client, laeufeAbfrage);
    const kriteriumLaeufe = await query(client, kriteriumAbfrage);

    const sample = selectSample({
      projects: projekte,
      candidates: kandidaten,
      cacheExists: cacheExistsIn(cacheVerzeichnis),
      perProject: args.perProject,
      seed: args.seed,
    });

    for (const projekt of sample.projects) {
      for (const foto of projekt.photos) {
        await copy(
          displayPath(cacheVerzeichnis, foto.photoId, foto.etag),
          join(ziel, IMAGES_DIR, `${foto.photoId}.jpg`),
        );
      }
    }

    const ids = fotoIds(sample);
    const roh = {};
    for (const abfrage of queriesForPhotos(ids)) {
      roh[abfrage.name] = await query(client, abfrage);
    }
    const baseline = assembleBaseline({
      photoIds: ids,
      motifStrengths: roh.motifStrengths,
      assessments: roh.assessments,
      albumSuitability: roh.albumSuitability,
      fineLabels: roh.fineLabels,
      landmarks: roh.landmarks,
      criterionScores: roh.criterionScores,
      remoteRuns: laeufe,
      criterionRuns: kriteriumLaeufe,
    });

    await schreibeJson(join(ziel, RUN_FILE), {
      version: 1,
      seed: args.seed,
      mappingHash: EYE_PURPOSE_MAPPING_HASH,
      createdAt: new Date().toISOString(),
      projects: projekte,
      sample,
      baseline,
    });

    console.log(`Projekte: ${sample.counts.projects}`);
    console.log(`Fotos in der Stichprobe: ${sample.counts.photos}`);
    console.log(`Ohne stimmigen Cache: ${sample.counts.inconsistent}`);
    for (const projekt of sample.projects) {
      console.log(
        `Projekt ${projekt.projectId} (${projekt.kind}): ${projekt.counts.selected} von ${projekt.counts.eligible}`,
      );
    }
    console.log(`Arbeitsverzeichnis: ${ziel}`);
  } finally {
    await client.end();
  }
}

async function analyze(args, workDir) {
  const run = await ladeRun(workDir);
  assertLicenseEnvironment();
  const modellVerzeichnis = args.modelDir ?? join(workDir, "models");
  await mkdir(join(workDir, ANALYSIS_DIR), { recursive: true });

  const { eye, pins } = await openModel({ directory: modellVerzeichnis });
  const ids = fotoIds(run.sample);
  const zeiten = [];
  try {
    for (const [index, id] of ids.entries()) {
      const start = process.hrtime.bigint();
      const analysis = await analyzeDisplayFile(eye, join(workDir, IMAGES_DIR, `${id}.jpg`));
      zeiten.push(Number(process.hrtime.bigint() - start) / 1e6);
      await schreibeJson(join(workDir, ANALYSIS_DIR, `${id}.json`), analysis);
      process.stderr.write(`\rAnalysiert: ${index + 1} von ${ids.length}`);
    }
    process.stderr.write("\n");
    await eye.flushTelemetry();
  } finally {
    eye.dispose();
  }

  const summe = zeiten.reduce((gesamt, wert) => gesamt + wert, 0);
  const mittel = Math.round(summe / Math.max(1, zeiten.length));
  await schreibeJson(join(workDir, RUNTIME_FILE), {
    photos: ids.length,
    totalMs: Math.round(summe),
    meanMs: mittel,
    model: `eye@${pins.revision ?? "unbekannt"}`,
    pins: { revision: pins.revision, commit: pins.commit, files: pins.checked },
  });

  console.log(`Analysierte Fotos: ${ids.length}`);
  console.log(`Mittlere Dauer je Foto: ${mittel} ms`);
  console.log(`Modellrevision: ${pins.revision ?? "unbekannt"}`);
}

async function ladeAnalysen(workDir) {
  const verzeichnis = join(workDir, ANALYSIS_DIR);
  if (!existsSync(verzeichnis)) return {};
  const analysen = {};
  for (const datei of await readdir(verzeichnis)) {
    if (!datei.endsWith(".json")) continue;
    analysen[Number(datei.replace(/\.json$/, ""))] = await leseJson(join(verzeichnis, datei));
  }
  return analysen;
}

function ladeEntscheidungen(run, workDir) {
  const pfad = join(workDir, DECISIONS_FILE);
  if (!existsSync(pfad)) {
    return { state: createState({ seed: run.seed, purposes: PURPOSE_ORDER }), pfad };
  }
  return {
    state: loadState(pfad, { seed: run.seed, purposes: PURPOSE_ORDER, resume: true }),
    pfad,
  };
}

function startIndex(state, purpose, laenge) {
  if (laenge === 0) return 0;
  return Math.min(state?.purposes?.[purpose]?.index ?? 0, laenge - 1);
}

async function pages(args, workDir) {
  const run = await ladeRun(workDir);
  const { items, missing } = buildItems({
    sample: run.sample,
    baseline: run.baseline,
    analyses: await ladeAnalysen(workDir),
  });
  const { state } = ladeEntscheidungen(run, workDir);
  const abbildung = { mappingHash: run.mappingHash, seed: run.seed, purposes: {} };

  for (const purpose of zwecke(args)) {
    const liste = items[purpose] ?? [];
    if (liste.length === 0) {
      console.log(`${purpose}: keine Paare (fehlende Analyse oder Basis)`);
      continue;
    }
    const { html, assignments } = renderComparisonPage({
      purpose,
      purposeLabel: EYE_PURPOSE_MAPPING.purposes[purpose].label,
      seed: run.seed,
      items: liste,
      startIndex: startIndex(state, purpose, liste.length),
    });
    abbildung.purposes[purpose] = assignments;
    await writeFile(join(workDir, `page-${purpose}.html`), html);
    console.log(`${purpose}: ${liste.length} Paare`);
  }

  await schreibeJson(join(workDir, AB_MAP_FILE), abbildung);
  console.log(`Ohne Analyse: ${missing.withoutAnalysis}`);
}

function indexSeite() {
  const links = PURPOSE_ORDER.map(
    (purpose) =>
      `<li><a href="page-${purpose}.html">${EYE_PURPOSE_MAPPING.purposes[purpose].label}</a></li>`,
  ).join("\n");
  return `<!doctype html>
<html lang="de"><head><meta charset="utf-8"><title>Vergleich</title>
<style>body{font:16px/1.5 system-ui,sans-serif;background:#121212;color:#f2f2f2;margin:24px}
a{color:#8ab4f8;display:inline-block;min-height:44px;line-height:44px}</style></head>
<body><h1>Vergleich je Zweck</h1><ul>${links}</ul></body></html>`;
}

async function serve(args, workDir) {
  const run = await ladeRun(workDir);
  const { state, pfad } = ladeEntscheidungen(run, workDir);
  let aktuell = state;
  await pages({ ...args, purpose: undefined }, workDir);

  const server = createServer(async (req, res) => {
    const url = new URL(req.url, "http://127.0.0.1");

    if (req.method === "POST" && url.pathname === "/decisions") {
      let roh = "";
      for await (const stueck of req) {
        roh += stueck;
        if (roh.length > 4096) {
          res.writeHead(413).end();
          return;
        }
      }
      try {
        const daten = JSON.parse(roh);
        if (!PURPOSE_ORDER.includes(daten.purpose)) {
          throw new DecisionStoreError("Unbekannter Zweck.");
        }
        aktuell = daten.skip
          ? recordSkip(aktuell, { purpose: daten.purpose, index: daten.index })
          : recordChoice(aktuell, {
              purpose: daten.purpose,
              photoId: daten.photoId,
              choice: daten.choice,
              index: daten.index,
            });
        saveState(pfad, aktuell);
        res.writeHead(204).end();
      } catch (problem) {
        res.writeHead(400, { "content-type": "text/plain; charset=utf-8" });
        res.end(problem.message);
      }
      return;
    }

    if (req.method !== "GET") {
      res.writeHead(405).end();
      return;
    }
    if (url.pathname === "/" || url.pathname === "/index.html") {
      res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
      res.end(indexSeite());
      return;
    }
    if (!STATISCH.test(url.pathname)) {
      res.writeHead(404).end();
      return;
    }
    try {
      const inhalt = await readFile(join(workDir, url.pathname.replace(/^\//, "")));
      res.writeHead(200, {
        "content-type": url.pathname.endsWith(".html") ? "text/html; charset=utf-8" : "image/jpeg",
      });
      res.end(inhalt);
    } catch {
      res.writeHead(404).end();
    }
  });

  await new Promise((fertig) => server.listen(args.port, "127.0.0.1", fertig));
  const adresse = server.address();
  console.log(`Vergleichsseite: http://127.0.0.1:${adresse.port}/`);
  console.log(`Entscheidungsdatei: ${pfad}`);
  console.log("Beenden mit Strg+C. Kein Port nach außen (S12).");

  await new Promise((fertig) => {
    const beenden = () => server.close(() => fertig());
    process.once("SIGINT", beenden);
    process.once("SIGTERM", beenden);
  });
  console.log("Server beendet.");
}

async function summary(args, workDir) {
  const run = await ladeRun(workDir);
  const { items } = buildItems({
    sample: run.sample,
    baseline: run.baseline,
    analyses: await ladeAnalysen(workDir),
  });
  const pfad = join(workDir, DECISIONS_FILE);
  if (!existsSync(pfad)) {
    throw new Error(`${pfad} fehlt. Erst vergleichen (\`serve\`), dann zusammenfassen.`);
  }
  const state = loadState(pfad, { seed: run.seed, purposes: PURPOSE_ORDER, resume: true });
  const abPfad = join(workDir, AB_MAP_FILE);
  if (!existsSync(abPfad)) {
    throw new Error(
      `${abPfad} fehlt. Erst \`pages\` laufen lassen: ohne die A/B-Zuordnung sind die Stimmen nicht deutbar.`,
    );
  }
  const abbildung = ladeAbMap(await readFile(abPfad, "utf8"), abPfad);
  const aufrufe = countCalls(run.baseline.runs);

  const summaries = [];
  const zweckUrteile = {};
  for (const purpose of PURPOSE_ORDER) {
    const roh = countChoices(state, purpose);
    const gemappt = mapVotes({
      choices: state.purposes[purpose].choices,
      assignments: abbildung.purposes[purpose] ?? [],
    });
    const gesamt = items[purpose]?.length ?? 0;
    const uebersprungen = Math.max(0, gesamt - roh.decided);
    zweckUrteile[purpose] = {
      better: gemappt.better,
      same: gemappt.same,
      worse: gemappt.worse,
      skipped: uebersprungen,
      total: gesamt,
    };
    summaries.push({
      purpose,
      label: EYE_PURPOSE_MAPPING.purposes[purpose].label,
      counts: { better: roh.a, same: roh.same, worse: roh.b, skipped: uebersprungen, total: gesamt },
    });
  }

  const ersparnis = computeSavings({
    categories: {
      photosWithCall: aufrufe.category,
      photosWithoutCall: 0,
      purposes: {
        motivstaerken: zweckUrteile.motivstaerken,
        ausschluss: zweckUrteile.ausschluss,
        albumtauglichkeit: zweckUrteile.albumtauglichkeit,
        feinlabels: zweckUrteile.feinlabels,
      },
    },
    landmark: { candidates: aufrufe.landmark, verdicts: zweckUrteile.sehenswuerdigkeit },
  });

  await schreibeJson(join(workDir, SUMMARY_FILE), {
    createdAt: new Date().toISOString(),
    mappingHash: run.mappingHash,
    seed: run.seed,
    purposes: zweckUrteile,
    calls: {
      category: aufrufe.category,
      landmark: aufrufe.landmark,
      source: aufrufe.categorySource,
      fallbackProjects: aufrufe.fallbackProjects,
    },
    savings: ersparnis,
    models: run.baseline.runs.models,
    baseline: { counts: run.baseline.counts },
  });
  await writeFile(join(workDir, "abschluss.html"), renderCompletionPage({ summaries }));

  for (const zeile of summaries) {
    const { counts } = zeile;
    console.log(
      `${zeile.label}: A ${counts.better}, gleich ${counts.same}, B ${counts.worse}, übersprungen ${counts.skipped}, gesamt ${counts.total}`,
    );
  }
  console.log(
    `Kategorie-Aufrufe gespart: ${ersparnis.categoryCallsSaved} (${ersparnis.replacedCategoryPurposes}/4 Zwecke ersetzt)`,
  );
  console.log(`Landmark-Aufrufe gespart: ${ersparnis.landmarkCallsSaved}`);
  console.log(ersparnis.note);
  console.log(`Abschlussseite: ${join(workDir, "abschluss.html")}`);
}

async function reportCheck(args, workDir) {
  const namenPfad = join(workDir, NAMES_FILE);
  const namen = existsSync(namenPfad) ? await leseJson(namenPfad) : { projects: [], landmarks: [] };
  const markdown = await readFile(args.positional[0], "utf8");
  const ergebnis = checkReport(markdown, {
    projectNames: namen.projects ?? [],
    landmarkNames: namen.landmarks ?? [],
  });

  await writeFile(
    join(workDir, "report-check.txt"),
    `${formatFindings(ergebnis)}\n\nFundstellen (nur lokal):\n${ergebnis.findings
      .map((befund) => `Zeile ${befund.line}: ${befund.excerpt}`)
      .join("\n")}\n`,
  );
  console.log(formatFindings(ergebnis));
  console.log(
    namen.projects?.length || namen.landmarks?.length
      ? "Projekt- und Ortsnamen wurden gegen names.json geprüft."
      : "names.json fehlt: Projekt- und Ortsnamen wurden nicht geprüft (nur lokal anlegen).",
  );
  return ergebnis.ok ? 0 : 1;
}

export async function main(argv) {
  const args = parseArgs(argv);
  if (args.command === "help") {
    console.log(usage());
    return 0;
  }
  const workDir = resolveWorkDir({
    workDir: args.workDir,
    repoRoot: REPO_ROOT,
    toolRoot: TOOL_ROOT,
    istCheckout: IST_CHECKOUT,
  });

  switch (args.command) {
    case "prepare":
      await prepare(args, workDir);
      return 0;
    case "analyze":
      await analyze(args, workDir);
      return 0;
    case "pages":
      await pages(args, workDir);
      return 0;
    case "serve":
      await serve(args, workDir);
      return 0;
    case "summary":
      await summary(args, workDir);
      return 0;
    case "report-check":
      return reportCheck(args, workDir);
    default:
      throw new ArgsError(`Unbekannter Befehl „${args.command}“.`);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.argv.slice(2))
    .then((code) => process.exit(code))
    .catch((problem) => {
      console.error(problem instanceof Error ? problem.message : String(problem));
      process.exit(1);
    });
}
