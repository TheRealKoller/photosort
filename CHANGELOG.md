# Changelog

## [0.13.0](https://github.com/TheRealKoller/photosort/compare/v0.12.0...v0.13.0) (2026-08-21)


### Features

* **github-project-sync:** natives Status-Feld statt Custom-Field, Inbox-Einbindung ([#173](https://github.com/TheRealKoller/photosort/issues/173)) ([fb09996](https://github.com/TheRealKoller/photosort/commit/fb09996dd1a3eaee2d26252ebccc86a8871bbcfe))
* **github-project-sync:** Zwei-Wege-Sync Feature-Specs ↔ GitHub-Projekt (Spec 0031) ([#115](https://github.com/TheRealKoller/photosort/issues/115)) ([c07414e](https://github.com/TheRealKoller/photosort/commit/c07414ea2bdcc9c9fb240fb7971a02703d015493))


### Bug Fixes

* **github-project-sync:** gh issue create liefert kein JSON, plus Status-Feld-Namenskollision ([#117](https://github.com/TheRealKoller/photosort/issues/117)) ([a04c4ce](https://github.com/TheRealKoller/photosort/commit/a04c4ced6b976da9ef531d812d1ad3880c6fe368))
* **github-project-sync:** Status-Extraktion auf Enum-Schluesselwort begrenzen, Lauf-Resilienz ([#120](https://github.com/TheRealKoller/photosort/issues/120)) ([6f9cd04](https://github.com/TheRealKoller/photosort/commit/6f9cd04e9bea783122d38b6d4052e84a0c27faaf))

## [0.12.0](https://github.com/TheRealKoller/photosort/compare/v0.11.0...v0.12.0) (2026-08-20)


### Features

* Automatisierter Flow als Stepper-Übersicht + Detailseiten (Spec 0042) ([#101](https://github.com/TheRealKoller/photosort/issues/101)) ([a8c8919](https://github.com/TheRealKoller/photosort/commit/a8c8919586fb7d88f194a5a3e4404c28560f9506))
* Bewertungsdetails permanent in Detailansicht + Hover-Auto-Close im Popover (Spec 0041) ([#103](https://github.com/TheRealKoller/photosort/issues/103)) ([871f012](https://github.com/TheRealKoller/photosort/commit/871f012810ee910195612b9c0d02f7d948354962))

## [0.11.0](https://github.com/TheRealKoller/photosort/compare/v0.10.0...v0.11.0) (2026-08-16)


### Features

* Kuratierungs-Tage einzeln und global auf-/zuklappbar ([#100](https://github.com/TheRealKoller/photosort/issues/100)) ([430d757](https://github.com/TheRealKoller/photosort/commit/430d757cef7d62b0a6ea12f84aea23ffe4257dcb))
* Sticky Titelleiste mit Projekt-Kontext-Link ([#99](https://github.com/TheRealKoller/photosort/issues/99)) ([d529a59](https://github.com/TheRealKoller/photosort/commit/d529a59fadc624add3246e77d3e8dba15072fd8c))


### Bug Fixes

* Scan-Statistik Grid-Layout und aufklappbarer Hilfetext ([#97](https://github.com/TheRealKoller/photosort/issues/97)) ([c4827a0](https://github.com/TheRealKoller/photosort/commit/c4827a08ff5ea173932aa140823ea280f2f2b916))

## [0.10.0](https://github.com/TheRealKoller/photosort/compare/v0.9.0...v0.10.0) (2026-08-15)


### Features

* Kuratierung nach Tagen gruppieren, Cluster mit Tageszeit-Ueberschrift ([3925595](https://github.com/TheRealKoller/photosort/commit/3925595ccc2baaab73357bccaab54994ffd94001))
* Kuratierung nach Tagen gruppieren, Cluster mit Tageszeit-Ueberschrift ([9436233](https://github.com/TheRealKoller/photosort/commit/9436233ee4faec4c234a823807d7ba5a72951456))
* timeOfDay-Utility fuer Tag-/Tageszeit-Ableitung aus taken_at ([b8586c7](https://github.com/TheRealKoller/photosort/commit/b8586c7980022c64d13ce37b3d6853b9bb816402))


### Bug Fixes

* Copilot-Review-Findings beheben (PR [#91](https://github.com/TheRealKoller/photosort/issues/91)) ([7ac84c2](https://github.com/TheRealKoller/photosort/commit/7ac84c29a420410057bd49875b61272db600a492))
* Review-Findings zu Spec 0039 beheben ([1bce61b](https://github.com/TheRealKoller/photosort/commit/1bce61bf44902e286c2ab2b1473ace652f9578e9))

## [0.9.0](https://github.com/TheRealKoller/photosort/compare/v0.8.0...v0.9.0) (2026-08-15)


### Features

* Aesthetik-Kriterium (NIMA/MobileNet ueber tensorflow) ([b57f776](https://github.com/TheRealKoller/photosort/commit/b57f7762a3f34eb7f7fba0eb56ca5d6e4b4584ce))
* Gebaeude-Kriterium (classify_scene, EfficientNet-Lite0) ([8006135](https://github.com/TheRealKoller/photosort/commit/8006135b115b1ce4e151bab1fb8ceaa3ae3ea810))
* Goldener-Schnitt-Kriterium (compute_golden_ratio_score) ([995f082](https://github.com/TheRealKoller/photosort/commit/995f0822934d58bf878b3414e209d201b0ebc023))
* Tier-Kriterium (detect_animals, EfficientDet-Lite0) + Goldener-Schnitt-Verdrahtung ([dbecb44](https://github.com/TheRealKoller/photosort/commit/dbecb442401557edab6ac7a10603b96984f7b448))
* Vier zusätzliche Kriterien (Tier, Gebäude, Goldener Schnitt, Ästhetik) ([5e1490f](https://github.com/TheRealKoller/photosort/commit/5e1490f5b7acfd937a16e703a6dd3d065646637b))


### Bug Fixes

* Copilot-Review-Findings beheben (PR [#88](https://github.com/TheRealKoller/photosort/issues/88)) ([95f3ed6](https://github.com/TheRealKoller/photosort/commit/95f3ed609351cb7a536f5069e40d08cbd86ff292))

## [0.8.0](https://github.com/TheRealKoller/photosort/compare/v0.7.0...v0.8.0) (2026-08-15)


### Features

* **api:** criterion_scores und RankingOut.partition_size exponieren ([260672b](https://github.com/TheRealKoller/photosort/commit/260672bf7b79b3fa1ad12a77e2df93c9dbeb15bd))
* **frontend:** api/types.ts um CriterionScoreOut/partition_size erweitern ([79f2cfd](https://github.com/TheRealKoller/photosort/commit/79f2cfd3e4add0bdbb8f12f8c5a9675b343fb7b5))
* **frontend:** CriterionDetailsPopover-Komponente ([3b33e1b](https://github.com/TheRealKoller/photosort/commit/3b33e1b628a93c8deed86e3695a801b34a83951f))
* **frontend:** duennen Radix-Popover-Wrapper ui/popover.tsx ergaenzen ([ddc14fe](https://github.com/TheRealKoller/photosort/commit/ddc14fe8a61beeef5a11cb2e37bdacd301ab8999))
* **frontend:** Info-Popover in CurateCategoriesPage.tsx einbinden ([80e6848](https://github.com/TheRealKoller/photosort/commit/80e68489aab53361dde5289c6052adda4a28ef88))
* **frontend:** Info-Popover in PhotoDetailPage.tsx einbinden ([d539549](https://github.com/TheRealKoller/photosort/commit/d539549f6e957ca0cc13e0ca71b263e7c129e5ae))
* **frontend:** Info-Popover in PhotoGridPage.tsx einbinden ([50f77a6](https://github.com/TheRealKoller/photosort/commit/50f77a6e6061e61344b412c2694bc31d2125c974))


### Bug Fixes

* **frontend:** pointer-events-none auf dem Badge-Overlay, damit die Kachel klickbar bleibt ([5c44016](https://github.com/TheRealKoller/photosort/commit/5c440163090d0a0f6c04f846d20eb046ef7b368b))
* Review-Findings der Runde 0040 beheben ([912e560](https://github.com/TheRealKoller/photosort/commit/912e560df715acd3c53fcd5651669ce60d2fe96c))

## [0.7.0](https://github.com/TheRealKoller/photosort/compare/v0.6.1...v0.7.0) (2026-08-15)


### Features

* frontend anpassung an gateführte pipeline (spec 0037, teil 3/4) ([587d9f2](https://github.com/TheRealKoller/photosort/commit/587d9f2ce1c802c8064ae4ba652bc20d7d5d0bfc))
* gateführte Bewertungs-Pipeline mit Kriterien-Scoring und Kategorie-Kuratierung ([770ea9e](https://github.com/TheRealKoller/photosort/commit/770ea9e0865ce2ed4d10fca72a10fa84903a84f3))
* kategorie-kuratierungs-ansicht /curate mit backfill (spec 0037, teil 4/4) ([495eb67](https://github.com/TheRealKoller/photosort/commit/495eb6716f4ccead8a4afe744828ec5e2f65488e))
* kriterien-datenmodell und rangfolgen-pipeline (spec 0037, teil 1/3) ([2b952ae](https://github.com/TheRealKoller/photosort/commit/2b952ae374040bc2cef5c456764d789d4c9ffe05))


### Bug Fixes

* review-findings aus schritt 4 beheben (spec 0037) ([024d98d](https://github.com/TheRealKoller/photosort/commit/024d98d73a47468d9d921e7784798cd1d1079853))
* stale ALBUM_WORTHY-Vorschläge in Migration bereinigen (Copilot-Review PR [#80](https://github.com/TheRealKoller/photosort/issues/80)) ([e55b83a](https://github.com/TheRealKoller/photosort/commit/e55b83ad5a3d2fbee32216cc137ee0839ea6c0cf))

## [0.6.1](https://github.com/TheRealKoller/photosort/compare/v0.6.0...v0.6.1) (2026-08-14)


### Bug Fixes

* also install libgles2 for mediapipe FaceDetector ([850a431](https://github.com/TheRealKoller/photosort/commit/850a431c73b5bbe9e8a8d7d2ec65685b7124c9ee))
* install libegl1 for mediapipe FaceDetector in CI and Docker image ([8c806b8](https://github.com/TheRealKoller/photosort/commit/8c806b8ef1b5f8d68f45335ac4c9735043aec382))
* libegl1 fehlt für mediapipe FaceDetector in CI/Docker ([5911f9f](https://github.com/TheRealKoller/photosort/commit/5911f9f8f8409f3b6cd218c295a9f4d2d085c1bd))

## [0.6.0](https://github.com/TheRealKoller/photosort/compare/v0.5.0...v0.6.0) (2026-08-13)


### Features

* reine Phase-2a-Klassifikationsfunktion fuer den Scan extrahieren ([fdfb3f5](https://github.com/TheRealKoller/photosort/commit/fdfb3f518dc1a06e20bcd2dd1e87440ffb5c1154))
* scan_download_concurrency-Einstellung hinzufuegen ([70dc2ff](https://github.com/TheRealKoller/photosort/commit/70dc2ff66b36a5ef1522497f795845462b01ef4e))
* Scan-Performance — Enumerationsphase, begrenzte Parallelisierung, echter Prozent-Fortschritt (Spec 0036) ([294295c](https://github.com/TheRealKoller/photosort/commit/294295c65096eadfd840c7eb6c239e4c1b579ad7))
* Scan-Worker auf Zwei-Phasen-Ablauf mit begrenzter Parallelisierung umstellen ([6953490](https://github.com/TheRealKoller/photosort/commit/69534905ada3e3f8a7a77912153c3152fb303f62))
* ScanRun.total_files-Spalte fuer Spec 0036 hinzufuegen ([ca087eb](https://github.com/TheRealKoller/photosort/commit/ca087ebb6e18dd8d99c87f70cce9a316b14ea758))
* ScanSummary.total_files in der Projekt-API exponieren ([c2ee684](https://github.com/TheRealKoller/photosort/commit/c2ee6844fcd653e4b4423a044531b67525531c02))
* zweiphasigen Scan-Fortschritt im Frontend anzeigen ([e841d74](https://github.com/TheRealKoller/photosort/commit/e841d746687c33a9594d57474d8ace0db4e516d4))


### Bug Fixes

* Review-Findings aus Schritt 4 beheben (Spec 0036) ([b99f16c](https://github.com/TheRealKoller/photosort/commit/b99f16ce2f17ad7055456494fa137717ebf014ed))

## [0.5.0](https://github.com/TheRealKoller/photosort/compare/v0.4.0...v0.5.0) (2026-08-09)


### Features

* arq-Registrierung mit grosszuegigem Not-Anker + deaktiviertem Retry (Spec 0034, Schritt 4) ([775b292](https://github.com/TheRealKoller/photosort/commit/775b292c869426808dc9a3d59f6ae4eff796c3fc))
* last_progress_at Pflege an bestehenden Checkpoint-Stellen (Spec 0034, Schritt 3) ([e250108](https://github.com/TheRealKoller/photosort/commit/e2501081096d8a656fc99dab60dc9a239f5c686f))
* last_progress_at Spalte fuer Fortschritts-Watchdog (Spec 0034, Schritt 1) ([b5a209f](https://github.com/TheRealKoller/photosort/commit/b5a209f6214cabdf2cbadf6057a296f8ce6bdd3f))
* reap_stalled_runs Cron-Job als Schicht 2 des Fortschritts-Watchdogs (Spec 0034, Schritt 5) ([02e3d71](https://github.com/TheRealKoller/photosort/commit/02e3d71a032ce7f497d253c31ba67d5c3e08c5ea))
* Scan-Hänger-Detektion - Fortschritts-Watchdog gegen dauerhaft hängende Job-Läufe ([cab52c2](https://github.com/TheRealKoller/photosort/commit/cab52c2876ad5cadbbdd9d42666f51d7ac9354ee))
* Schicht 1 Fortschritts-Watchdog - CancelledError faengt Job-Laeufe ab (Spec 0034, Schritt 2) ([1c525eb](https://github.com/TheRealKoller/photosort/commit/1c525ebb33e8e98af1073c511ea5412e9b3b2f71))
* Zyklenschutz in OpenCloudClient.walk() (Spec 0034, Schritt 6) ([6bb7a19](https://github.com/TheRealKoller/photosort/commit/6bb7a19d696d241d71d301a4b83dc25ad74a0e54))


### Bug Fixes

* Copilot-Review-Funde in reap_stalled_runs/_fail_run beheben (PR [#67](https://github.com/TheRealKoller/photosort/issues/67)) ([6f342e0](https://github.com/TheRealKoller/photosort/commit/6f342e05d9ddedbcbf5f2916c95e69b8989d791d))
* rollback() nach fehlgeschlagenem SELECT in reap_stalled_runs (Review-Fund) ([c40ae5b](https://github.com/TheRealKoller/photosort/commit/c40ae5bc72936170825e5456c60bd6003fa7d048))

## [0.4.0](https://github.com/TheRealKoller/photosort/compare/v0.3.0...v0.4.0) (2026-08-09)


### Features

* gefilterte "Vorschläge ansehen"-Links auf der Projektseite ([e2dc3c9](https://github.com/TheRealKoller/photosort/commit/e2dc3c9bd5d2ebfaaf4b30b61c77a384dd6b22fb))
* idea-sharpener Modellzuweisung und Skip-Logik kalibrieren ([429374d](https://github.com/TheRealKoller/photosort/commit/429374d68289eb695d6ff5ee78b69ae40a087c9a))
* idea-sharpener Modellzuweisung und Skip-Logik kalibrieren (Spec 0032) ([f2f132e](https://github.com/TheRealKoller/photosort/commit/f2f132e29b8de58f4d79764c30d55c84429f6e9f))
* suggested-Filter im Photos-API-Endpunkt (Backend) ([b567855](https://github.com/TheRealKoller/photosort/commit/b5678558985fdbf96fd0b1d3dbf0dc8fd11adb11))
* suggested-Filter in der Foto-Grid-Ansicht (Frontend) ([7fb9428](https://github.com/TheRealKoller/photosort/commit/7fb9428a0363ec063d563c859e6e619d1532274a))
* Vorgeschlagene Fotos filterbar anzeigen (neuer Filter + Links) ([#61](https://github.com/TheRealKoller/photosort/issues/61)) ([130e520](https://github.com/TheRealKoller/photosort/commit/130e5205d8a3d1802b6fee350bbaacea6e16a1cb))


### Bug Fixes

* Review-Findings zu Spec 0032 beheben ([4b1acae](https://github.com/TheRealKoller/photosort/commit/4b1acae0f05c14f72fea5cd537ed5e246e9e4bc7))

## [0.3.0](https://github.com/TheRealKoller/photosort/compare/v0.2.0...v0.3.0) (2026-08-09)


### Features

* add research-engineer agent for structured web research ([#57](https://github.com/TheRealKoller/photosort/issues/57)) ([3d61068](https://github.com/TheRealKoller/photosort/commit/3d61068caeb9b6436bd1d2ff9a6e776fff72d574))

## [0.2.0](https://github.com/TheRealKoller/photosort/compare/v0.1.0...v0.2.0) (2026-08-08)


### Features

* local top-photo selection with category mix (Spec 0024) ([#51](https://github.com/TheRealKoller/photosort/issues/51)) ([61ccac1](https://github.com/TheRealKoller/photosort/commit/61ccac18465afd38c3aac791482ac21291bcb697))
