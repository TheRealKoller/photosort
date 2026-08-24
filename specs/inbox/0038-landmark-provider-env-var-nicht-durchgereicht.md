# 0038 - LANDMARK_PROVIDER/MISTRAL_API_KEY werden nicht an Container durchgereicht

**Typ:** Bug (vermeintlich)
**Erfasst:** 2026-08-24
**Status:** Unrefined

## Rohtext

`LANDMARK_PROVIDER=mistral` in `.env` gesetzt, um Mistral statt Anthropic für die Kategorisierung (inkl. der neuen Remote-Kategorie-Klassifizierung, Spec 0055) zu verwenden. Die Klassifizierung lief aber trotzdem mit Anthropic.

Diagnose in der Session: `LANDMARK_PROVIDER` ist der korrekte, absichtlich für beide Funktionen (landmark-Kriterium und Remote-Kategorie-Klassifizierung) gemeinsam genutzte Schalter (ADR 0032 Punkt 3) — kein Namensfehler im Code. Der eigentliche Fehler liegt in `docker-compose.yml`: die `environment:`-Blöcke der Services `backend` und `worker` reichen `LANDMARK_PROVIDER` und `MISTRAL_API_KEY` nicht durch — nur `ANTHROPIC_API_KEY` wird weitergegeben. Dadurch sieht der Container den Wert aus `.env` nie und pydantic fällt still auf den Default `"anthropic"` zurück. Betrifft vermutlich auch das bestehende `landmark`-Kriterium, nicht nur Spec 0055. Vorgeschlagener Fix: `LANDMARK_PROVIDER` und `MISTRAL_API_KEY` in den `environment:`-Blöcken von `backend` und `worker` in `docker-compose.yml` ergänzen; danach reicht ein Neustart (`docker compose up -d`), kein Rebuild nötig.
