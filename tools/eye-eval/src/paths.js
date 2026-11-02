import { homedir } from "node:os";
import { isAbsolute, join, relative as relativ, resolve } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Der Arbeitsbereich liegt außerhalb des Repositorys (S9): dort entstehen Seiten, Bildkopien,
 * Analysen und Entscheidungen — alles, was nie in einen Commit geraten darf. Ein Pfad im
 * Repository ist deshalb kein Warnfall, sondern ein Abbruch.
 */
export class WorkDirError extends Error {
  constructor(message) {
    super(message);
    this.name = "WorkDirError";
  }
}

export function toolRootFromModule(importMetaUrl) {
  return resolve(fileURLToPath(new URL("..", importMetaUrl)));
}

export function repoRootFromModule(importMetaUrl) {
  return resolve(toolRootFromModule(importMetaUrl), "../..");
}

export function assertOutsideRepo(pfad, repoRoot) {
  const repo = resolve(repoRoot);
  const ziel = resolve(pfad);
  const abstand = relativ(repo, ziel);
  if (abstand === "" || (!abstand.startsWith("..") && !isAbsolute(abstand))) {
    throw new WorkDirError(
      `Das Arbeitsverzeichnis ${ziel} liegt im Repository (${repo}). Es muss außerhalb des Repositorys liegen (S9); Standard ist ~/photosort-eye-eval.`,
    );
  }
  return ziel;
}

export function resolveWorkDir({ workDir, home = homedir(), repoRoot }) {
  const roh =
    typeof workDir === "string" && workDir.trim() !== ""
      ? workDir.trim()
      : join(home, "photosort-eye-eval");
  const aufgeloest = roh.startsWith("~/") ? join(home, roh.slice(2)) : roh;
  const absolut = isAbsolute(aufgeloest) ? aufgeloest : resolve(aufgeloest);
  return assertOutsideRepo(absolut, repoRoot);
}
