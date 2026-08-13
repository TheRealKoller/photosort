# 0035 - Klassifizierung: Recherche zu Qualitäts- und Bildinhalt-Bestimmung

**Status:** Implemented
**Erstellt:** 2026-08-09
**Bezug:** Inbox-Eintrag `specs/inbox/0015-klassifizierung-qualitaet-inhalt-ueberdenken.md` (nach Aufnahme in diese Spec gelöscht). ADR [`decisions/0015-lokale-kategorie-klassifikation.md`](../decisions/0015-lokale-kategorie-klassifikation.md) (Accepted) — stoppte die dort ursprünglich geplante Cloud-Phase bewusst; diese Spec nimmt den Themenkomplex wieder auf, diesmal als offene Recherche statt vorschneller Entscheidung. `research-engineer`-Agent: Spec [`0028`](./0028-research-engineer-agent.md)/ADR [`decisions/0016-research-engineer-agent.md`](../decisions/0016-research-engineer-agent.md).

## Ziel

Diese Spec beauftragt **ausschließlich Recherche und Dokumentation**, keine Implementierung. Es soll systematisch untersucht und dokumentiert werden, welche Möglichkeiten es gibt, um (a) die **Qualität** von Fotos zu bestimmen und (b) den **Bildinhalt** zu klassifizieren (Mensch, Tier, Landschaft, Gebäude, Sehenswürdigkeit u.a.) — sowohl über lokale/selbst-hostbare Modelle als auch über Cloud-APIs (z.B. Anthropic, Mistral, Replicate, Hugging Face).

Bindende Vorgabe des Stakeholders (Daniel, bei der Ideenschärfung): Diese Spec trifft **keine** Auswahlentscheidung zwischen den recherchierten Optionen und plant **keine** Implementierung. Sie liefert ausschließlich die dokumentierte Entscheidungsgrundlage. Welche Lösung(en) gewählt werden und wann sie umgesetzt werden, entscheidet sich erst in einem eigenständigen, späteren Schritt, nachdem die Rechercheergebnisse vorliegen.

Hintergrund: PhotoSort hat bereits produktive lokale Qualitäts-/Klassifizierungslogik (Phase A: Schärfe/Belichtung/Duplikat-Erkennung/lokaler Quality-Score, Spec [`0003`](./0003-automatic-best-photo-selection.md); Phase B: lokale Kategorie-Klassifizierung PEOPLE/LANDSCAPE/DETAIL via mediapipe, Spec [`0024`](./0024-top-photo-selection-category-mix.md)). ADR 0015 hatte eine Cloud-Erweiterung (Anthropic Claude Vision) bewusst gestoppt, u.a. wegen ungeklärtem Einwilligungsmechanismus und dem Datenschutz-Vorbehalt "Familienfotos verlassen den Homeserver". Diese Recherche soll eine breitere, aktuelle Grundlage schaffen, um diese Frage später informiert neu zu bewerten — ohne den ursprünglichen Vorbehalt zu ignorieren.

## User Story

Als Stakeholder (Daniel) möchte ich eine dokumentierte Übersicht der verfügbaren Ansätze zur Qualitäts- und Inhaltsbestimmung von Fotos (lokal und Cloud, inkl. Kosten- und Datenschutz-Einschätzung je Option), damit ich anschließend informiert entscheiden kann, ob und wie die bestehende lokale Klassifizierung erweitert werden soll — ohne dass die Recherche selbst schon eine Lösung festlegt.

## Akzeptanzkriterien

