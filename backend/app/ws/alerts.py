"""WebSocket endpoints: /ws/alerts for live detections, /ws/traffic for live flow."""
from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.security import decode_access_token
from app.engine.bus import alert_bus, traffic_bus

router = APIRouter()


async def _auth(ws: WebSocket, token: str | None) -> bool:
    """Allow either a valid JWT in the query string OR (in dev) any connection.
    Clients connect as: ws://host/ws/alerts?token=<jwt>"""
    if not token:
        await ws.close(code=4401)
        return False
    payload = decode_access_token(token)
    if not payload:
        await ws.close(code=4401)
        return False
    return True


@router.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket, token: str | None = Query(default=None)) -> None:
    await ws.accept()
    if not await _auth(ws, token):
        return
    q = await alert_bus.subscribe()
    try:
        while True:
            evt = await q.get()
            await ws.send_text(json.dumps(evt, default=str))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await alert_bus.unsubscribe(q)


@router.websocket("/ws/traffic")
async def ws_traffic(ws: WebSocket, token: str | None = Query(default=None)) -> None:
    await ws.accept()
    if not await _auth(ws, token):
        return
    q = await traffic_bus.subscribe(maxsize=2000)
    # throttle: send batches of up to 50 events every 500 ms to limit frontend churn
    buf: list[dict] = []
    last = time.monotonic()
    try:
        while True:
            try:
                evt = await asyncio.wait_for(q.get(), timeout=0.5)
                buf.append(evt)
            except asyncio.TimeoutError:
                pass
            now = time.monotonic()
            if buf and (len(buf) >= 50 or now - last >= 0.5):
                await ws.send_text(json.dumps({"type": "traffic_batch", "events": buf}, default=str))
                buf = []
                last = now
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await traffic_bus.unsubscribe(q)
