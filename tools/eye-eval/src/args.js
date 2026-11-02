import { DEFAULT_SAMPLE_SEED, MIN_PHOTOS_PER_PROJECT } from "./sample.js";
import { PURPOSE_ORDER } from "./compare.js";

/**
 * Befehle und Schalter werden hier geprüft, bevor irgendetwas eine Datenbank oder ein SDK
 * berührt: ein Tippfehler soll eine Meldung geben und keinen halben Lauf starten.
 */
export class ArgsError extends Error {
  constructor(message) {
    super(message);
    this.name = "ArgsError";
  }
}

export const COMMANDS = ["prepare", "analyze", "pages", "serve", "summary", "report-check", "help"];

const MIT_WERT = {
  "--work-dir": "workDir",
  "--database-url": "databaseUrl",
  "--photo-cache": "photoCache",
  "--model-dir": "modelDir",
  "--seed": "seed",
  "--per-project": "perProject",
  "--purpose": "purpose",
  "--port": "port",
};

function zahl(wert, name) {
  const geprueft = Number(wert);
  if (!Number.isInteger(geprueft) || geprueft < 0) {
    throw new ArgsError(`${name} muss eine ganze Zahl sein, war „${wert}“.`);
  }
  return geprueft;
}

export function parseArgs(argv = []) {
  const args = {
    command: "help",
    positional: [],
    workDir: undefined,
    databaseUrl: undefined,
    photoCache: undefined,
    modelDir: undefined,
    seed: DEFAULT_SAMPLE_SEED,
    perProject: MIN_PHOTOS_PER_PROJECT,
    purpose: undefined,
    port: 0,
    resume: false,
  };

  const rest = [...argv];
  if (rest.length > 0 && !rest[0].startsWith("-")) {
    const befehl = rest.shift();
    if (!COMMANDS.includes(befehl)) {
      throw new ArgsError(`Unbekannter Befehl „${befehl}“; erlaubt sind ${COMMANDS.join(", ")}.`);
    }
    args.command = befehl;
  }

  while (rest.length > 0) {
    const roh = rest.shift();
    if (roh === "--help" || roh === "-h") {
      args.command = "help";
      continue;
    }
    if (roh === "--resume") {
      args.resume = true;
      continue;
    }
    if (!roh.startsWith("--")) {
      args.positional.push(roh);
      continue;
    }

    const [name, angehaengt] = roh.includes("=") ? roh.split(/=(.*)/s, 2) : [roh, undefined];
    const feld = MIT_WERT[name];
    if (!feld) throw new ArgsError(`Unbekannte Option „${name}“.`);
    const wert = angehaengt ?? rest.shift();
    if (wert === undefined) throw new ArgsError(`Option „${name}“ fehlt ein Wert.`);
    args[feld] = wert;
  }

  args.seed = zahl(args.seed, "Die Saat");
  args.perProject = zahl(args.perProject, "Die Fotozahl je Projekt");
  args.port = zahl(args.port, "Der Port");
  if (args.port > 65535) throw new ArgsError(`Der Port ${args.port} liegt außerhalb von 1–65535.`);
  if (args.perProject < MIN_PHOTOS_PER_PROJECT) {
    throw new ArgsError(
      `Mindestens ${MIN_PHOTOS_PER_PROJECT} Fotos je Projekt; ${args.perProject} verkleinert die Stichprobe still.`,
    );
  }
  if (args.purpose !== undefined && !PURPOSE_ORDER.includes(args.purpose)) {
    throw new ArgsError(`Unbekannter Zweck „${args.purpose}“; erlaubt sind ${PURPOSE_ORDER.join(", ")}.`);
  }
  if (args.command === "report-check" && args.positional.length !== 1) {
    throw new ArgsError("report-check braucht genau einen Pfad zur Markdown-Datei.");
  }

  return args;
}

export function usage() {
  return `Aufruf: node src/cli.js <Befehl> [Optionen]

Befehle:
  prepare       Stichprobe und Basis aus der Datenbank, Bildkopien in den Arbeitsbereich
  analyze       Gewichte prüfen und die Stichprobe durch das Modell schicken
  pages         Vergleichsseiten je Zweck bauen (nach analyze)
  serve         Lokaler Server für die Wahlen (127.0.0.1, nicht 0.0.0.0)
  summary       Zählungen, Ersparnis und Abschlussseite
  report-check  Markdown-Bericht gegen S6–S11 prüfen

Optionen:
  --work-dir <pfad>        Arbeitsverzeichnis außerhalb des Repositorys (Standard ~/photosort-eye-eval)
  --database-url <url>     Read-only-Verbindung; sonst EYE_EVAL_DATABASE_URL
  --photo-cache <pfad>     photo_cache, schreibgeschützt eingebunden; sonst EYE_EVAL_PHOTO_CACHE_DIR
  --model-dir <pfad>       Gewichte mit pins.json (Standard <work-dir>/models)
  --seed <zahl>            Saat der Stichprobe und der A/B-Zuordnung
  --per-project <zahl>     Fotos je Projekt, mindestens ${MIN_PHOTOS_PER_PROJECT}
  --purpose <zweck>        Nur ein Durchlauf; sonst alle fünf
  --port <zahl>            Port für serve (Standard 0 = freier Port)
  --resume                 An einer vorhandenen Entscheidungsdatei fortsetzen
  --help                   Diese Übersicht`;
}