- [x] Die Spec enthält eine dokumentierte Übersicht von mindestens drei Ansätzen zur **Qualitätsbestimmung** (mindestens: lokal-heuristisch, lokales ML-Modell, Cloud-API), je mit Einschätzung zu Genauigkeit, Kosten und Datenschutz.
- [x] Die Spec enthält eine dokumentierte Übersicht von mindestens drei Ansätzen zur **Bildinhalt-Klassifizierung** (mindestens: lokal-heuristisch/lokales ML-Modell, Cloud-API), mit Fokus auf die im Rohtext genannten Kategorien (Mensch, Tier, Landschaft, Gebäude, Sehenswürdigkeit) und auf Verhalten/Performance bei großen Fotobibliotheken (mehrere tausend Bilder pro Ordner).
- [x] Für jede untersuchte **Cloud-Option** sind die in "Security" festgelegten Datenschutz-Kriterien (Datenfluss, Aufbewahrung/Löschung, Trainingsdaten-Nutzung, Rechtsraum/DSGVO-Bezug, Einwilligungsbedarf, Anonymisierungs-Möglichkeiten, API-Key-Zugriffskontrolle) mit dokumentiert, soweit öffentlich verfügbar.
- [x] Für Cloud-Optionen sind mögliche Kostenkontroll-Strategien dokumentiert (z.B. Batch-Limits, Quotas, Sampling statt Vollverarbeitung, Caching, Vorab-Kostenschätzung) — als recherchierte Handlungsoptionen, nicht als Festlegung, welche davon umgesetzt wird.
- [x] Alle recherchierten Optionen sind in einer strukturierten Vergleichstabelle gegenübergestellt (mind. Genauigkeit/Eignung, Kosten, Datenschutz, Aufwand/Abhängigkeiten) mit Quellenangaben (Aktualität, Vertrauenswürdigkeit, Relevanz je Quelle bewertet, gemäß Standard-Ausgabeformat des `research-engineer`-Agenten).
- [x] Offene Unsicherheiten der Recherche sind explizit benannt (z.B. Punkte, die nur durch einen tatsächlichen Test mit echten Projektfotos zu klären wären).
- [x] Die Spec enthält an keiner Stelle eine Empfehlung, Priorisierung oder Vorauswahl einer bestimmten Lösung — das bleibt ausdrücklich einem späteren, eigenständigen Entscheidungsschritt vorbehalten.

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

## Rechercheergebnis

Ausgeführt durch den `research-engineer`-Agenten (2026-08-10). Diese Recherche spricht bewusst **keine** Empfehlung, Priorisierung oder Vorauswahl aus (bindende Stakeholder-Vorgabe, siehe Abschnitt "Ziel"). Sie liefert ausschließlich dokumentierte, quellenbelegte Fakten zu allen recherchierten Optionen als Entscheidungsgrundlage für einen späteren, eigenständigen Auswahlschritt.

### 1. Ansätze zur Qualitätsbestimmung

| # | Ansatz | Genauigkeit/Eignung | Kosten | Datenschutz |
|---|---|---|---|---|
| A | **Lokal-heuristisch** (bereits produktiv: Laplace-Varianz-Schärfe, Belichtungs-Histogramm, dHash-Duplikate — Spec 0003) | Grobe, nicht gegen echte Kamerafotos kalibrierte Näherung (dokumentierter Vorbehalt in Spec 0003/ADR 0006); erkennt objektiv Unschärfe/Fehlbelichtung, keine Ästhetik-/Kompositionsbewertung | 0 € (reines Pillow, bereits vorhandene Abhängigkeit) | unkritisch — keine Daten verlassen den Server |
| B | **Lokales ML-Modell** (Ästhetik-/Qualitäts-Score), z.B. NIMA (`idealo/image-quality-assessment`, Apache-2.0, MobileNet-Backbone) oder die `pyiqa`/`IQA-PyTorch`-Toolbox (BRISQUE, MUSIQ, CLIP-IQA u.a.) | Potenziell näher an menschlicher Ästhetik-Wahrnehmung als reine Heuristik, aber trainiert auf allgemeinen Foto-Datensätzen, nicht auf privaten Familienfotos — Trefferquote auf tatsächlichen Projektfotos ungeprüft | 0 € Lizenzkosten, aber CPU-Zeit/Modellgröße höher als reine Heuristik (MobileNet ~16 MB; größere Backbones deutlich mehr) | unkritisch — läuft lokal, keine Datenübertragung |
| C | **Cloud-API** (Vision-LLM-Ästhetik-Bewertung per Prompt, z.B. Anthropic Claude Vision, Mistral Pixtral) | Potenziell hohe Genauigkeit inkl. Kontext-/Kompositionsverständnis und Textbegründung, aber nicht projektspezifisch getestet | Pro-Bild-/Token-Kosten (siehe Abschnitt 4) | kritisch — Bilddaten verlassen den Server, siehe Abschnitt 3 |

### 2. Ansätze zur Bildinhalt-Klassifizierung

