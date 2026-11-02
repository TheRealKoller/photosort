import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { test } from "node:test";

import {
  WorkDirError,
  assertOutsideRepo,
  repoRootFromModule,
  resolveWorkDir,
  toolRootFromModule,
} from "../src/paths.js";

const REPO = resolve("/home/thekoller/projekte/photosort");

test("das Arbeitsverzeichnis liegt standardmäßig unter $HOME", () => {
  const pfad = resolveWorkDir({ home: "/home/daniel", repoRoot: REPO });
  assert.equal(pfad, "/home/daniel/photosort-eye-eval");
});

test("~ wird aufgelöst", () => {
  assert.equal(
    resolveWorkDir({ workDir: "~/eye", home: "/home/daniel", repoRoot: REPO }),
    "/home/daniel/eye",
  );
});

test("ein Pfad im Repository bricht ab", () => {
  assert.throws(
    () => resolveWorkDir({ workDir: join(REPO, "tmp"), home: "/home/daniel", repoRoot: REPO }),
    (error) => {
      assert.ok(error instanceof WorkDirError);
      assert.match(error.message, /außerhalb des Repositorys/);
      return true;
    },
  );
  assert.throws(() => resolveWorkDir({ workDir: REPO, home: "/home/daniel", repoRoot: REPO }), WorkDirError);
});

test("ein gleichnamiger Nachbarpfad ist nicht das Repository", () => {
  const nachbar = `${REPO}-alt`;
  assert.equal(assertOutsideRepo(nachbar, REPO), nachbar);
});

test("der Repository-Pfad kommt aus dem Modulort", () => {
  const modul = new URL("../src/paths.js", import.meta.url).href;
  assert.equal(toolRootFromModule(modul).endsWith("/tools/eye-eval"), true);
  assert.equal(repoRootFromModule(modul), resolve(toolRootFromModule(modul), "../.."));
  assert.equal(repoRootFromModule(modul).endsWith("photosort"), true);
});

test("ein relatives Arbeitsverzeichnis wird absolut", () => {
  const verzeichnis = mkdtempSync(join(tmpdir(), "eye-eval-paths-"));
  try {
    mkdirSync(join(verzeichnis, "arbeit"));
    const vorher = process.cwd();
    process.chdir(verzeichnis);
    try {
      const pfad = resolveWorkDir({ workDir: "arbeit", home: "/home/daniel", repoRoot: REPO });
      assert.equal(pfad, join(verzeichnis, "arbeit"));
    } finally {
      process.chdir(vorher);
    }
  } finally {
    rmSync(verzeichnis, { recursive: true, force: true });
  }
});

test("im Checkout-Layout gilt weiter die Repository-Regel", () => {
  const repo = "/repo";
  const tool = "/repo/tools/eye-eval";
  assert.throws(
    () => resolveWorkDir({ workDir: "/repo/w", home: "/home/daniel", repoRoot: repo, toolRoot: tool, istCheckout: true }),
    (error) => {
      assert.ok(error instanceof WorkDirError);
      assert.match(error.message, /außerhalb des Repositorys/);
      return true;
    },
  );
  assert.equal(
    resolveWorkDir({ workDir: "/tmp/w", home: "/home/daniel", repoRoot: repo, toolRoot: tool, istCheckout: true }),
    "/tmp/w",
  );
});

test("im Kopie-Layout liegt das Arbeitsverzeichnis neben dem Werkzeugbaum", () => {
  const tool = "/app";
  const repo = "/";
  const optionen = { home: "/home/daniel", repoRoot: repo, toolRoot: tool, istCheckout: false };

  assert.equal(resolveWorkDir({ ...optionen, workDir: "/work" }), "/work");
  for (const verboten of ["/app/out", "/app", "/"]) {
    assert.throws(
      () => resolveWorkDir({ ...optionen, workDir: verboten }),
      (error) => {
        assert.ok(error instanceof WorkDirError);
        assert.match(error.message, new RegExp(verboten.replace(/^\/$/, "/")));
        assert.match(error.message, /Werkzeugbaum/);
        return true;
      },
      verboten,
    );
  }
});
