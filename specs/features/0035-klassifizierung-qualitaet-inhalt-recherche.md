# 0035 - Klassifizierung: Recherche zu Qualitäts- und Bildinhalt-Bestimmung

**Status:** Accepted
**Erstellt:** 2026-08-09
**Bezug:** Inbox-Eintrag `specs/inbox/0015-klassifizierung-qualitaet-inhalt-ueberdenken.md` (nach Aufnahme in diese Spec gelöscht). ADR [`decisions/0015-lokale-kategorie-klassifikation.md`](../decisions/0015-lokale-kategorie-klassifikation.md) (Accepted) — stoppte die dort ursprünglich geplante Cloud-Phase bewusst; diese Spec nimmt den Themenkomplex wieder auf, diesmal als offene Recherche statt vorschneller Entscheidung. `research-engineer`-Agent: Spec [`0028`](./0028-research-engineer-agent.md)/ADR [`decisions/0016-research-engineer-agent.md`](../decisions/0016-research-engineer-agent.md).

## Ziel

Diese Spec beauftragt **ausschließlich Recherche und Dokumentation**, keine Implementierung. Es soll systematisch untersucht und dokumentiert werden, welche Möglichkeiten es gibt, um (a) die **Qualität** von Fotos zu bestimmen und (b) den **Bildinhalt** zu klassifizieren (Mensch, Tier, Landschaft, Gebäude, Sehenswürdigkeit u.a.) — sowohl über lokale/selbst-hostbare Modelle als auch über Cloud-APIs (z.B. Anthropic, Mistral, Replicate, Hugging Face).

Bindende Vorgabe des Stakeholders (Daniel, bei der Ideenschärfung): Diese Spec trifft **keine** Auswahlentscheidung zwischen den recherchierten Optionen und plant **keine** Implementierung. Sie liefert ausschließlich die dokumentierte Entscheidungsgrundlage. Welche Lösung(en) gewählt werden und wann sie umgesetzt werden, entscheidet sich erst in einem eigenständigen, späteren Schritt, nachdem die Rechercheergebnisse vorliegen.

Hintergrund: PhotoSort hat bereits produktive lokale Qualitäts-/Klassifizierungslogik (Phase A: Schärfe/Belichtung/Duplikat-Erkennung/lokaler Quality-Score, Spec [`0003`](./0003-automatic-best-photo-selection.md); Phase B: lokale Kategorie-Klassifizierung PEOPLE/LANDSCAPE/DETAIL via mediapipe, Spec [`0024`](./0024-top-photo-selection-category-mix.md)). ADR 0015 hatte eine Cloud-Erweiterung (Anthropic Claude Vision) bewusst gestoppt, u.a. wegen ungeklärtem Einwilligungsmechanismus und dem Datenschutz-Vorbehalt "Familienfotos verlassen den Homeserver". Diese Recherche soll eine breitere, aktuelle Grundlage schaffen, um diese Frage später informiert neu zu bewerten — ohne den ursprünglichen Vorbehalt zu ignorieren.

## User Story

Als Stakeholder (Daniel) möchte ich eine dokumentierte Übersicht der verfügbaren Ansätze zur Qualitäts- und Inhaltsbestimmung von Fotos (lokal und Cloud, inkl. Kosten- und Datenschutz-Einschätzung je Option), damit ich anschließend informiert entscheiden kann, ob und wie die bestehende lokale Klassifizierung erweitert werden soll — ohne dass die Recherche selbst schon eine Lösung festlegt.

## Akzeptanzkriterien

