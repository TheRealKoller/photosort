# 0140 - Eye-Übersetzung v2: Lauf-Fassung, Tiererkennung als Motivsignal, Fassung je Ergebnis

**Status:** Accepted
**Teilweise abgelöst:** Punkt 1 (v2 ist die Lauf-Fassung) und Punkt 6 (Pins umfassen die
Motiv-Tags) durch ADR
[`0141`](./0141-eye-uebersetzung-v3-definierende-signale-support.md); alle übrigen Punkte gelten
weiter.
**Datum:** 2026-11-07
**Bezug:** Issue [#615](https://github.com/TheRealKoller/photosort/issues/615), Spec
[`0615`](../features/0615-eye-uebersetzung-v2.md), ADR
[`0138`](./0138-eye-als-dritte-grundlage-sidecar-schattentabellen.md) (Punkt 3 teilweise abgelöst),
ADR [`0139`](./0139-pruefung-von-klassifizierungsverfahren-in-der-app.md) (Punkt 5, Fassungen)

## Kontext

Die Eye-Übersetzung `eye-4.2.3/v1` schließt über zwölf Fotoarten aus, kennt als Tiere nur vier
Arten und als Aktivität nur Sportarten. An einer Eye-Ergebniszeile ist nicht erkennbar, mit
welcher Fassung sie entstand. Eye liefert die Fotoart nur als `kind` (wahrscheinlichste Art);
`details.photo.type` serialisiert der Sidecar nicht.

## Entscheidung

### 1. v2 neben v1; v2 ist die Lauf-Fassung; `analyze` ohne Default

`eye-4.2.3/v2` ist ein zweiter Eintrag in `MAPPINGS`; v1 bleibt wertgleich und als
`MAPPING_VERSION_V1` aufrufbar. `MAPPING_VERSION` ist die Fassung, die der Eye-Lauf rechnet
(v2), und `EYE_PURPOSE_MAPPING` beschreibt sie. `analyze(payload, version)` hat keinen Default:
Der Worker übergibt `MAPPING_VERSION`, die Klassifizierungsprüfung die gespeicherte Fassung ihrer
Seite. Fehlt diese, entsteht `EyeMappingError` statt eines Rückfalls auf die Lauf-Fassung — sonst
rechnete eine alte Prüfseite still mit einer anderen Fassung, als sie angibt.

### 2. `pets` als zweites Motivsignal, nur für Tiere

Löst ADR 0138 Punkt 3 („Stärke als größte Konfidenz der zugeordneten Tags“) für Tiere ab: Die
Stärke ist das Maximum aus Tag-Konfidenzen und der größten `confidence` in `pets`. `EyeMapping`
trägt dafür `motif_detections` (v2 `{"tiere": "pets"}`, v1 leer). **Was gilt:** ein fehlendes,
nicht-listenförmiges oder fehlerhaftes `pets` (nicht numerisch, `bool`, NaN, unendlich) zählt als
0, Werte werden auf [0, 1] geklemmt. **Bei Verletzung:** eine einzelne kaputte Sidecar-Antwort
bricht den Lauf ab oder schreibt eine Stärke außerhalb des Wertebereichs.

### 3. Ausschluss nur über `kind`, mit fester Kernmenge

v2 schließt aus, wenn `kind` einer von `document`, `screenshot`, `receipt`, `photo_of_screen`,
`id_card` ist. Fehlendes oder unbekanntes `kind` schließt nicht aus. Ein Hintergrund- oder
Flächensignal gibt es ohne Sidecar-Umbau nicht; ein Bildschirmfoto, das Eye als `photo` einstuft,
bleibt eingeschlossen.

### 4. Feinlabel-Filter von der Ausschlussmenge entkoppelt

`EyeMapping.fine_label_excluded` hält in beiden Fassungen die bisherigen zwölf Fotoarten.
`fine_labels` filtert darüber, damit ein schmalerer Ausschluss die Feinlabels nicht verändert.

### 5. `mapping_version` je Ergebniszeile

`photo_eye_results.mapping_version` (String, NOT NULL, ohne bleibenden Default). Bestehende Zeilen
erhalten `eye-4.2.3/v1` — sie sind alle mit v1 entstanden — und werden nicht neu berechnet.

### 6. Pins sind die Vereinigung aller Fassungen

`eye/src/pins.json::mappingTags` ist die Vereinigung der Motiv-Tags aller registrierten
Fassungen. **Bei Verletzung:** ein Pin-Wechsel prüft eine aufrufbare Fassung nicht mit und
liefert für sie still Nullen.

## Konsequenzen

- Alte Ergebnisse bleiben v1, bis ein Eye-Lauf sie ersetzt.
- Jede künftige Fassung erweitert dieselbe Pin-Vereinigung.
- Eine Typwahrscheinlichkeit setzt einen Sidecar-Umbau voraus; er ist nicht Teil dieser
  Entscheidung.