| # | Ansatz | Genauigkeit/Eignung | Verhalten bei großen Bibliotheken |
|---|---|---|---|
| A | **Lokal-heuristisch + leichtgewichtiges lokales ML** (bereits produktiv: mediapipe Face Detector für "Menschen", Pillow-Uniform-Flächen-Heuristik für Landschaft/Detail — ADR 0015/Spec 0024) | Deckt aktuell nur 3 von 5 im Rohtext genannten Kategorien ab (Mensch/Landschaft/Detail als Fallback); **Tier, Gebäude, Sehenswürdigkeit fehlen strukturell** | Bereits gelöst durch begrenzten Kandidatenpool pro Cluster (`min(cluster_size, max(N*3, 6))`, Spec 0024) statt Vollverarbeitung — verhindert, dass mediapipe/Heuristik auf jedes Foto eines großen Ordners läuft |
| B | **Weitere lokale ML-Modelle** (mehrere unabhängige Optionen, je nach Kategorie unterschiedlich geeignet):<br>• **CLIP/`open_clip`** (Zero-Shot-Textlabel-Matching, z.B. "Mensch"/"Tier"/"Landschaft"/"Gebäude") — kein Fine-Tuning nötig, aber grob<br>• **Places365** (CSAILVision, 365-Klassen-Szenen-Klassifikation) — für Landschaft/Gebäude-Unterscheidung potenziell direkter geeignet als die aktuelle Uniform-Flächen-Heuristik<br>• **YOLOv8**/objekterkennungsbasierte Modelle für "Tier" (COCO-Klassen umfassen diverse Tierarten)<br>• **Landmark-Erkennung** (Google Landmarks Dataset v2 + DELG/DOLG) — von ADR 0015 bereits bewusst als für v1 unwirtschaftlich eingeschätzt (großes Modell, geringe Trefferquote für private Reisefotos ohne GPS); diese Recherche bestätigt diese Einschätzung, ohne sie neu zu bewerten | Jedes zusätzliche Modell erhöht CPU-Laufzeit pro Foto — dieselbe, bereits in Spec 0024 etablierte Strategie (Kandidatenpool-Begrenzung statt Vollverarbeitung) wäre auch hier anwendbar, kein neues Konzept nötig |
| C | **Cloud-API** (Vision-LLM-Klassifikation per Prompt: Anthropic, Mistral Pixtral, oder gehostete Spezialmodelle via Replicate/Hugging-Face-Inference-Providers) | Potenziell höchste Genauigkeit inkl. Sehenswürdigkeiten-Erkennung (LLM-Trainingswissen über bekannte Wahrzeichen) — als einzige der drei Kategorien realistisch in der Lage, "Sehenswürdigkeit" ohne GPS zu erkennen | Bei mehreren tausend Bildern: proportional wachsende Kosten, Rate-Limit-Risiko, Netzwerk-Latenz pro Anfrage — macht Batch-APIs und/oder Sampling (Abschnitt 4) relevant statt Vollverarbeitung |

### 3. Security-Kriterien je Cloud-Option

#### Anthropic (Claude API)

1. **Datenfluss:** Bild als Base64 im Request (bis 10 MB/Bild, bis 100 Bilder/Request, bis 8000×8000 px, intern skaliert/tokenisiert). Rechenzentrum primär USA (AWS als Sub-Processor); die "reine" Anthropic-API bietet **keine garantierte EU-Region** — EU-Hosting nur über den Umweg AWS Bedrock (Frankfurt/Irland/Paris/Stockholm) oder Google Vertex AI EU-Regionen, nicht über die direkte Anthropic-API selbst.
2. **Aufbewahrung/Löschung:** Standard-API-Log-Retention seit 14.09.2025 auf **7 Tage** reduziert (vorher 30), kein Training. Über DPA erweiterbar auf 30 Tage oder **Zero Data Retention (ZDR)** — ZDR muss separat pro Organisation bei Anthropic Sales beantragt werden, keine Selbstbedienungs-Option.
3. **Trainingsdaten-Nutzung:** Standardmäßig **kein** Training mit API-/Commercial-Daten (anders als Consumer-Claude.ai). Eine unabhängige Kritik-Quelle (2026-06-09) weist auf einen "Safety-Flag"-Carve-out bei Consumer-Produkten hin — betrifft laut Quellenlage ausdrücklich nicht die API.
4. **Rechtsraum/DSGVO:** Anthropic Inc., USA. DPA (inkl. SCC) automatisch Teil der Commercial Terms, zugänglich über die Anthropic-Console auch für reguläre (nicht nur Enterprise-)API-Kunden — **unklar, ob ein privates Einzelkonto denselben Zugriffsweg erhält wie ein Business-Konto** (offene Unsicherheit).
5. **Einwilligungsbedarf:** anbieterunabhängige, generische Frage — siehe Sammelabsatz unten.
6. **Anonymisierung vor Versand:** technisch möglich clientseitig (lokal, vor dem API-Call): Gesichter unkenntlich machen (konterkariert aber "Menschen"-Erkennung), EXIF-/GPS-Metadaten entfernen (mit dem bereits vorhandenen Pillow möglich). Reine Embedding-Übermittlung statt Originalbild ist bei der Anthropic-Vision-API technisch nicht vorgesehen (API erwartet ein Bild, kein rohes Embedding als Input).
7. **API-Key-Kontrolle:** Keys pro Workspace gescoped, Rollenmodell (user/developer/billing/admin) steuert Erstellung/Verwaltung, sofortiger Widerruf über Console; keine native automatische Rotation (Empfehlung Dritter: manuell ~alle 90 Tage).

