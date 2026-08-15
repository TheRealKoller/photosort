# Changelog

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
