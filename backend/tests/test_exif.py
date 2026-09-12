import io
import logging

import pytest
from PIL import Image
from PIL.ExifTags import IFD
from PIL.TiffImagePlugin import IFDRational

from photosort.cameras import CameraIdentity
from photosort.opencloud.exif import extract_camera, extract_gps, extract_taken_at

_DATETIME_ORIGINAL_TAG = 36867


def _make_jpeg(with_exif_datetime: str | None) -> bytes:
    image = Image.new("RGB", (4, 4), color="red")
    buffer = io.BytesIO()

    if with_exif_datetime is not None:
        exif = image.getexif()
        exif_ifd = exif.get_ifd(IFD.Exif)
        exif_ifd[_DATETIME_ORIGINAL_TAG] = with_exif_datetime
        image.save(buffer, format="JPEG", exif=exif)
    else:
        image.save(buffer, format="JPEG")

    return buffer.getvalue()


def _make_png() -> bytes:
    image = Image.new("RGB", (4, 4), color="blue")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_extracts_datetime_original_from_jpeg_exif() -> None:
    jpeg_bytes = _make_jpeg("2023:08:15 12:30:00")

    taken_at = extract_taken_at(jpeg_bytes)

    assert taken_at is not None
    assert (taken_at.year, taken_at.month, taken_at.day) == (2023, 8, 15)
    assert (taken_at.hour, taken_at.minute, taken_at.second) == (12, 30, 0)


def test_returns_none_for_jpeg_without_exif() -> None:
    jpeg_bytes = _make_jpeg(with_exif_datetime=None)

    assert extract_taken_at(jpeg_bytes) is None


def test_returns_none_for_png_without_exif() -> None:
    assert extract_taken_at(_make_png()) is None


def test_returns_none_for_garbage_bytes() -> None:
    assert extract_taken_at(b"not-an-image") is None


# ---------------------------------------------------------------------------------------------
# specs/features/0051-gps-landmark-cluster-bildung.md, decisions/0072-ortsbezogene-cluster-
# anzeigeort-als-antwortableitung.md Entscheidung 6, Sicherheitskonzept "Standortdaten (GPS aus
# EXIF)": extract_gps als Pendant zu extract_taken_at - best effort, aber MIT
# Plausibilitaetsgrenzen. Der breite `except Exception` allein traegt hier nicht: `IFDRational`
# mit Nenner 0 ergibt bei Pillow 12.3.0 `nan` OHNE jede Exception, und ein durchgelassenes `nan`
# legt ueber Starlettes `allow_nan=False` die gesamte Listenantwort des Projekts auf HTTP 500.


def _make_jpeg_with_gps(gps_values: dict[int, object]) -> bytes:
    """JPEG mit einem GPSInfo-IFD, das GENAU die uebergebenen Tags traegt (1 = GPSLatitudeRef,
    2 = GPSLatitude, 3 = GPSLongitudeRef, 4 = GPSLongitude) - so lassen sich auch unvollstaendige
    und entartete Datensaetze erzeugen, wie sie reale Kameras schreiben."""
    image = Image.new("RGB", (4, 4), color="red")
    exif = image.getexif()
    gps_ifd = exif.get_ifd(IFD.GPSInfo)
    gps_ifd.update(gps_values)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def _dms(degrees: int, minutes: int, seconds: float) -> tuple[object, object, object]:
    return (
        IFDRational(degrees, 1),
        IFDRational(minutes, 1),
        IFDRational(round(seconds * 100), 100),
    )


# Eiffelturm, 48deg51'29.09"N 2deg17'40.90"E - eine bekannte Referenzkoordinate statt eines
# "plausibel aussehenden" Floats (Teststrategie der Spec).
_EIFFEL_LAT_DMS = _dms(48, 51, 29.09)
_EIFFEL_LON_DMS = _dms(2, 17, 40.90)
_EIFFEL_LAT_DECIMAL = 48.858080555555556
_EIFFEL_LON_DECIMAL = 2.2946944444444446


def test_extracts_north_east_coordinates_as_positive_decimal_degrees() -> None:
    jpeg_bytes = _make_jpeg_with_gps({1: "N", 2: _EIFFEL_LAT_DMS, 3: "E", 4: _EIFFEL_LON_DMS})

    coordinate = extract_gps(jpeg_bytes)

    assert coordinate is not None
    lat, lon = coordinate
    assert lat > 0
    assert lon > 0


