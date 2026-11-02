import assert from "node:assert/strict";
import { test } from "node:test";

import { ArgsError, COMMANDS, parseArgs } from "../src/args.js";
import { DEFAULT_SAMPLE_SEED } from "../src/sample.js";

test("ohne Argumente gibt es Hilfe", () => {
  const args = parseArgs([]);
  assert.equal(args.command, "help");
  assert.equal(args.seed, DEFAULT_SAMPLE_SEED);
  assert.equal(args.perProject, 100);
  assert.equal(args.port, 0);
  assert.equal(args.resume, false);
});

test("jeder Befehl wird erkannt", () => {
  for (const befehl of COMMANDS) {
    if (befehl === "help" || befehl === "report-check") continue;
    assert.equal(parseArgs([befehl]).command, befehl);
  }
});

test("Optionen in beiden Schreibweisen", () => {
  const args = parseArgs([
    "prepare",
    "--work-dir=/tmp/eye",
    "--database-url",
    "postgresql://x",
    "--photo-cache=/mnt/cache",
    "--per-project",
    "120",
    "--seed",
    "7",
    "--resume",
  ]);

  assert.equal(args.workDir, "/tmp/eye");
  assert.equal(args.databaseUrl, "postgresql://x");
  assert.equal(args.photoCache, "/mnt/cache");
  assert.equal(args.perProject, 120);
  assert.equal(args.seed, 7);
  assert.equal(args.resume, true);
});

test("report-check nimmt die Datei als Positionsargument", () => {
  const args = parseArgs(["report-check", "ergebnis.md"]);
  assert.equal(args.command, "report-check");
  assert.deepEqual(args.positional, ["ergebnis.md"]);
});

test("unbekannte Option und fehlender Wert brechen ab", () => {
  assert.throws(() => parseArgs(["prepare", "--zauber"]), ArgsError);
  assert.throws(() => parseArgs(["prepare", "--seed"]), /fehlt/);
  assert.throws(() => parseArgs(["prepare", "--seed", "viele"]), /Zahl/);
  assert.throws(() => parseArgs(["prepare", "--port", "70000"]), /Port/);
  assert.throws(() => parseArgs(["tanzen"]), /Unbekannter Befehl/);
});

test("--purpose muss ein bekannter Zweck sein", () => {
  assert.equal(parseArgs(["pages", "--purpose", "ausschluss"]).purpose, "ausschluss");
  assert.throws(() => parseArgs(["pages", "--purpose", "alles"]), /Zweck/);
});