#### Mistral AI

1. **Datenfluss:** Bild an Pixtral-Modell übermittelt. Mistral AI SAS, Sitz Frankreich/EU — Speicherung laut Dokumentation standardmäßig in der EU.
2. **Aufbewahrung/Löschung:** Standard 30 Tage rollierende Aufbewahrung (Missbrauchsüberwachung), danach Löschung. **Zero Data Retention** für zustandslose Aufrufe (u.a. Chat Completions, also auch Vision-Prompts) verfügbar — **aber nur im kostenpflichtigen "Scale"-Tarif**, nicht im Standard-/Einzelentwickler-Tarif.
3. **Trainingsdaten-Nutzung:** API-Daten werden nicht für Training verwendet, zahlende API-Nutzer standardmäßig opted-out; unklar, ob das für unbezahlte/Free-Tarife identisch gilt.
4. **Rechtsraum/DSGVO:** EU-Unternehmen, DPA laut eigener Aussage "GDPR als Baseline". **Verfügbarkeit für Einzelpersonen-/Nicht-Business-Konten aus den gesichteten Quellen nicht eindeutig geklärt** — der DPA-Text unterscheidet "Commercial Customers" von "Consumers", ohne dass klar wird, welchem Bucket ein privates API-Konto zugeordnet ist (offene Unsicherheit).
5. **Einwilligungsbedarf:** siehe Sammelabsatz unten.
6. **Anonymisierung:** technisch analog zu Anthropic möglich, keine anbieterspezifische Unterstützung gefunden.
7. **API-Key-Kontrolle:** in den gesichteten Quellen deutlich weniger granular dokumentiert als bei Anthropic/HF (offene Unsicherheit).

#### Replicate

1. **Datenfluss:** Bild an Replicate-API, die an das gewählte (oft community-gehostete) Modell weiterleitet — Infrastruktur primär USA (San Francisco). Bei Community-Modellen ist der jeweilige Modell-Autor/-Betreiber ein zusätzlicher De-facto-Verarbeiter — komplexere Kette als bei Anthropic/Mistral als Erstanbieter.
2. **Aufbewahrung/Löschung:** API-Predictions (Input/Output/Logs) **automatisch nach 1 Stunde gelöscht** (Default) — kürzeste Standard-Retention aller vier untersuchten Optionen. Web-Interface-Predictions dagegen unbegrenzt gespeichert (für eine API-Nutzung durch PhotoSort irrelevant).
3. **Trainingsdaten-Nutzung:** aus den gesichteten Quellen nicht eindeutig, ob reguläre Inferenz-Requests (nicht explizite Fine-Tuning-Uploads) zum Training verwendet werden — die Datenschutzerklärung behandelt explizit nur hochgeladene "Training Data" für Fine-Tuning (offene Unsicherheit).
4. **Rechtsraum/DSGVO:** Replicate Inc., USA. Eine gefundene "DPA"-Quelle bezog sich auf eine andere Domain ("replicatelabs.ai" statt "replicate.com") — **Verwechslungsgefahr, nicht als verlässliche Aussage über die eigentliche Plattform gewertet**. Ob replicate.com selbst einen öffentlich zugänglichen DPA für Einzelkonten anbietet, konnte nicht zweifelsfrei bestätigt werden (offene Unsicherheit).
5. **Einwilligungsbedarf:** siehe Sammelabsatz unten.
6. **Anonymisierung:** technisch analog möglich, keine anbieterspezifische Unterstützung gefunden.
7. **API-Key-Kontrolle:** kontoweite Spend-Limits über Dashboard (seit Juli 2025 Prepaid-Guthaben statt monatlicher Spend-Limits — Guthaben wirkt als harte Obergrenze), Schwellenwert-Webhooks (50/80/100 %). Granulares API-Key-Scoping (pro Projekt/Modell) oder erzwungene Rotation nicht mit belastbarer Quelle bestätigt (offene Unsicherheit).

#### Hugging Face (gehostete Endpunkte)

