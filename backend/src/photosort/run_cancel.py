"""Kooperativer Abbruch eines Laufs: Merker-Lesung, Kontext-Token und unterbrechbare Wartezeiten.

Die API setzt `cancel_requested_at` an der Laufzeile; der Worker liest den Merker an seinen
Pruefpunkten frisch (`cancel_requested`) und beendet den Lauf dort. Wartezeiten, die laenger
dauern koennen als ein Element (Drosselung und 429-Wiederholung in `cloud_vision.py`), laufen gegen
das Ereignis eines `CancelToken`, den ein Beobachter in eigener Session aus demselben Merker setzt.

Bewusst ohne Import aus `photosort.*`: `cloud_vision.py` importiert dieses Modul, und
`cloud_vision.py` darf weder `photosort.config` noch etwas erreichen, das es importiert.

`CancelledError` wird nirgends gefangen oder abgeschirmt - Job-Timeout und Worker-Shutdown bleiben
echte Abbruchpunkte und enden weiter auf dem bestehenden Fehlerpfad.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

# Abstand, in dem der Beobachter den Merker liest - die obere Grenze, wie lange eine Wartezeit
# nach einem Abbruch noch laeuft.
WATCH_INTERVAL_SECONDS = 2.0


class RunCancelled(Exception):
    """Eine Wartezeit wurde durch einen Abbruchwunsch beendet. Kein Fehler des Elements: die
    Aufrufer zaehlen es weder als fehlgeschlagenen Aufruf noch als Cloud-Fehler."""


class CancelToken:
    """Das Abbruch-Ereignis eines Laufs. Gesetzt wird es vom Beobachter in
    `watch_cancel_requests`; gelesen von `sleep_unless_cancelled`."""

    def __init__(self) -> None:
        self.event = asyncio.Event()


# Kontextvariable statt Parameter: die Schrittmacher existieren prozessweit je Anbieter, und
# `post_vision_request` hat mehrere Aufrufstellen. `asyncio.gather`-Kinder erben den Kontext.
current_cancel_token: ContextVar[CancelToken | None] = ContextVar(
    "current_cancel_token", default=None
)


async def cancel_requested(session: AsyncSession, run: Any) -> bool:
    """Ist fuer diesen Lauf ein Abbruch angefordert? Eine Primaerschluessel-Lesung je Aufruf, frisch
    aus der Datenbank - der Stand im geladenen Objekt kann veraltet sein.

    Ohne Autoflush: ein Flush schriebe die noch nicht committeten Zaehler der Laufzeile und hielte
    deren Zeilensperre bis zum naechsten Commit - das bedingte `UPDATE` der API wartete so lange."""
    model = type(run)
    with session.no_autoflush:
        value = (
            await session.execute(select(model.cancel_requested_at).where(model.id == run.id))
        ).scalar_one_or_none()
    return value is not None


async def sleep_unless_cancelled(sleep: Callable[[float], Awaitable[None]], seconds: float) -> None:
    """Wartet `seconds` ueber den uebergebenen `sleep` - es sei denn, der Lauf im Kontext wird
    vorher abgebrochen: dann endet die Wartezeit sofort mit `RunCancelled`.

    Ohne Token (kein Lauf, Tests ohne Kontext) ist das genau `await sleep(seconds)`."""
    token = current_cancel_token.get()
    if token is None:
        await sleep(seconds)
        return
    if token.event.is_set():
        raise RunCancelled
    sleeper = asyncio.ensure_future(sleep(seconds))
    waiter = asyncio.ensure_future(token.event.wait())
    try:
        await asyncio.wait({sleeper, waiter}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        sleeper.cancel()
        waiter.cancel()
    if sleeper.done() and not sleeper.cancelled():
        sleeper.result()
        return
    raise RunCancelled


async def _watch(
    session_factory: async_sessionmaker[AsyncSession],
    model: Any,
    run_id: int,
    token: CancelToken,
    interval_seconds: float,
) -> None:
    while True:
        try:
            async with session_factory() as session:
                value = (
                    await session.execute(
                        select(model.cancel_requested_at).where(model.id == run_id)
                    )
                ).scalar_one_or_none()
        except Exception:
            # Ein verpasster Lesezyklus verzoegert nur das Ende einer Wartezeit; die Pruefpunkte
            # des Laufs lesen den Merker unabhaengig davon.
            logger.warning("Abbruchmerker nicht lesbar (Lauf %s)", run_id, exc_info=True)
            value = None
        if value is not None:
            token.event.set()
            return
        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def watch_cancel_requests(
    session_factory: async_sessionmaker[AsyncSession],
    model: Any,
    run_id: int,
    *,
    interval_seconds: float = WATCH_INTERVAL_SECONDS,
) -> AsyncIterator[CancelToken]:
    """Setzt fuer die Dauer des Blocks einen `CancelToken` in den Kontext und beobachtet den
    Merker des Laufs in eigener Session. Der Beobachter endet mit dem Block."""
    token = CancelToken()
    reset = current_cancel_token.set(token)
    watcher = asyncio.create_task(_watch(session_factory, model, run_id, token, interval_seconds))
    try:
        yield token
    finally:
        watcher.cancel()
        await asyncio.wait({watcher})
        current_cancel_token.reset(reset)