- [ ] Die Spec enthält eine dokumentierte Übersicht von mindestens drei Ansätzen zur **Qualitätsbestimmung** (mindestens: lokal-heuristisch, lokales ML-Modell, Cloud-API), je mit Einschätzung zu Genauigkeit, Kosten und Datenschutz.
- [ ] Die Spec enthält eine dokumentierte Übersicht von mindestens drei Ansätzen zur **Bildinhalt-Klassifizierung** (mindestens: lokal-heuristisch/lokales ML-Modell, Cloud-API), mit Fokus auf die im Rohtext genannten Kategorien (Mensch, Tier, Landschaft, Gebäude, Sehenswürdigkeit) und auf Verhalten/Performance bei großen Fotobibliotheken (mehrere tausend Bilder pro Ordner).
- [ ] Für jede untersuchte **Cloud-Option** sind die in "Security" festgelegten Datenschutz-Kriterien (Datenfluss, Aufbewahrung/Löschung, Trainingsdaten-Nutzung, Rechtsraum/DSGVO-Bezug, Einwilligungsbedarf, Anonymisierungs-Möglichkeiten, API-Key-Zugriffskontrolle) mit dokumentiert, soweit öffentlich verfügbar.
- [ ] Für Cloud-Optionen sind mögliche Kostenkontroll-Strategien dokumentiert (z.B. Batch-Limits, Quotas, Sampling statt Vollverarbeitung, Caching, Vorab-Kostenschätzung) — als recherchierte Handlungsoptionen, nicht als Festlegung, welche davon umgesetzt wird.
- [ ] Alle recherchierten Optionen sind in einer strukturierten Vergleichstabelle gegenübergestellt (mind. Genauigkeit/Eignung, Kosten, Datenschutz, Aufwand/Abhängigkeiten) mit Quellenangaben (Aktualität, Vertrauenswürdigkeit, Relevanz je Quelle bewertet, gemäß Standard-Ausgabeformat des `research-engineer`-Agenten).
- [ ] Offene Unsicherheiten der Recherche sind explizit benannt (z.B. Punkte, die nur durch einen tatsächlichen Test mit echten Projektfotos zu klären wären).
- [ ] Die Spec enthält an keiner Stelle eine Empfehlung, Priorisierung oder Vorauswahl einer bestimmten Lösung — das bleibt ausdrücklich einem späteren, eigenständigen Entscheidungsschritt vorbehalten.

## Datenmodell-Bezug

Keines. Reine Recherche/Dokumentation, keine Code- oder Datenmodelländerung.

## Architektur / Umsetzung

**Nicht relevant** — `architect` nicht konsultiert (Schritt 6, siehe "Entscheidungen"): Diese Spec ist eine reine Text-/Dokumentationsaufgabe ohne jede Code-, Komponenten- oder Datenmodelländerung durch sich selbst. Eine Architekturentscheidung fällt frühestens bei einer künftigen, auf den Rechercheergebnissen aufbauenden Umsetzungs-Spec an — dort ist eine neue `architect`-Konsultation (und ggf. eine neue ADR) verbindlich fällig, nicht hier.

## UI/UX

**Nicht relevant** — `ux-ui-designer` nicht konsultiert (Schritt 7, siehe "Entscheidungen"): reine Recherche-Dokumentation ohne jede sichtbare Oberfläche, kein Frontend-Bezug in diesem Auftrag selbst.

## Security

Diese Spec beauftragt reine Recherche/Dokumentation, keine Implementierung — es werden keine echten Familienfotos verarbeitet oder an einen Dienst versendet. Direkt sicherheitskritisch ist die Recherche damit nicht. Sicherheitsrelevant ist aber ihr **Gegenstand**: ADR [`decisions/0015-lokale-kategorie-klassifikation.md`](../decisions/0015-lokale-kategorie-klassifikation.md) hat eine frühere Cloud-Phase (Anthropic Claude Vision) bewusst gestoppt, weil Familienfotos den Homeserver verlassen würden und der Einwilligungsmechanismus ungeklärt war. Diese Recherche greift denselben Themenkomplex wieder auf — eine spätere Entscheidung für eine Cloud-Option muss auf Basis vollständiger Datenschutz-Information getroffen werden können. Die Recherche selbst trifft diese Entscheidung nicht, liefert aber die Grundlage dafür.

**Muss-Kriterium für diese Spec:** Für jede untersuchte **Cloud-Option** (Anthropic, Mistral, Replicate, Hugging-Face-gehostete Endpunkte etc.) dokumentiert die Recherche mindestens:

