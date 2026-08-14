# 0017 - Sehenswürdigkeit-Erkennung über Cloud-Vision-API

**Typ:** Idee
**Erfasst:** 2026-08-13
**Status:** Unrefined

## Rohtext

Sehenswürdigkeit-Erkennung (Landmark) als künftiges Kriterium für die Kriterien-Bewertungs-Pipeline (PhotoCriterionScore/CRITERIA_REGISTRY, Spec 0037): laut Recherche in Spec 0035 gibt es keinen brauchbaren lokalen Weg dafür (ADR 0015 hatte lokale Landmark-Erkennung wie DELG/DOLG bereits als für private Reisefotos ohne GPS unwirtschaftlich verworfen) — realistisch nur über eine Cloud-Vision-API (z.B. Anthropic, Mistral) lösbar, mit LLM-Weltwissen über bekannte Wahrzeichen. Am 2026-08-13 mit Daniel besprochen und bewusst zurückgestellt: aktuell nicht wichtig genug, um die dafür nötige Cloud-Anbindung (Einwilligungsmechanismus, Kostenkontrolle, ungeklärte DPA-Frage für Privatkonten) zu rechtfertigen. Alle anderen offenen Kriterien aus Spec 0037 (Tier, Gebäude, Goldener Schnitt, Ästhetik) werden stattdessen lokal umgesetzt. Bei Bedarf später als eigenständige Spec mit eigener Security-Konsultation aufgreifen.
