"""Modellkonfidenz je Kategorie: zwei Spalten an photo_category_classifications

specs/features/0299-kategorie-konfidenz-anzeigen.md, decisions/0067-modellkonfidenz-je-kategorie-
anzeige-und-auswertung.md Punkt 3/4.

Rein additiv, keine Datenmigration:

- `detected_category_confidences` (JSON) - die Abbildung `category_key -> Konfidenz in [0, 1]`,
  ausschliesslich mit Schluesseln aus `detected_categories`. Eine ABBILDUNG und kein
  positionsparalleles Array: der Wert haengt am Schluessel und ueberlebt jede Umsortierung der
  Kandidatenliste.
- `category_confidence` (Float) - die Konfidenz zur AUFGELOESTEN Kategorie dieser Zeile, also
  `detected_category_confidences.get(category_key)`. Bewusst redundant zur Abbildung: die
  Statistik-Aggregation muss in SQL laufen (ein `AVG` ueber einen aus JSON extrahierten Wert ist in
  SQLite und PostgreSQL unterschiedlich zu schreiben), und alle Klassifizierungszeilen eines
  Projekts nach Python zu laden vertraegt sich nicht mit der Groessenannahme "mehrere tausend
  Fotos".

NULL-SEMANTIK (der Grund fuer "nullable, aber KEIN server_default"), exakt das Muster der
Kostenspalten aus Revision f4a5b6c7d8e9 / ADR 0051:

    NULL = "nicht erhoben" - die Zeile stammt aus der Zeit VOR dieser Revision, oder das Modell hat
                             zu diesem Schluessel keine brauchbare Zahl geliefert.
    0.0  = "das Modell war sich zu 0 % SICHER" - eine Aussage, keine Abwesenheit.

Ein `server_default` von `0` bzw. `'{}'` naehme den Bestandszeilen genau diese Unterscheidung und
gaebe jeder von ihnen eine Modellaussage, die es nie gab. Es gibt deshalb bewusst KEINEN
server_default und KEINEN Backfill; Akzeptanzkriterium 9 der Spec ("bestehende Klassifizierungs-
zeilen behalten dauerhaft NULL und zeigen keine Angabe") erfuellt sich damit durch die Spaltenform
selbst statt durch eine Sonderbehandlung im Lesepfad. Neue Zeilen bekommen ihre Werte ueber den
produktiven Schreibpfad (worker.py::run_remote_category_classification); der Python-seitige
Modell-Default ist `None`, dasselbe `ScanRun.total_files`-Idiom.

Auch ein erneuter Klassifizierungslauf fuellt den Altbestand nicht nach, weil der Worker jedes Foto
mit vorhandener Klassifizierungszeile ueberspringt (Kostenschutz). "Neu-Klassifizierung erzwingen"
ist ausdruecklich eine eigene Folge-Story.

`sa.Float()` fuer den Skalar (rendert `FLOAT` auf Postgres, laut PostgreSQL-Dokumentation
gleichbedeutend mit DOUBLE PRECISION; `FLOAT` auf SQLite) - derselbe Typ, den alle uebrigen
`Mapped[float]`-Spalten des Datenmodells erzeugen. Kein ganzzahliger Typ: eine Konfidenz von 0.92
wuerde sonst still auf 0 gerundet. `sa.JSON()` fuer die Abbildung, analog `detected_categories`
derselben Tabelle.

`downgrade()` ist verlustbehaftet (die beiden Spaltenwerte gehen verloren), aber schema-
vollstaendig umkehrbar - kein Datenbestand ausserhalb dieser Spalten wird beruehrt.

Revision ID: a3b4c5d6e7f8
Revises: 5ab22032843c
Create Date: 2026-09-09 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "5ab22032843c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("photo_category_classifications") as batch_op:
        batch_op.add_column(sa.Column("detected_category_confidences", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("category_confidence", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("photo_category_classifications") as batch_op:
        batch_op.drop_column("category_confidence")
        batch_op.drop_column("detected_category_confidences")