**Wichtige Nuance:** HF bietet strukturell zwei unterschiedliche Wege, getrennt zu bewerten: **(a) Inference Providers** (Serverless-Marktplatz, leitet an 15+ Dritt-Backends wie Together, Fireworks, Replicate, Cerebras u.a. weiter) und **(b) Inference Endpoints** (dediziertes Single-Tenant-Hosting, Region/Cloud-Anbieter selbst wählbar, inkl. EU).

1. **Datenfluss:** bei Inference Providers hängt der tatsächliche Empfänger vom gewählten Dritt-Provider ab (kein einheitlicher Datenfluss); bei Inference Endpoints geht das Bild ausschließlich an die selbst gewählte, dedizierte Infrastruktur.
2. **Aufbewahrung/Löschung:** für Inference Endpoints laut HF-Doku keine Payload-/Token-Speicherung, nur 30 Tage Log-Aufbewahrung (vermutlich Metadaten); für Inference Providers gilt die Policy des jeweiligen Drittanbieters (offene Unsicherheit je gewähltem Provider).
3. **Trainingsdaten-Nutzung:** für die "Inference API mit DPA" wird ein expliziter No-Training/No-Retention-Grundsatz genannt — ob das auch ohne kostenpflichtiges DPA (Free/PRO) gilt, nicht eindeutig bestätigt.
4. **Rechtsraum/DSGVO:** Hugging Face SAS, Hauptniederlassung Paris/Frankreich (CNIL-Aufsicht), SOC2-Type-2-zertifiziert. **DPA nur über Enterprise-Hub-Abo verfügbar** — für ein privates Einzelkonto (Free/PRO) kein eigenständiger DPA-Self-Service-Zugang gefunden (klarste negative Aussage unter den vier Optionen).
5. **Einwilligungsbedarf:** siehe Sammelabsatz unten.
6. **Anonymisierung:** bei Inference Endpoints zusätzlich vollständig selbstkontrollierte Infrastruktur wählbar (eigene Region, AWS PrivateLink) — reduziert, ersetzt aber nicht clientseitige Vorverarbeitung.
7. **API-Key-Kontrolle:** "Fine-grained Access Tokens" mit granularer Ressourcen-/Rechte-Scoping (z.B. nur ein Modell/eine Organisation), Status-Anzeige, unwiderruflicher Widerruf jederzeit möglich — von den vier Optionen die am detailliertesten dokumentierte Token-Granularität.

**Sammelabsatz Einwilligungsbedarf (Punkt 5, alle vier Optionen gleichermaßen, nicht anbieterspezifisch, nur dokumentiert, nicht bewertet):** Nach Erwägungsgrund 51 DSGVO gelten Fotos nicht automatisch als "besondere Kategorie" personenbezogener Daten — nur wenn sie durch spezifische technische Verarbeitung zur eindeutigen Identifizierung (biometrisch) genutzt werden. Für Kinder gelten nach Art. 8 DSGVO zusätzlich verschärfte Einwilligungsanforderungen (Einwilligung Erziehungsberechtigter unterhalb einer mitgliedstaatlich festgelegten Altersgrenze, meist 16 Jahre). Ob/welcher technische Einwilligungsmechanismus im Familienkontext nötig wäre, bleibt ausdrücklich Daniels spätere Bewertung.

### 4. Kostenkontroll-Strategien für Cloud-Optionen (recherchierte Handlungsoptionen, keine Festlegung)

- **Batch-APIs:** Anthropic und Mistral bieten beide native Batch-Verarbeitung (je 50 % Rabatt, Anthropic mit 24h-Fenster) für nicht-zeitkritische Massenverarbeitung — passt strukturell zum bestehenden asynchronen Job-Muster des Projekts (`ScoringRun`/`TopSelectionRun`).
- **Prompt Caching (Anthropic):** wiederkehrende, identische Prompt-Anteile (z.B. Klassifikations-Anweisung) werden bei wiederholten Aufrufen zu 10 % des Preises abgerechnet, kombinierbar mit Batch für bis zu ~95 % Ersparnis auf den Nicht-Bild-Anteil — das Bild selbst ist pro Anfrage i.d.R. nicht cachebar.
- **Sampling statt Vollverarbeitung:** nur eine Stichprobe pro Cluster/Ordner an die Cloud schicken (analog zum bereits etablierten "begrenzten Kandidatenpool" aus Spec 0024) statt aller tausend Fotos.
- **Caching/Wiederverwendung von Ergebnissen:** einmal klassifizierte Fotos nicht bei jedem erneuten Lauf neu senden — Gegenmodell zum aktuellen "jeder Lauf scort neu"-Prinzip (Spec 0003/0024), das dort bewusst gewählt wurde, *weil* lokal kostenlos; bei einer Cloud-Variante wäre dieselbe Entscheidung teuer und müsste neu bewertet werden.
- **Vorab-Kostenschätzung:** Anzahl Fotos × Preis pro Bild/Token vor Start anzeigen — bereits im früheren, verworfenen Cloud-Phase-B-Entwurf vorgesehen; hier nur als weiterhin verfügbare Option dokumentiert.
- **Konto-/Spend-Limits als harte Obergrenze:** bei Replicate über Prepaid-Guthaben belegt; bei Anthropic/Mistral über Console-Billing-Limits nicht im Detail für alle vier Anbieter recherchiert (offene Unsicherheit).
- **Serverseitige Batch-Größenobergrenze pro Lauf:** rein projektinterne, anbieterunabhängige Maßnahme.