def test_converts_degrees_minutes_seconds_to_decimal_degrees_at_a_known_reference() -> None:
    """ENGE Toleranz (Teststrategie der Spec): ein Faktorfehler in der Minuten-/Sekunden-Division
    liefert einen Wert, der auf zwei Nachkommastellen noch plausibel aussieht."""
    jpeg_bytes = _make_jpeg_with_gps({1: "N", 2: _EIFFEL_LAT_DMS, 3: "E", 4: _EIFFEL_LON_DMS})

    coordinate = extract_gps(jpeg_bytes)

    assert coordinate is not None
    lat, lon = coordinate
    assert abs(lat - _EIFFEL_LAT_DECIMAL) < 1e-9
    assert abs(lon - _EIFFEL_LON_DECIMAL) < 1e-9


def test_applies_the_sign_flip_for_a_southern_latitude() -> None:
    """Der naheliegendste Fehler ist, den Betrag zu uebernehmen (Teststrategie der Spec) - deshalb
    Sued und West als ZWEI getrennte Faelle, nicht als einer."""
    jpeg_bytes = _make_jpeg_with_gps(
        {1: "S", 2: _dms(33, 51, 24.5), 3: "E", 4: _dms(151, 12, 55.8)}
    )

    coordinate = extract_gps(jpeg_bytes)

    assert coordinate is not None
    lat, lon = coordinate
    assert abs(lat - -33.856805555555556) < 1e-9
    assert lon > 0


def test_applies_the_sign_flip_for_a_western_longitude() -> None:
    jpeg_bytes = _make_jpeg_with_gps({1: "N", 2: _dms(40, 41, 21.0), 3: "W", 4: _dms(74, 2, 40.2)})

    coordinate = extract_gps(jpeg_bytes)

    assert coordinate is not None
    lat, lon = coordinate
    assert lat > 0
    assert abs(lon - -74.04450000000001) < 1e-9


def test_trims_whitespace_and_nul_from_the_reference_and_accepts_lowercase() -> None:
    """Reale Dateien schreiben den Ref als NUL-terminierten ASCII-String; Pillow liefert ihn dann
    als `'S\\x00'`. Ohne Trimmen fiele eine voellig gewoehnliche Suedhalbkugel-Aufnahme durch die
    Ref-Pruefung und verloere ihren Ort."""
    jpeg_bytes = _make_jpeg_with_gps(
        {1: " s\x00", 2: _dms(33, 51, 24.5), 3: "e\x00", 4: _dms(151, 12, 55.8)}
    )

    coordinate = extract_gps(jpeg_bytes)

    assert coordinate is not None
    assert coordinate[0] < 0
    assert coordinate[1] > 0


def test_returns_none_for_a_jpeg_without_a_gps_ifd() -> None:
    assert extract_gps(_make_jpeg("2023:08:15 12:30:00")) is None


def test_returns_none_for_a_jpeg_without_any_exif() -> None:
    assert extract_gps(_make_jpeg(with_exif_datetime=None)) is None


def test_extract_gps_returns_none_for_a_png() -> None:
    assert extract_gps(_make_png()) is None


def test_extract_gps_returns_none_for_garbage_bytes() -> None:
    assert extract_gps(b"not-an-image") is None