1. **Datenfluss** — welche Daten genau übertragen werden (Originalbild, Downscale/Thumbnail oder nur ein Embedding), an wen (Anbieter, Rechenzentrums-Standort/Land, sofern öffentlich dokumentiert).
2. **Aufbewahrung/Löschung beim Anbieter** — Standard-Retention der übermittelten Bilder/Anfragen, ob und wie eine Löschung nach der Anfrage erfolgt oder erzwingbar ist (z.B. Zero-Data-Retention-Option), ob serverseitiges Logging/Caching der Anfrageinhalte stattfindet.
3. **Trainingsdaten-Nutzung** — nutzt der Anbieter über die API übermittelte Bilder standardmäßig zum Modelltraining, gibt es einen expliziten Opt-out, und gilt dieser für API-Nutzung (oft abweichend von Consumer-Produkten desselben Anbieters).
4. **Rechtsraum/DSGVO-Bezug** — EU-Hosting-Option vorhanden? Bei Drittlandbezug (insb. USA): Rechtsgrundlage für die Übermittlung (Standardvertragsklauseln, Angemessenheitsbeschluss); Verfügbarkeit eines Auftragsverarbeitungsvertrags (AVV/DPA) auch für Einzelpersonen-/Nicht-Enterprise-Konten, nicht nur für Business-Tarife.
5. **Einwilligungsbedarf** — auf den Fotos sind ggf. beide Nutzer und weitere Familienmitglieder (potenziell auch Kinder) erkennbar; dokumentieren, ob/welcher technische Einwilligungsmechanismus dafür nötig wäre. Die Bewertung, ob das für dieses private Projekt vertretbar ist, bleibt ausdrücklich Daniels spätere Entscheidung, nicht Teil dieser Recherche.
6. **Anonymisierung/Vorverarbeitung vor Versand** — technische Möglichkeit, vor dem Versand z.B. nur ein Embedding statt des Originalbilds zu senden, Gesichter unkenntlich zu machen (mit dem Hinweis, dass das den Zweck bei Personen-Erkennung konterkarieren kann) oder EXIF-/GPS-Metadaten zu entfernen.
7. **API-Key-/Zugriffskontrolle beim Anbieter** — Granularität von Scoping/Rotation/Widerruf des API-Keys (relevant für eine spätere Umsetzung, hier nur als Recherche-Kriterium mit erfassen).

Für **lokale/selbst-hostbare Modelle** entfällt dieser Datenschutz-Vorbehalt strukturell (keine Bilddaten verlassen den Homeserver) — hier sind Lizenzbedingungen (Redistribution/kommerzielle Nutzung, falls Modellgewichte wie bei `mediapipe` im Repo gebündelt würden) und Ressourcenbedarf die primär zu dokumentierenden Kriterien; das ist jedoch eine Architektur-, keine Sicherheitsfrage.

Randbemerkung zur im Rohtext genannten Kostenkontrolle: kein Sicherheitsaspekt im engeren Sinn, aber verwandt — ein unkontrollierter Batch von tausenden Anfragen bei einer Cloud-Option vervielfacht nicht nur die Kosten, sondern auch die Menge tatsächlich versendeter Familienfotos. Sinnvoll, das bei Punkt 1 (Datenfluss) je Option mit zu vermerken.

Kein Bezug zu Auth/Endpunkten/Secrets in dieser Spec, da keine Implementierung erfolgt. `specs/architecture/0003-securitykonzept.md` wird durch diese Spec nicht geändert — es entsteht keine reale Angriffsfläche. Sobald aus den Rechercheergebnissen eine konkrete Umsetzungs-Entscheidung getroffen und eine Feature-Spec dafür verfeinert wird, ist dort erneut eine Security-Konsultation vor Implementierung fällig (verbindlich, analog zum bereits dokumentierten Cloud-Phase-B-Vorbehalt in ADR 0015).

## Teststrategie

