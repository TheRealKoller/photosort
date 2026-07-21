import io
from contextlib import redirect_stderr, redirect_stdout

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Connection

from photosort.config import Settings
from photosort.db import Base
from photosort.security import verify_password
from photosort.seed import configured_seed_users, seed_configured_users, users_table


def _make_connection() -> Connection:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine.connect()


def _all_users(conn: Connection) -> list[tuple[str, str]]:
    rows = conn.execute(select(users_table.c.username, users_table.c.password_hash)).all()
    return [(row.username, row.password_hash) for row in rows]


def test_seed_creates_two_users_on_empty_db() -> None:
    with _make_connection() as conn:
        seed_configured_users(conn, [("daniel", "pw-daniel"), ("frau", "pw-frau")])
        conn.commit()

        rows = _all_users(conn)

    assert {username for username, _ in rows} == {"daniel", "frau"}
    hashes = dict(rows)
    assert verify_password("pw-daniel", hashes["daniel"]) is True
    assert verify_password("pw-frau", hashes["frau"]) is True


def test_seed_leaves_existing_user_password_hash_untouched() -> None:
    with _make_connection() as conn:
        seed_configured_users(conn, [("daniel", "original-password")])
        conn.commit()
        original_hash = dict(_all_users(conn))["daniel"]

        # Erneuter Lauf mit geaendertem konfigurierten Passwort - der bestehende Hash darf
        # NICHT ueberschrieben werden, nur der fehlende zweite User wird ergaenzt.
        seed_configured_users(conn, [("daniel", "changed-password"), ("frau", "pw-frau")])
        conn.commit()

        rows = dict(_all_users(conn))

    assert rows["daniel"] == original_hash
    assert verify_password("original-password", rows["daniel"]) is True
    assert "frau" in rows


def test_seed_is_noop_when_both_users_already_exist() -> None:
    with _make_connection() as conn:
        seed_configured_users(conn, [("daniel", "pw-daniel"), ("frau", "pw-frau")])
        conn.commit()

        seed_configured_users(conn, [("daniel", "pw-daniel"), ("frau", "pw-frau")])
        conn.commit()

        rows = _all_users(conn)

    assert len(rows) == 2


def test_seed_never_logs_cleartext_passwords() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    with _make_connection() as conn, redirect_stdout(stdout), redirect_stderr(stderr):
        seed_configured_users(
            conn, [("daniel", "super-secret-cleartext"), ("frau", "other-secret")]
        )
        conn.commit()

    combined_output = stdout.getvalue() + stderr.getvalue()
    assert "super-secret-cleartext" not in combined_output
    assert "other-secret" not in combined_output


def test_configured_seed_users_maps_both_settings_users_in_order() -> None:
    # Regressionsschutz (Review-Fund test-engineer): die Migration selbst
    # (alembic/versions/1574f8180817_seed_auth_users.py) baut die Nutzerliste aus den
    # Settings-Feldern - ein Tippfehler/vertauschtes Feld dort waere durch keinen anderen Test
    # abgesichert, da "alembic upgrade" bewusst nicht in der Testsuite laeuft (siehe
    # architecture/0002-testkonzept.md). configured_seed_users() ist die dafuer ausgelagerte,
    # ohne Alembic-Runtime testbare Zuordnung.
    settings = Settings(
        _env_file=None,
        auth_seed_user1_username="daniel",
        auth_seed_user1_password="pw-daniel",
        auth_seed_user2_username="frau",
        auth_seed_user2_password="pw-frau",
    )

    assert configured_seed_users(settings) == [
        ("daniel", "pw-daniel"),
        ("frau", "pw-frau"),
    ]