### 5. Lokale/selbst-hostbare Modelle: Lizenz & Ressourcenbedarf

| Modell | Lizenz | Ressourcenbedarf |
|---|---|---|
| mediapipe (bereits im Projekt) | Apache-2.0 | CPU-only, `.tflite`-Modell wenige MB, bereits ins Docker-Image gebündelt |
| NIMA (`idealo/image-quality-assessment`) | Apache-2.0 | MobileNet-Backbone ~16 MB, TensorFlow/Keras, CPU-fähig |
| `pyiqa`/IQA-PyTorch (BRISQUE, MUSIQ, CLIP-IQA u.a.) | **PolyForm Noncommercial License 1.0.0 + NTU S-Lab License** — nicht für kommerzielle Nutzung freigegeben | PyTorch, je nach Metrik von sehr leicht (BRISQUE) bis mehrere hundert MB (MUSIQ/MANIQA) |
| CLIP/`open_clip` | Original OpenAI-Code/-Gewichte MIT; Nachfolge-/LAION-Checkpoints teils eigene, separat zu prüfende Lizenzen | ViT-B/32 (~350 MB) CPU-tauglich; größere Varianten praktisch GPU-Bedarf bei tausenden Bildern |
| Places365 (CSAILVision) | **CC BY** (Attribution erforderlich) | ResNet18 (~45 MB) bis ResNet152 (~230 MB), CPU-fähig |
| YOLOv8 (Ultralytics) | **AGPL-3.0** — Redistribution/Bündelung im Repo löst laut Ultralytics potenziell Offenlegungspflicht für den gesamten Quellcode aus; Enterprise-Lizenz nötig, falls das nicht gewünscht ist. Projektspezifische Prüfung nötig, hier nur als recherchiertes Faktum dokumentiert. | mehrere MB bis ~50 MB je Variante, CPU-fähig |
| Google Landmarks / DELG/DOLG | Code meist Apache-2.0, Datensatz-Bilder unter Wikimedia-kompatiblen freien Lizenzen | großes Modell, wie in ADR 0015 bereits als für v1 unwirtschaftlich eingeschätzt — hier nur zur Vollständigkeit bestätigt, keine neue Bewertung |

### 6. Vergleichstabelle (Gesamtübersicht)

| Option | Genauigkeit/Eignung | Kosten | Datenschutz | Aufwand/Abhängigkeiten |
|---|---|---|---|---|
| Lokal-heuristisch (Ist-Zustand) | grob, unkalibriert | 0 € | unkritisch | keine neue Abhängigkeit |
| Lokales ML (NIMA/pyiqa/CLIP/Places365/YOLOv8) | potenziell besser, ungeprüft auf Projektfotos | 0 € Lizenz, höhere CPU-Zeit | unkritisch | neue Abhängigkeit + teils Lizenzprüfung nötig (AGPL/Noncommercial) |
| Anthropic Claude Vision | potenziell hoch (LLM-Kontextverständnis) | Token-basiert, Batch/Caching verfügbar | USA-Default, kein EU-Hosting direkt, DPA-Zugang für Einzelkonten unklar | API-Key, neue externe Schnittstelle |
| Mistral Pixtral | potenziell hoch | Token-basiert, Batch verfügbar | EU-nativ, ZDR nur im teuren Tarif, DPA-Konto-Typ unklar | API-Key, neue externe Schnittstelle |
| Replicate (gehostete Modelle) | modellabhängig, sehr variabel | pro Sekunde/Modell | kürzeste Default-Retention (1h), DPA-Verfügbarkeit unklar, komplexere Verarbeiterkette | API-Key, neue externe Schnittstelle |
| Hugging Face (Endpoints/Providers) | modellabhängig | modellabhängig, Free-Tier vorhanden | Endpoints: volle Kontrolle inkl. EU-Region; Providers: uneinheitlich je Drittanbieter; DPA nur Enterprise | API-Key, neue externe Schnittstelle, ggf. mehrere Sub-Processoren |

