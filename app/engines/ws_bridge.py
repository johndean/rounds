"""
WebSocket bridge — Redis pub/sub channel between Celery workers and the
FastAPI WSManager.

Tasks call `publish_ws_event_sync(session_id, payload)` — this pushes
JSON onto `rounds:ws:{session_id}`. The FastAPI lifespan subscribes
via `start_ws_bridge(ws_manager)` and forwards each message to all
clients currently connected to that session's WebSocket.

Closes audit gaps 🟠 #19 (no WS bridge), 🟡 (live status). Phase 6n / U130-U132.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


_WS_CHANNEL = "rounds:ws:{session_id}"
_WS_GLOB = "rounds:ws:*"


def publish_ws_event_sync(session_id: str, payload: dict[str, Any]) -> None:
    """
    Publish a WS event from a synchronous context (Celery tasks).

    Envelope shape (matches MIC §10):
        {"session_id": "...", "payload": {...inner payload...}}
    The bridge forwarder unwraps `data["payload"]` and broadcasts that to
    connected clients — so frontend receives just `{type, ...}` without the
    session_id wrapper.
    """
    try:
        import redis as _redis

        r = _redis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            r.publish(
                _WS_CHANNEL.format(session_id=session_id),
                json.dumps({"session_id": session_id, "payload": payload}),
            )
        finally:
            r.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"ws publish failed for {session_id}: {exc}")


async def start_ws_bridge(ws_manager) -> None:
    """
    Subscribe to all rounds:ws:* channels and forward messages to ws_manager.
    Runs as a background task in FastAPI lifespan.
    """
    import redis.asyncio as _aredis

    r = _aredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    try:
        await pubsub.psubscribe(_WS_GLOB)
        logger.info(f"ws_bridge: psubscribed to {_WS_GLOB}")
        async for message in pubsub.listen():
            if message["type"] != "pmessage":
                continue
            try:
                data = json.loads(message["data"])
                session_id = data.get("session_id")
                payload = data.get("payload")
                if session_id and isinstance(payload, dict):
                    await ws_manager.broadcast(session_id, payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"ws_bridge forward error: {exc}")
    except asyncio.CancelledError:
        logger.info("ws_bridge cancelled — closing pubsub")
        raise
    finally:
        try:
            await pubsub.unsubscribe()
        except Exception as e:  # noqa: BLE001
            logger.debug(f"unsubscribe ignored: {e}")
        await r.aclose()


class WSManager:
    """
    Simple in-memory WebSocket manager. Per-session connection set.
    Tasks publish through Redis pub/sub; this manager fans out to clients.
    """

    def __init__(self) -> None:
        from collections import defaultdict

        self._connections: dict[str, set] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, session_id: str, websocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[session_id].add(websocket)
        logger.info(f"ws: client connected to {session_id}")

    async def disconnect(self, session_id: str, websocket) -> None:
        async with self._lock:
            self._connections[session_id].discard(websocket)
            if not self._connections[session_id]:
                del self._connections[session_id]

    async def broadcast(self, session_id: str, payload: dict) -> None:
        async with self._lock:
            connections = list(self._connections.get(session_id, set()))
        for ws in connections:
            try:
                await ws.send_json(payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"ws broadcast failed (session={session_id}): {exc}")
                await self.disconnect(session_id, ws)