def test_returns_none_for_truncated_bytes_without_propagating_an_error() -> None:
    """Das Range-Read-Fenster (`worker.py::_EXIF_RANGE_BYTES`) kann mitten im Datenstrom enden -
    ein einzelnes unlesbares Foto darf einen Scan-Lauf nie abbrechen."""
    jpeg_bytes = _make_jpeg_with_gps({1: "N", 2: _EIFFEL_LAT_DMS, 3: "E", 4: _EIFFEL_LON_DMS})

    assert extract_gps(jpeg_bytes[: len(jpeg_bytes) // 2]) is None


def test_returns_none_when_the_latitude_reference_is_missing() -> None:
    """KEIN stiller Default auf Nord (ADR 0072, Entscheidung 6): die Referenz zu raten spiegelte
    eine Suedhalbkugel-Aufnahme wortlos auf die Nordhalbkugel."""
    jpeg_bytes = _make_jpeg_with_gps({2: _EIFFEL_LAT_DMS, 3: "E", 4: _EIFFEL_LON_DMS})

    assert extract_gps(jpeg_bytes) is None


def test_returns_none_when_the_longitude_reference_is_missing() -> None:
    jpeg_bytes = _make_jpeg_with_gps({1: "N", 2: _EIFFEL_LAT_DMS, 4: _EIFFEL_LON_DMS})

    assert extract_gps(jpeg_bytes) is None


def test_returns_none_for_a_reference_outside_the_four_known_values() -> None:
    jpeg_bytes = _make_jpeg_with_gps({1: "X", 2: _EIFFEL_LAT_DMS, 3: "E", 4: _EIFFEL_LON_DMS})

    assert extract_gps(jpeg_bytes) is None


def test_returns_none_when_latitude_and_longitude_references_are_swapped() -> None:
    """`E` ist als BREITEN-Referenz unzulaessig - die Pruefung laeuft je Komponente gegen ihr
    eigenes Wertepaar, nicht gegen die Vereinigung aller vier Buchstaben."""
    jpeg_bytes = _make_jpeg_with_gps({1: "E", 2: _EIFFEL_LAT_DMS, 3: "N", 4: _EIFFEL_LON_DMS})

    assert extract_gps(jpeg_bytes) is None


def test_returns_none_when_only_the_latitude_is_readable() -> None:
    """Paar-Invariante: BEIDE Werte oder KEINER. Sonst stuende in der Datenbank ein halbes
    Koordinatenpaar und jede spaetere `is not None`-Pruefung muesste beide Spalten einzeln
    kennen."""
    jpeg_bytes = _make_jpeg_with_gps({1: "N", 2: _EIFFEL_LAT_DMS})

    assert extract_gps(jpeg_bytes) is None


def test_returns_none_when_only_the_longitude_is_readable() -> None:
    jpeg_bytes = _make_jpeg_with_gps({3: "E", 4: _EIFFEL_LON_DMS})

    assert extract_gps(jpeg_bytes) is None


def test_returns_none_for_an_ifd_rational_with_a_zero_denominator() -> None:
    """VERIFIZIERT am Projektstand (Pillow 12.3.0): `IFDRational(x, 0)` ergibt `nan` OHNE jede
    Exception, und `nan` propagiert durch die DMS-Arithmetik. Der breite `except Exception` sieht
    das nicht - nur der Bereichsvergleich faengt es ab. Ein durchgelassenes `nan` in
    `Photo.gps_lat` legt ueber Starlettes `allow_nan=False` die GESAMTE Listenantwort des Projekts
    dauerhaft auf HTTP 500."""
    jpeg_bytes = _make_jpeg_with_gps(
        {
            1: "N",
            2: (IFDRational(48, 1), IFDRational(51, 1), IFDRational(5, 0)),
            3: "E",
            4: _EIFFEL_LON_DMS,
        }
    )

    assert extract_gps(jpeg_bytes) is None


def test_returns_none_for_a_latitude_beyond_ninety_degrees() -> None:
    jpeg_bytes = _make_jpeg_with_gps({1: "N", 2: _dms(91, 0, 0.0), 3: "E", 4: _EIFFEL_LON_DMS})

    assert extract_gps(jpeg_bytes) is None


def test_returns_none_for_a_longitude_beyond_one_hundred_eighty_degrees() -> None:
    jpeg_bytes = _make_jpeg_with_gps({1: "N", 2: _EIFFEL_LAT_DMS, 3: "E", 4: _dms(181, 0, 0.0)})

    assert extract_gps(jpeg_bytes) is None


def test_accepts_the_exact_boundary_values() -> None:
    """Der Bereichsvergleich ist inklusiv - der Nordpol und der 180. Meridian sind gueltige Orte,
    keine Fehlerfaelle."""
    jpeg_bytes = _make_jpeg_with_gps({1: "N", 2: _dms(90, 0, 0.0), 3: "E", 4: _dms(180, 0, 0.0)})

    assert extract_gps(jpeg_bytes) == (90.0, 180.0)


def test_discards_the_exact_null_island_pair() -> None:
    """Bekanntes Kamera-Artefakt bei fehlgeschlagenem Fix (ADR 0072, Entscheidung 6): das Paar
    liegt im gueltigen Bereich, ist aber keine Ortsangabe - und risse sein Cluster bei 500 m
    Schwelle gleich ZWEIMAL auf, beim Hinein- und beim Hinauslaufen."""
    jpeg_bytes = _make_jpeg_with_gps({1: "N", 2: _dms(0, 0, 0.0), 3: "E", 4: _dms(0, 0, 0.0)})

    assert extract_gps(jpeg_bytes) is None


def test_keeps_a_coordinate_with_only_one_zero_component() -> None:
    """Verworfen wird AUSSCHLIESSLICH das exakte Doppel-Null-Paar. Der Nullmeridian bzw. der
    Aequator allein bleiben gueltige Orte."""
    jpeg_bytes = _make_jpeg_with_gps({1: "N", 2: _EIFFEL_LAT_DMS, 3: "E", 4: _dms(0, 0, 0.0)})

    coordinate = extract_gps(jpeg_bytes)

    assert coordinate is not None
    assert coordinate[1] == 0.0


def test_returns_none_when_both_references_are_present_but_the_values_are_missing() -> None:
    """Ein GPS-IFD, das nur die beiden Referenzbuchstaben traegt - der Datensatz ist damit
    strukturell vorhanden, aber ohne jede Zahl. Kein Fehler nach aussen, nur "kein Ort"."""
    jpeg_bytes = _make_jpeg_with_gps({1: "N", 3: "E"})

    assert extract_gps(jpeg_bytes) is None


def test_returns_none_when_the_dms_tuple_does_not_have_three_components() -> None:
    jpeg_bytes = _make_jpeg_with_gps(
        {1: "N", 2: (IFDRational(48, 1), IFDRational(51, 1)), 3: "E", 4: _EIFFEL_LON_DMS}
    )

    assert extract_gps(jpeg_bytes) is None


def test_no_coordinate_value_ever_reaches_the_log(caplog: pytest.LogCaptureFixture) -> None:
    """Muss-Kriterium des Sicherheitskonzepts ("Koordinaten gehoeren nie in ein Log"): eine
    Logzeile ist eine schwaecher geschuetzte, laenger lebende Oberflaeche als die Datenbank. Die
    Zeile traegt ausschliesslich ein FESTES Grund-Token und die `photo_id` - weder der akzeptierte
    noch der verworfene Rohwert."""
    jpeg_bytes = _make_jpeg_with_gps({1: "N", 2: _dms(91, 0, 0.0), 3: "E", 4: _dms(179, 12, 55.8)})

    with caplog.at_level(logging.WARNING):
        assert extract_gps(jpeg_bytes, photo_id=4711) is None

    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "ausserhalb_intervall" in message
    assert "4711" in message
    for fragment in ("91", "179", "55.8", "12"):
        assert fragment not in message, fragment


def test_a_photo_without_a_gps_ifd_logs_nothing_at_all(caplog: pytest.LogCaptureFixture) -> None:
    """Der Normalfall (kein GPS im EXIF) ist kein Befund: ein Scan ueber tausende Fotos ohne
    Ortsangabe darf keine einzige Zeile erzeugen."""
    with caplog.at_level(logging.WARNING):
        assert extract_gps(_make_jpeg("2023:08:15 12:30:00"), photo_id=1) is None

    assert caplog.records == []


def test_an_accepted_coordinate_logs_nothing_at_all(caplog: pytest.LogCaptureFixture) -> None:
    """Auch der AKZEPTIERTE Wert wird nicht geloggt - der Erfolgsfall ist genau der, in dem die
    Koordinate tatsaechlich vorliegt."""
    jpeg_bytes = _make_jpeg_with_gps({1: "N", 2: _EIFFEL_LAT_DMS, 3: "E", 4: _EIFFEL_LON_DMS})

    with caplog.at_level(logging.WARNING):
        assert extract_gps(jpeg_bytes, photo_id=1) is not None

    assert caplog.records == []


def test_a_missing_reference_logs_its_own_reason_token(caplog: pytest.LogCaptureFixture) -> None:
    jpeg_bytes = _make_jpeg_with_gps({2: _EIFFEL_LAT_DMS, 3: "E", 4: _EIFFEL_LON_DMS})

    with caplog.at_level(logging.WARNING):
        assert extract_gps(jpeg_bytes, photo_id=9) is None

    assert len(caplog.records) == 1
    assert "ref_fehlt" in caplog.records[0].getMessage()


def test_an_unusable_dms_value_logs_its_own_reason_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    jpeg_bytes = _make_jpeg_with_gps(
        {1: "N", 2: (IFDRational(48, 1), IFDRational(51, 1)), 3: "E", 4: _EIFFEL_LON_DMS}
    )

    with caplog.at_level(logging.WARNING):
        assert extract_gps(jpeg_bytes, photo_id=9) is None

    assert len(caplog.records) == 1
    assert "nicht_numerisch" in caplog.records[0].getMessage()


def test_the_null_island_pair_logs_its_own_reason_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ein eigenes festes Token statt einer Einordnung unter `ausserhalb_intervall`: das Paar
    LIEGT im gueltigen Intervall, und "Geraet hatte keinen Fix" ist eine andere Fehlerklasse als
    "Parser hat Unsinn gelesen". Kein Fremdtext, dieselbe Log-Injection-Freiheit."""
    jpeg_bytes = _make_jpeg_with_gps({1: "N", 2: _dms(0, 0, 0.0), 3: "E", 4: _dms(0, 0, 0.0)})

    with caplog.at_level(logging.WARNING):
        assert extract_gps(jpeg_bytes, photo_id=9) is None

    assert len(caplog.records) == 1
    assert "nullinsel" in caplog.records[0].getMessage()


# ---------------------------------------------------------------------------------------------
# specs/features/0426-zeitversatz-je-kamera.md, decisions/0089 Punkt 3: extract_camera liest
# `Make` (271) und `Model` (272) aus DEMSELBEN Range-Read-Fenster wie Zeit und Koordinate - kein
# zusaetzlicher Netzwerkzugriff. Best-effort wie die beiden Nachbarn: kein Lesefehler bricht
# einen Scan ab.

_MAKE_TAG = 271
_MODEL_TAG = 272


def _make_jpeg_with_camera(camera_values: dict[int, object]) -> bytes:
    """JPEG, dessen Basis-IFD GENAU die uebergebenen Kamera-Tags traegt - so lassen sich auch
    unvollstaendige und entartete Datensaetze erzeugen, wie sie reale Kameras schreiben."""
    image = Image.new("RGB", (4, 4), color="red")
    exif = image.getexif()
    exif.update(camera_values)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def test_extracts_make_and_model_as_a_camera_identity() -> None:
    jpeg_bytes = _make_jpeg_with_camera({_MAKE_TAG: "Canon", _MODEL_TAG: "Canon EOS 5D"})

    assert extract_camera(jpeg_bytes) == CameraIdentity(make="Canon", model="Canon EOS 5D")


def test_reads_the_camera_from_the_same_window_as_time_and_coordinate() -> None:
    """Die tragende Zusage von Umsetzungsschritt 3: EIN Byte-Fenster, drei Auswertungen."""
    image = Image.new("RGB", (4, 4), color="red")
    exif = image.getexif()
    exif.update({_MAKE_TAG: "Canon", _MODEL_TAG: "EOS 5D"})
    exif.get_ifd(IFD.Exif)[_DATETIME_ORIGINAL_TAG] = "2026:08:12 14:32:00"
    exif.get_ifd(IFD.GPSInfo).update({1: "N", 2: _EIFFEL_LAT_DMS, 3: "E", 4: _EIFFEL_LON_DMS})
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    content = buffer.getvalue()

    assert extract_camera(content) == CameraIdentity(make="Canon", model="EOS 5D")
    assert extract_taken_at(content) is not None
    assert extract_gps(content) is not None


def test_only_make_is_enough_for_a_camera_identity() -> None:
    jpeg_bytes = _make_jpeg_with_camera({_MAKE_TAG: "Canon"})

    assert extract_camera(jpeg_bytes) == CameraIdentity(make="Canon", model="")


def test_only_model_is_enough_for_a_camera_identity() -> None:
    jpeg_bytes = _make_jpeg_with_camera({_MODEL_TAG: "EOS 5D"})

    assert extract_camera(jpeg_bytes) == CameraIdentity(make="", model="EOS 5D")


def test_returns_none_when_both_make_and_model_are_missing() -> None:
    assert extract_camera(_make_jpeg("2023:08:15 12:30:00")) is None


def test_extract_camera_returns_none_for_a_jpeg_without_any_exif() -> None:
    assert extract_camera(_make_jpeg(with_exif_datetime=None)) is None


def test_extract_camera_returns_none_for_a_png() -> None:
    assert extract_camera(_make_png()) is None


def test_extract_camera_returns_none_for_garbage_bytes() -> None:
    assert extract_camera(b"not-an-image") is None


def test_extract_camera_returns_none_for_truncated_bytes_without_an_error() -> None:
    """Ein abgeschnittenes Range-Read-Fenster ist bei grossen Dateien der Regelfall - es darf
    keine Ausnahme nach aussen tragen."""
    jpeg_bytes = _make_jpeg_with_camera({_MAKE_TAG: "Canon", _MODEL_TAG: "EOS 5D"})

    assert extract_camera(jpeg_bytes[:20]) is None


def test_a_numeric_value_arrives_as_its_ascii_form_because_the_tag_is_ascii() -> None:
    """Verifiziert gegen Pillow 12.3.0: `Make`/`Model` sind ASCII-Tags, ein geschriebener `int`
    kommt als `'42'` zurueck - nicht als `int`. Der Nicht-`str`-Zweig von `camera_identity` ist
    deshalb ueber eine echte Datei gar nicht erreichbar und dort direkt getestet
    (test_cameras.py); hier steht, was ueber diesen Weg tatsaechlich ankommt."""
    jpeg_bytes = _make_jpeg_with_camera({_MAKE_TAG: 42, _MODEL_TAG: "EOS 5D"})

    assert extract_camera(jpeg_bytes) == CameraIdentity(make="42", model="EOS 5D")


def test_an_undecodable_raw_value_is_discarded_without_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Rohwert eines entarteten Datensatzes kann jeden Typ tragen (Pillow liefert bei einem
    abweichenden Feldtyp z.B. `bytes`). Er wird VERWORFEN statt umgedeutet - und kein Typfehler
    traegt nach aussen. Ueber Pillows Schreibweg nicht erzeugbar, deshalb am Leseaufruf gesetzt."""
    jpeg_bytes = _make_jpeg_with_camera({_MAKE_TAG: "Canon", _MODEL_TAG: "EOS 5D"})

    def _degenerate_get(self: object, tag: int, default: object = None) -> object:
        return b"\x01\x02" if tag == _MAKE_TAG else "EOS 5D"

    monkeypatch.setattr(Image.Exif, "get", _degenerate_get, raising=True)

    assert extract_camera(jpeg_bytes) == CameraIdentity(make="", model="EOS 5D")


def test_an_accepted_camera_logs_nothing_at_all(caplog: pytest.LogCaptureFixture) -> None:
    jpeg_bytes = _make_jpeg_with_camera({_MAKE_TAG: "Canon", _MODEL_TAG: "EOS 5D"})

    with caplog.at_level(logging.WARNING):
        assert extract_camera(jpeg_bytes, photo_id=1) is not None

    assert caplog.records == []


def test_a_photo_without_camera_tags_logs_nothing_at_all(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Der Normalfall (keine Kamera-Angabe im EXIF) ist kein Befund - ein Scan ueber tausende
    solcher Fotos bleibt still."""
    with caplog.at_level(logging.WARNING):
        assert extract_camera(_make_jpeg("2023:08:15 12:30:00"), photo_id=1) is None

    assert caplog.records == []


def test_a_discarded_camera_logs_a_fixed_reason_token_without_the_raw_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Nur im VERWERFUNGSFALL eine Zeile, und in ihr ausschliesslich ein festes Grund-Token plus
    `photo_id`. `Make`/`Model` sind Fremdtext aus einer Kamera-Firmware: ein Rohwert im Log ist
    eine Log-Injection-Flaeche, und die FEHLERKLASSE traegt den vollen Diagnosewert."""
    jpeg_bytes = _make_jpeg_with_camera({_MAKE_TAG: "M" * 300, _MODEL_TAG: "X" * 300})

    with caplog.at_level(logging.WARNING):
        assert extract_camera(jpeg_bytes, photo_id=4711) is None

    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "verworfen" in message
    assert "4711" in message
    assert "MMM" not in message
    assert "XXX" not in message
