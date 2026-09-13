# 0096 - Die erste Hauptversion ist eine Produktentscheidung, kein Commit-Suffix

**Status:** Accepted
**Datum:** 2026-09-13
**Bezug:** [GitHub-Issue #459](https://github.com/TheRealKoller/photosort/issues/459), Spec 0459

Revidiert einen Teil von ADR [`0008`](./0008-automated-semver-releases.md): den dort gesetzten
Wert `bump-minor-pre-major: false`. Alle übrigen Entscheidungen aus ADR 0008 (Tooling,
`release-type: simple`, Manifest als Source of Truth, `extra-files`, SHA-Pinning, PAT, Trigger)
bleiben unverändert.

## Kontext

ADR 0008 setzt `bump-minor-pre-major: false` und kommentiert den Wert mit „feat bumpt MINOR auch
< 1.0.0". Dieser Kommentar beschreibt das Flag falsch. Das offizielle Konfigurationsschema von
release-please sagt wörtlich:

> `bump-minor-pre-major` — Breaking changes only bump semver minor if version < 1.0.0
> `bump-patch-for-minor-pre-major` — Feature changes only bump semver patch if version < 1.0.0

Das erste Flag steuert ausschließlich das Verhalten bei **Breaking Changes**, nicht das bei
`feat:`. Auf `false` entfällt die Schonung: Ein Breaking Change bumpt die Major-Version auch
unterhalb von 1.0. Die in ADR 0008 gemeinte Wirkung („feat bumpt MINOR, fix bumpt PATCH, auch vor
1.0") kommt allein von `bump-patch-for-minor-pre-major: false` und ist von dieser Entscheidung
nicht betroffen.

Der Fall wurde am 2026-09-12 real: Der Merge von PR #450 (`feat!: …`) zog die Version von 0.43.0
auf 1.0.0 und erzeugte Tag und GitHub-Release `v1.0.0`.

## Entscheidung

`bump-minor-pre-major` wird auf `true` gesetzt. Unterhalb von 1.0.0 erzeugt ein Breaking Change
damit einen MINOR-Bump.

**Die erste Hauptversion wird von Hand ausgelöst, nicht von einem Commit.** Version 1.0.0
entsteht in diesem Repository ausschließlich dadurch, dass Daniel den Wert wieder auf `false`
setzt und der nächste Breaking Change den Sprung auslöst — oder dadurch, dass er das Manifest
unmittelbar auf `1.0.0` hebt. Solange der Wert auf `true` steht, gibt es keinen Commit-Inhalt und
kein Commit-Suffix, das die Projektversion über 0.x hinaustragen kann. Verletzt eine Änderung
diese Zusage — etwa indem sie den Wert ohne Daniels Entscheidung zurückstellt —, vergibt der
nächste Release-Lauf eine Versionsnummer, die nach außen eine Reife behauptet, die das Projekt
nicht erklärt hat; zurücknehmbar ist das nur über das Löschen von Tag und Release.

Kein Wächtertest nagelt den Wert fest. Er ist ein bewusst umzustellender Schalter, und ein Test,
der ihn auf `true` festschreibt, stünde genau bei der Umstellung im Weg, für die er gedacht wäre.

## Konsequenzen

- Ein `feat!:` erzeugt vor 1.0.0 denselben Bump wie ein `feat:`. Die Kennzeichnung bleibt im
  Changelog sichtbar (Abschnitt „⚠ BREAKING CHANGES"), wirkt aber nicht mehr auf die Nummer.
- Der bereits erzeugte Stand `v1.0.0` wird zurückgenommen (Tag, GitHub-Release, Manifest,
  Changelog-Abschnitt, Frontend-Paketdateien), damit die Zählung ab `v0.43.0` fortsetzt. Das
  Löschen eines GitHub-Release ist nicht umkehrbar; der Inhalt bleibt über `CHANGELOG.md`
  rekonstruierbar.
- Ein bereits andernorts gezogener Tag `v1.0.0` verschwindet durch das Löschen auf GitHub nicht
  aus fremden Arbeitskopien.
- Der irreführende Kommentar in ADR 0008 wird an Ort und Stelle richtiggestellt, damit die
  falsche Beschreibung nicht weiterwirkt.