**Nicht relevant** — `test-engineer` nicht konsultiert (Schritt 8, siehe "Entscheidungen"): Durch diese Spec entsteht kein Code, der dem TDD-Zwang aus `CLAUDE.md` unterläge — reine Recherche-/Dokumentationsaufgabe.

## Entscheidungen

- **Recherche-Umfang: lokal + Cloud gleichwertig** (per Rückfrage an Daniel bestätigt): konsistent mit der bisherigen "erst lokal versuchen"-Linie aus ADR 0015 — die Recherche soll eine vollständige Grundlage liefern, nicht nur Cloud-Optionen vertiefen.
- **`architect` nicht konsultiert (Schritt 6):** reine Recherche-/Dokumentationsaufgabe ohne Code-/Komponenten-/Datenmodell-Bezug durch diese Spec selbst — Architekturentscheidungen fallen erst bei einer künftigen Umsetzungs-Spec an.
- **`ux-ui-designer` nicht konsultiert (Schritt 7):** keine sichtbare Oberfläche, kein Frontend-Bezug in diesem Auftrag.
- **`test-engineer` nicht konsultiert (Schritt 8):** kein Code entsteht durch diese Spec, somit kein TDD-pflichtiges Verhalten zu testen.
- **`security-engineer` bewusst konsultiert, trotz reiner Recherche-Natur (Schritt 8):** das recherchierte Thema (potenzielle künftige Cloud-KI-Verarbeitung von Familienfotos) berührt genau den Datenschutz-Vorbehalt, der die Cloud-Phase in ADR 0015 bereits einmal gestoppt hat — die Recherche muss deshalb selbst schon die Kriterien liefern, mit denen eine spätere Entscheidung datenschutzbewusst getroffen werden kann, auch wenn sie hier noch nicht getroffen wird.
- **Keine Auswahl-/Priorisierungs-Entscheidung in dieser Spec** (bindende Stakeholder-Vorgabe): explizit als eigenes Akzeptanzkriterium festgehalten, um zu verhindern, dass die spätere Ausführung der Recherche (z.B. durch den `research-engineer`-Agenten) informell doch schon eine Empfehlung ausspricht, die als Vorentscheidung missverstanden werden könnte.
- **Ausführung/Ownership (technische Detailentscheidung, keine Rückfrage nötig):** Die eigentliche Recherche wird — anders als bei einer normalen Umsetzungs-Spec — nicht vom `developer`-Agenten (TDD-Workflow, hier nicht anwendbar) bearbeitet, sondern durch direkte Beauftragung des `research-engineer`-Agenten in einer eigenen, späteren Session. Das Ergebnis wird als neuer Abschnitt "Rechercheergebnis" an diese Spec-Datei angehängt; der Status wechselt danach auf `Implemented` (hier zu verstehen als "Recherche abgeschlossen und dokumentiert", nicht als "Code umgesetzt").
- **Roadmap-Priorität: Mittel** (`requirements-engineer`-Konsultation, 2026-08-09): strategisch relevant (Kernfeature Bildklassifizierung), aber nicht blockierend für laufende Arbeit; kein Prioritätskonflikt mit bereits Geplantem.

## Offene Fragen

Keine.

## Out of Scope

- Auswahl/Entscheidung, welche der recherchierten Lösungen tatsächlich verwendet wird — folgt in einem eigenständigen, späteren Schritt nach Vorliegen der Rechercheergebnisse.
- Implementierung jeglicher Art (Code, neue Abhängigkeiten, Konfiguration, Datenmodelländerungen) — folgt frühestens mit einer eigenen, künftigen Feature-Spec nach der Auswahlentscheidung.
- Tatsächlicher Aufbau eines konkreten Kostenkontroll-Mechanismus — die Recherche dokumentiert nur mögliche Strategien dafür, baut keine.
- Tatsächliches Testen/Benchmarking recherchierter Modelle an echten Projektfotos — falls die Recherche das für eine belastbare Bewertung für nötig hält, wird das als offene Unsicherheit benannt, nicht selbst durchgeführt (keine Familienfotos würden dafür ungeprüft an eine Cloud-API geschickt).
