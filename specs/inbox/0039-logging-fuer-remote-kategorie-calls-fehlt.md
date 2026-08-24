# 0039 - Logging für Remote-Kategorie-Calls fehlt

**Typ:** Bug (vermeintlich)
**Erfasst:** 2026-08-24
**Status:** Unrefined

## Rohtext

Das Logging für die Remote-Calls muss verbessert werden, weil sonst nicht klar ist, ob die Requests tatsächlich stattgefunden haben oder ob sie fehlerhaft waren.

Hintergrund aus der Session: `worker.py::run_remote_category_classification` schluckt jeden Pro-Foto-Fehler mit einem bloßen `except: continue` (worker.py:1460-1465) — es existiert kein `logging`/`logger`/`print` in `worker.py`, `remote_classification.py` oder `cloud_vision.py`. Dadurch ist nach einem Lauf nicht mehr feststellbar, ob ein einzelnes Foto z.B. wegen eines Anthropic-Fehlers (401/429/...), eines lokalen Lesefehlers (fehlende Thumbnail-Cache-Datei) oder eines Antwort-Parsing-Fehlers übersprungen wurde. `docker compose logs` zeigt dazu aktuell nichts an.