### Quellenliste (Bewertung: Aktualität / Vertrauenswürdigkeit / Relevanz)

- [Anthropic Privacy Center — Is my data used for model training?](https://privacy.claude.com/en/articles/7996868-is-my-data-used-for-model-training) / [How long do you store my data?](https://privacy.claude.com/en/articles/10023548-how-long-do-you-store-my-data) — aktuell (offizielle, laufend gepflegte Anbieterseite 2026), hoch vertrauenswürdig (Erstanbieter), hoch relevant.
- [Claude Platform Docs — Vision](https://platform.claude.com/docs/en/build-with-claude/vision), [API and data retention](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention) — aktuell, offizielle Doku, hoch relevant für Datenfluss/Retention/Bildlimits.
- Sekundärquellen zu Anthropic-Themen (tygartmedia.com, pecollective.com, compound.law, techcoffeehouse.com) — mittlere Vertrauenswürdigkeit (Drittanbieter-Blogs, teils SEO-getrieben, keine Erstquelle), wurden nur zur Einordnung genutzt, nicht als alleiniger Beleg für harte Fakten; eine Quelle (claudecodecamp.com, Modell-Token-Details) enthielt Modellnamen, deren Existenz nicht anderweitig verifiziert werden konnte — mit geringer Konfidenz behandelt, nicht als belastbares Faktum übernommen.
- [Mistral — Data Processing Addendum](https://legal.mistral.ai/terms/data-processing-addendum), [Privacy and data controls](https://docs.mistral.ai/admin/monitor-comply/privacy-data-controls), [Privacy](https://docs.mistral.ai/admin/security-access/privacy) — aktuell, offizielle Erstanbieter-Doku, hoch relevant, aber an einer Stelle (Konto-Typ-Zuordnung DPA) mehrdeutig formuliert.
- [Mistral Help Center — Opt-out Training](https://help.mistral.ai/en/articles/455207-can-i-opt-out-of-my-input-or-output-data-being-used-for-training) — offizielle Support-Quelle, aktuell, hoch relevant.
- [Replicate — Privacy policy](https://replicate.com/privacy), [Data retention](https://replicate.com/docs/topics/predictions/data-retention) — offizielle Erstanbieter-Doku, aktuell, aber lückenhaft zu Trainingsdaten-Nutzung reiner Inferenz-Requests.
- "Data Processing Agreement | Replicate Labs" (replicatelabs.ai) — **nicht verwertet als Aussage über replicate.com**, da andere Domain/vermutlich anderes Unternehmen; explizit als Verwechslungsrisiko markiert, nicht als belastbare Quelle in die Bewertung eingeflossen.
- [Hugging Face — Security & Compliance (Inference Endpoints)](https://huggingface.co/docs/inference-endpoints/en/security), [Privacy Policy](https://huggingface.co/privacy), [User access tokens](https://huggingface.co/docs/hub/en/security-tokens) — offizielle Erstanbieter-Doku, aktuell, hoch relevant.
- WAIMAKERS GDPR-Compliance-Guide zu Hugging Face — Drittquelle, mittlere Vertrauenswürdigkeit, nur ergänzend zur Einordnung des CNIL-Bezugs genutzt.
- [idealo/image-quality-assessment (NIMA)](https://github.com/idealo/image-quality-assessment) — offizielles Repo, aktuell genug für Lizenz-/Architektur-Fakten, hoch relevant.
- [chaofengc/IQA-PyTorch (pyiqa)](https://github.com/chaofengc/IQA-PyTorch) — offizielles Repo, hoch relevant, Lizenzangabe direkt aus der README.
- [CSAILVision/places365](https://github.com/CSAILVision/places365) — offizielles Repo des Places365-Projekts, hoch vertrauenswürdig, hoch relevant.
- [Ultralytics License](https://www.ultralytics.com/license), [GitHub Issue #19390 zu AGPL-Fragen](https://github.com/ultralytics/ultralytics/issues/19390) — offizielle Anbieterseite + offizielles Repo-Issue, aktuell, hoch relevant für die Lizenzfrage.
- [tensorflow/models — DELF/DELG](https://github.com/tensorflow/models/tree/master/research/delf) — offizielles TensorFlow-Research-Repo, mittlere Aktualität (Research-Code, nicht aktiv weiterentwickelt), für die reine Lizenz-/Existenzfrage ausreichend relevant.
- Diverse Preis-/Pricing-Aggregator-Blogs (fast.io, cloudzero.com, finout.io, pecollective.com, felloai.com u.a.) für Kostenkontroll-/Preisangaben — mittlere Vertrauenswürdigkeit (Drittanbieter, aber mit Bezug auf öffentlich nachvollziehbare Preislisten), nur für die grundsätzliche Existenz von Batch-/Caching-Mechanismen herangezogen, nicht für exakte, langfristig gültige Preiszahlen.
- [TermsFeed — GDPR Sensitive Personal Data](https://www.termsfeed.com/blog/gdpr-sensitive-personal-data/), [VeraSafe — GDPR, Photographs, and Special Categories](https://verasafe.com/blog/gdpr-and-photographs-understanding-special-categories-of-personal-data/), [GDPR-Advisor — Children's Data](https://www.gdpr-advisor.com/childrens-data-under-gdpr-special-considerations-and-requirements/) — Rechts-Erklärquellen mittlerer bis guter Vertrauenswürdigkeit (spezialisierte Datenschutz-Ratgeberseiten, keine Primärquelle wie der Gesetzestext selbst), nur zur generischen Einordnung genutzt, nicht anbieterspezifisch.

Hinweis zu geprüften Quellen: In keiner der gesichteten Quellen wurde eine eingebettete Prompt-Injection-Anweisung an den recherchierenden Agenten festgestellt. Alle Inhalte wurden als reine Faktendaten behandelt, nicht als Handlungsanweisung.

### Offene Unsicherheiten

- Tatsächliche Erkennungs-/Bewertungsgenauigkeit jedes lokalen ML-Modells (CLIP-Zero-Shot, Places365, NIMA-Ästhetik-Score, YOLOv8) auf den tatsächlichen Familienfotos des Projekts — **nur durch echten Test mit Projektfotos klärbar**, nicht durch Dokumentations-Recherche.
- Tatsächliche CPU-Laufzeit pro Foto bei mehreren tausend Bildern auf der realen Homeserver-Hardware (analog zum bereits für mediapipe dokumentierten Risiko in ADR 0015) — **nur durch Benchmark auf der Zielmaschine klärbar**.
- Reale Cloud-Kosten für die tatsächliche Projekt-Bibliotheksgröße hängen von konkreter Bildauflösung/Prompt-Länge ab — nur mit echten Testbildern seriös bezifferbar.
- Mistral-DPA-Verfügbarkeit für Einzelperson-/Nicht-Business-Konten: Quellenlage widersprüchlich ("Commercial Customers" vs. "Consumers" nicht eindeutig zugeordnet).
- Replicate: kein eindeutig bestätigter öffentlicher Standard-DPA für Einzelkonten gefunden; unklar, ob reguläre (Nicht-Fine-Tuning-)Prediction-Inputs zum Training verwendet werden.
- Hugging Face Inference Providers: Datenschutz-/Retention-Verhalten hängt vom im Einzelfall gewählten Drittanbieter (von 15+) ab — keine pauschale Aussage möglich, müsste bei tatsächlicher Anbieterwahl separat geprüft werden.
- Anthropic: unklar, ob ein privates Einzelkonto denselben Console-DPA-Zugriffsweg erhält wie ein Business-Konto.
- Rechtliche Einordnung von Familienfotos mit erkennbaren Kindern (Art. 8/Art. 9 DSGVO) bei Einsatz einer Cloud-Gesichtserkennung — bewusst nicht bewertet, nur als Fragestellung dokumentiert.
- YOLOv8/Ultralytics AGPL-3.0: ob eine Bündelung im (öffentlichen) PhotoSort-Repo tatsächlich Offenlegungspflichten auslöst, wäre eine eigene rechtliche Prüfung wert.
- `pyiqa`/IQA-PyTorch "Noncommercial"-Lizenz: ob das für ein privates, nicht-kommerzielles Zwei-Personen-Projekt unproblematisch ist, ist eine Rechtsfrage, nicht abschließend bewertet.
- API-Key-Granularität bei Mistral und Replicate: weniger detailliert dokumentiert als bei Anthropic/Hugging Face — evtl. bei direkter Prüfung der jeweiligen Console präziser klärbar.
