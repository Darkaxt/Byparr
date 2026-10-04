"""FIFO ownership of the single browser, from admission through cleanup."""

import asyncio
import contextlib
from collections import deque
from contextlib import asynccontextmanager

from fastapi import HTTPException, Request


async def wait_for_disconnect(request: Request) -> None:
    """Wait for the actual ASGI event without polling or a queue deadline."""
    while (await request.receive())["type"] != "http.disconnect":
        pass


class BrowserAdmission:
    """One event-loop owner and a bounded FIFO of unsubmitted requests."""

    def __init__(self, limit: int):
        """Set the pending bound; one active operation is counted separately."""
        self.limit = limit
        self.owner: asyncio.Future | None = None
        self.waiters: deque[asyncio.Future] = deque()

    def status(self) -> dict[str, bool | int]:
        """Expose counts, never target URLs, client identity or private output."""
        return {
            "active": self.owner is not None,
            "queued": len(self.waiters),
            "queueLimit": self.limit,
        }

    def enter(self) -> asyncio.Future:
        """Register atomically before yielding control to another request."""
        if self.owner is not None and len(self.waiters) >= self.limit:
            raise HTTPException(
                503, "Browser queue full; no request was queued or submitted"
            )
        ticket = asyncio.get_running_loop().create_future()
        if self.owner is None:
            self.owner = ticket
            ticket.set_result(None)
        else:
            self.waiters.append(ticket)
        return ticket

    def leave(self, ticket: asyncio.Future) -> None:
        """Remove a waiter or hand ownership directly to the oldest waiter."""
        if ticket is self.owner:
            self.owner = self.waiters.popleft() if self.waiters else None
            if self.owner is not None:
                self.owner.set_result(None)
        else:
            self.waiters.remove(ticket)
            ticket.cancel()

    @asynccontextmanager
    async def transaction(self, request: Request | None = None):
        """Acquire once, drop disconnected waiters, and release after cleanup."""
        ticket = self.enter()
        disconnect = None
        try:
            if not ticket.done() and request is not None:
                disconnect = asyncio.create_task(wait_for_disconnect(request))
                done, _ = await asyncio.wait(
                    (ticket, disconnect), return_when=asyncio.FIRST_COMPLETED
                )
                if disconnect in done:
                    # Inspect unexpected receive failures rather than calling
                    # every completed watcher a genuine disconnect.
                    disconnect.result()
                    raise HTTPException(499, "Client disconnected while queued")
            else:
                await asyncio.shield(ticket)
            if disconnect is not None:
                disconnect.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await disconnect
                disconnect = None
            yield
        finally:
            try:
                if disconnect is not None:
                    disconnect.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await disconnect
            finally:
                self.leave(ticket)
