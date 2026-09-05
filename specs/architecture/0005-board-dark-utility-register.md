# 0005 - Figma-Board "Dark Utility Register" (photosort-design-system V1.2)

**Status:** Referenz (Momentaufnahme, kein Living Document)
**Ausgelesen:** 2026-09-04
**Quelle:** Figma-Datei „Photosort Dark", fileKey `zFiuhI1yjTzAQVQnceBiLC`, Board-Node `2:4`
([Link](https://www.figma.com/design/zFiuhI1yjTzAQVQnceBiLC/Photosort-Dark?node-id=2-4))
**Bezug:** Spec [`0320`](../features/0320-dark-utility-register.md), ADR [`0055`](../decisions/0055-dark-utility-register-fundament.md), Stufe 2 = Issue #321

Ausgelesen über den Figma-MCP (`get_metadata` + `get_design_context`). **Diese Datei ist die
maßgebliche Werteliste im Repo** — die Figma-Asset-URLs des Exports verfallen nach 7 Tagen, und
die Fachagenten haben keinen Figma-Zugriff. Sie hält den Stand V1.2 fest; sie wird *nicht*
laufend gepflegt. Was das Projekt daraus verbindlich übernimmt (inklusive der begründeten
Abweichungen), steht in ADR 0055 und im Design-System-Dokument
[`0004`](./0004-design-system.md) — bei Widerspruch gilt die ADR, nicht diese Momentaufnahme.

## 1. Farbpalette (die 12 benannten Tokens des Boards)

### Hintergrund & Oberflächen
| Board-Name | Hex | Zweck laut Board |
|---|---|---|
| Hintergrund | `#0B0C10` | Tiefstes Schwarz für den Bildfokus |
| Oberfläche | `#14161F` | Standard-Container und Paneele |
| Erhöht | `#1E2230` | Karten und schwebende Popups |
| Overlay | `#262B3D` | Modale Dialoge und Tooltips |

### Akzente & Status
| Board-Name | Hex | Zweck laut Board |
|---|---|---|
| Akzent Primär | `#FFB000` | Auswahl & Favoriten |
| Info | `#00E5FF` | Informationszustände & Tipps |
| Aussortiert | `#FF3D00` | Gekennzeichnet für Löschung |
| Album-würdig | `#00E676` | Bestätigt für Export/Alben |

### Typografie-Farben
| Board-Name | Hex | Zweck laut Board |
|---|---|---|
| Text Primär | `#FFFFFF` | Hoher Kontrast, reines Weiß |
| Text Sekundär | `#A0A5B5` | Standard-Fließtext & Labels |
| Text Muted | `#62677A` | Inaktive Metadaten & Hotkeys |
| Text Disabled | `#3E4252` | Deaktivierte Oberflächentexte |

### Nicht als Swatch dokumentiert, aber durchgängig verwendet
| Zweck | Hex | Fundstellen |
|---|---|---|
| Rahmen / Trennlinie | `#2A2E3D` | Panels, Karten, Sekundär-Button, Eingabefeld, Nav, Icon-Kacheln |
| Sekundär-Button gedrückt / Ghost gedrückt / Progress-Spur | `#2A2E3D` | s.u. |

### Kategorie-Chip-Farbpaare (Board zeigt 5 Beispiele, eigene Paare außerhalb der 12 Tokens)
| Kategorie | Fläche | Schrift |
|---|---|---|
| Menschen | `#4D3814` | `#FFC107` |
| Tiere | `#163E3C` | `#00F5D4` |
| Landschaft | `#1F2B49` | `#00B4D8` |
| Gebäude | `#3B1F43` | `#FF007F` |
| Essen | `#143C22` | `#70E000` |

## 2. Kontrastmatrix (berechnet, WCAG 2.x relative Luminanz)

| Vordergrund | auf #0B0C10 | auf #14161F | auf #1E2230 | auf #262B3D |
|---|---|---|---|---|
| Text Primär `#FFFFFF` | 19.55 | 18.04 | 15.83 | 14.04 |
| Text Sekundär `#A0A5B5` | 7.95 | 7.34 | 6.44 | 5.71 |
| **Text Muted `#62677A`** | **3.48** | **3.21** | **2.82** | **2.50** |
| **Text Disabled `#3E4252`** | **1.96** | **1.81** | **1.59** | **1.41** |
| Akzent Primär `#FFB000` | 10.67 | 9.84 | 8.64 | 7.67 |
| Info `#00E5FF` | 12.71 | 11.73 | 10.29 | 9.13 |
| **Aussortiert `#FF3D00`** | 5.51 | 5.08 | **4.46** | **3.96** |
| **Rahmen `#2A2E3D`** | **1.45** | **1.34** | **1.17** | **1.04** |

Beschriftung auf gefüllter Fläche:
- Tinte `#0B0C10` auf Akzent `#FFB000`: **10.67** ✓
- Tinte `#0B0C10` auf Album `#00E676`: **11.71** ✓
- Tinte `#0B0C10` auf Info `#00E5FF`: **12.71** ✓
- **Weiß `#FFFFFF` auf Aussortiert `#FF3D00`: 3.55** ✗ (Board benutzt genau das im Badge "AUSGESONDERT", 10px)
- Tinte `#0B0C10` auf Aussortiert `#FF3D00`: **5.51** ✓

### Konflikte Board ↔ Akzeptanzkriterium "jede Text-/Symbolfarbe erreicht WCAG-AA"

> **Aufgelöst in ADR 0055 Punkt 4.** Die folgenden Konflikte sind Befunde am Board, nicht der
> Projektstand. Insbesondere gilt im Projekt **`--text-muted` = `#8D92A4`** (aufgehellt) statt des
> Board-Werts `#62677A`, und **`--border-control` = `#727891`** statt des Board-Rahmens `#2A2E3D`
> an Bedienelementen. Ein sechster, unten nicht gelisteter Konflikt betrifft den Kategorie-Chip
> „Gebäude" (`#FF007F` auf `#3B1F43` = 3,80 → korrigiert auf `#FF44A1`).
1. **Text Muted** verfehlt 4,5:1 auf allen vier Gründen — das Board setzt es aber für echten Fließtext ein (Panel-Überschriften „SCHALTFLÄCHEN (BUTTONS)", Tabellenköpfe „Typ / Status", Karten-Status „Neu", inaktive Stepper-Stufe „4. Vorschlag").
2. **Text Disabled** liegt überall unter 3:1. WCAG 1.4.3 nimmt inaktive Bedienelemente ausdrücklich aus — als bewusste, dokumentierte Ausnahme vertretbar.
3. **Rahmen `#2A2E3D`** liegt weit unter 3:1. Als reine Dekorationslinie zulässig, **nicht** als einziger Umriss eines Bedienelements — das Board nutzt ihn aber genau so bei Sekundär-Button und Eingabefeld (AK fordert 3:1 für „Bedienelement-Umrisse").
4. **Aussortiert `#FF3D00`** erreicht auf Erhöht/Overlay nur 4,46 / 3,96 — für Fließtext zu wenig, grafisch (3:1) ausreichend.
5. **Weiß auf Aussortiert-Fläche** (3,55) verfehlt AA; dunkle Tinte darauf erreicht 5,51.

## 3. Typografie

Schriftfamilien: **Inter** (serifenlos, alle Texte), **JetBrains Mono** (dicktengleich, Datenausgaben).

| Stufe | Schnitt | Größe | Zeilenhöhe | Laufweite |
|---|---|---|---|---|
| Überschrift 1 | Inter Bold | 64px | auto | −2 % |
| Überschrift 2 | Inter Semi-Bold | 40px | 1.1 | — |
| Überschrift 3 | Inter Regular | 24px | 1.5 | — |
| Fließtext | Inter Medium | 20px | 1.5 | — |
| Fließtext Klein | Inter Regular | 16px | 1.5 | — |
| Beschriftung | Inter Semi-Bold | 12px | — | Uppercase |
| Monospace / Daten | JetBrains Mono Regular | 14px | — | — |

Hinweis: In den Komponenten selbst nutzt das Board zusätzlich 10/11/13/18px — das sind
Ausarbeitungsgrößen des Desktop-Entwurfs, keine dokumentierten Stufen.

## 4. Abstände und Raster

8-Punkt-Raster: **4 (XXS) · 8 (XS) · 12 (S) · 16 (SM) · 24 (M) · 32 (L) · 48 (XL) · 64 (XXL)**.

12-Spalten-Raster: Spaltenbreite flüssig (fill-parent), **Gutter 12px**.

## 5. Formsprache — Radien (aus den Knoten ausgelesen)

| Radius | Verwendung im Board |
|---|---|
| `4px` | Hotkey-Kästchen, Fortschrittsbalken (Spur und Füllung), Auswahlpunkt |
| `6px` | Buttons (alle Ausprägungen), Eingabefelder, Bewertungs-Pillen, Karten-Badge |
| `8px` | Toast, Navigationselement, Icon-Kachel, Kosten-Zeile, Bildfläche in der Karte, Bewertungsleisten-Container |
| `12px` | Panels, Foto-Karten |
| `16px` | Modal-Dialog, **Kategorie-Chips** (einzige Pillenform, die bleibt) |

Keine vollrunden Pillen mehr außer den Kategorie-Chips.

## 6. Grundelemente — konkrete Zustandswerte

### Schaltflächen (Padding durchgängig 16px/8px, Radius 6px, Inter Semi-Bold 12px)
| Ausprägung | Normal | Überfahren | Gedrückt |
|---|---|---|---|
| Primär | Fläche `#FFB000`, Schrift `#0B0C10` | dieselbe Fläche, Deckkraft 85 % | dieselbe Fläche, Deckkraft 70 % |
| Sekundär | Fläche `#262B3D`, Rand `#2A2E3D`, Schrift `#FFFFFF` | Deckkraft 80 % | Fläche `#2A2E3D`, Schrift `#A0A5B5` |
| Unaufdringlich (Ghost) | ohne Fläche, Schrift `#A0A5B5`, Inter Medium | Fläche `#262B3D`, Schrift `#FFFFFF` | Fläche `#2A2E3D`, Schrift `#62677A` |
| Deaktiviert | Fläche `#14161F`, Rand `#2A2E3D`, Schrift `#3E4252`, Deckkraft 40 % | — | — |

Höhe im Board: **31px** (Desktop-Entwurf).

### Schalter (Toggle)
48 × 24px, Knauf 20px, Radius vollrund. Aus: Knauf links; Ein: Knauf rechts.

### Eingabefelder (Radius 6px, Polsterung 12px, Fläche `#14161F`, Schrift 14px)
- Normal: Rand `#2A2E3D` (1px), Text `#A0A5B5`
- Fokussiert: Rand `#FFB000` (1,5px), Text `#FFFFFF`, Textmarke `#FFB000` (2 × 16px)
- Fehlerhaft: Rand `#FF3D00` (1px), Text `#FFFFFF`, Beschriftung + Meldung in `#FF3D00`

### Karten (Foto-Karte, Radius 12px, Fläche `#1E2230`, Rand `#2A2E3D`, Polsterung 12px)
Bildfläche 120px hoch, Radius 8px. Statuszustände:
- Neu: kein Badge, Status „Neu" in `#62677A`
- Favorit: Badge `FAVORIT` (Fläche `#FFB000`, Schrift `#0B0C10`, 10px Bold, Radius 6px) + `star`-Symbol 14px
- Album: Badge `ALBUM` (Fläche `#00E676`, Schrift `#0B0C10`) + `book`-Symbol 14px
- Aussortiert: Badge `AUSGESONDERT` (Fläche `#FF3D00`, Schrift weiß) + `x-circle`-Symbol, Dateiname **durchgestrichen** in `#3E4252`, ganze Karte Deckkraft 40 %
- Ausgewählt: Rand 2px `#FFB000`, Dateiname `#FFB000` Bold, 8px-Punkt in `#FFB000`

**Wichtig für „ohne Farbwahrnehmung unterscheidbar":** Das Board trägt die Bedeutung bereits
dreifach — Textbadge, eigenes Symbol, zusätzlich Durchstreichung/Deckkraft beim Aussortierten.

### Kennzeichen und Kategorie-Chips
Chips: Polsterung 12px/6px, Radius 16px, Inter Semi-Bold 12px, Farbpaar je Kategorie (s.o.).

### Bewertungsleiste
Container Fläche `#14161F`, Radius 8px, Polsterung 8px, Abstand 12px.
Je Eintrag: Fläche `#1E2230`, Radius 6px, 12px/6px, Symbol 16px + Beschriftung (Inter Semi-Bold
12px, weiß) + Hotkey-Kästchen (Fläche `#262B3D`, Radius 4px, JetBrains Mono 10px, Schrift in der
jeweiligen Zustandsfarbe: F → `#FFB000`, A → `#00E676`, X → `#FF3D00`).

### Fortschrittsanzeige mit Prozessstufen
Spur `#2A2E3D`, Füllung `#FFB000`, Höhe 8px, Radius 4px.
Kopfzeile: Beschriftung weiß 13px + Prozentwert JetBrains Mono `#FFB000`.
Stufenzeile 11px: erledigt/kommend `#A0A5B5`, **aktuelle Stufe Inter Bold `#FFB000`**,
noch nicht begonnen `#62677A`.

### Hinweis- und Meldungselemente (Toasts)
Fläche `#1E2230`, Radius 8px, Polsterung 12px, Abstand 12px, Symbol 18px, farbiger Rand 1px:
- Erfolg: Rand `#00E676`, Symbol `check`
- Warnung: Rand `#FFB000`, Symbol `star`
- Fehler: Rand `#FF3D00`, Symbol `x-circle`
Titel Inter Semi-Bold 13px weiß, Beitext Inter Regular 11px `#A0A5B5`.

### Überlagerungen (Modal)
Fläche `#262B3D`, Rand `#2A2E3D`, Radius 16px, Polsterung 24px, Abstand 20px.
Titelzeile: Symbol 24px + Inter Bold 18px weiß. Text Inter Regular 14px `#A0A5B5`, Zeilenhöhe 1.5.
Hervorgehobene Zeile (z.B. Kosten): Fläche `#14161F`, Rand `#2A2E3D`, Radius 8px, Polsterung 12px.
Schaltflächenzeile rechtsbündig, Abstand 12px.

### Navigationselement (Sidebar)
Radius 8px, 16px/8px, Symbol 16px + 13px Text.
- Ruhend: Fläche `#14161F`, Rand `#2A2E3D`, Text `#A0A5B5`
- Überfahren: Fläche `#262B3D`, Text `#FFFFFF`
- Aktiv: Fläche `#262B3D`, Rand 1,5px `#FFB000`, Text Inter Bold `#FFB000`

## 7. Ikonografie — die 12 Symbole

`star` · `book` · `x-circle` · `cog` · `image` · `check` · `info` · `chevron-down` · `search` ·
`folder` · `camera` · `tag`

Beschriftung im Board: Favorit, Album, Aussortiert, Einstellungen, Bild, Bestätigt, Information,
Dropdown, Suche, Ordner, Kamera, Tag/Etikett.

Form: 24 × 24 viewBox, Strichstärke 2, runde Enden, im Lucide-Stil (`star` ist als Pfad
ausgearbeitet). Die exportierten SVGs tragen harte `stroke="white"` bzw. Füllwerte — für die
Einfärbbarkeit über die Tokens muss das auf `currentColor` umgestellt werden; die Geometrie
bleibt dabei unangetastet.

**Abgleich mit Lucide (2026-09-04):** Alle zwölf Board-SVGs sind **Lucide-Pfade** — der
Figma-Export hat lediglich die Bögen in kubische Béziers aufgelöst und `star` in Gegenrichtung
gezeichnet; die Stützpunkte sind identisch. Es gibt damit keine Geometrie-Abweichung zwischen
Board und `lucide-react`, und die Original-SVGs müssen nicht im Repo vorgehalten werden
(ADR 0055 Punkt 7a). Die Zuordnung der Board-Namen auf die Lucide-Exportnamen — inklusive der
Fallen `x-circle`→`CircleX` und `image`→`Image as ImageIcon` — steht in ADR 0055 Punkt 7b.

## 8. Weitere Randbedingungen aus dem Board

- Fußzeile des Boards: „ENTWICKELT FÜR MOBILE PWA UND DESKTOP CLIENTS" — der Entwurf selbst ist
  aber durchgängig in Desktop-Maßen ausgearbeitet (Buttons 31px hoch, Bewertungspillen 29px).
  WCAG 2.2 „Target Size (Minimum)" (AA) verlangt 24 × 24 CSS-Pixel; das Board erfüllt das,
  bleibt aber unter den 44px, die für sicheres Treffen mit dem Finger üblich sind.
- Das Board kennt **keinen** hellen Modus.
