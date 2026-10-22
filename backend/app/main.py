"""NIDS SIEM — FastAPI entry point.

Wires the engine, sniffer/simulator, API routers, and WebSocket streams."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import alerts as alerts_api
from app.api import auth as auth_api
from app.api import dashboard as dashboard_api
from app.api import forensics as forensics_api
from app.api import ml as ml_api
from app.api import rules as rules_api
from app.api import sim as sim_api
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, init_db
from app.engine.dispatcher import build_dispatcher
from app.engine.sniffer import LiveSniffer, TrafficSimulator
from app.seed import reload_engine_from_db, seed_admin, seed_rules
from app.ws import alerts as ws_alerts

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
log = logging.getLogger("nids")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    log.info("Initialising database and default data...")
    await init_db()

    async with AsyncSessionLocal() as db:
        await seed_admin(db)
        await seed_rules(db)
        await reload_engine_from_db(db)

    dispatcher = build_dispatcher(pcap_dir=settings.pcap_dir, enable_ml=True)
    app.state.dispatcher = dispatcher

    # Start sniffer / simulator
    app.state.sniffer = None
    app.state.simulator = None

    def _new_simulator() -> TrafficSimulator:
        """Build a simulator wired to the configured defended host."""
        return TrafficSimulator(
            handler=dispatcher.handle,
            defended_host_ip=settings.defended_host_ip,
            attacks_on_demand_only=settings.sim_attacks_on_demand_only,
            benign_traffic=settings.sim_benign_traffic,
        )

    if settings.simulate_traffic or not settings.sniffer_interface:
        log.info(
            "Starting synthetic traffic simulator "
            "(defended host=%s, on-demand attacks=%s, benign baseline=%s)",
            settings.defended_host_ip,
            settings.sim_attacks_on_demand_only,
            settings.sim_benign_traffic,
        )
        sim = _new_simulator()
        sim.start()
        app.state.simulator = sim
    else:
        log.info("Starting live sniffer on %s", settings.sniffer_interface)
        try:
            live = LiveSniffer(
                interface=settings.sniffer_interface,
                bpf_filter=settings.sniffer_bpf_filter,
                handler=dispatcher.handle,
            )
            live.start(asyncio.get_running_loop())
            app.state.sniffer = live
        except Exception as exc:
            log.warning("Live sniffer failed (%s). Falling back to simulator.", exc)
            sim = _new_simulator()
            sim.start()
            app.state.simulator = sim

    log.info("NIDS is running.")
    try:
        yield
    finally:
        log.info("Shutting down engine...")
        if app.state.sniffer:
            app.state.sniffer.stop()
        if app.state.simulator:
            await app.state.simulator.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    origins = [o.strip() for o in settings.frontend_origin.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(auth_api.router)
    app.include_router(alerts_api.router)
    app.include_router(rules_api.router)
    app.include_router(dashboard_api.router)
    app.include_router(forensics_api.router)
    app.include_router(ml_api.router)
    app.include_router(sim_api.router)
    app.include_router(ws_alerts.router)

    @app.get("/api/health")
    async def health():
        disp = getattr(app.state, "dispatcher", None)
        sim = getattr(app.state, "simulator", None)
        return {
            "status": "ok",
            "app": settings.app_name,
            "debug": settings.debug,
            "packets": disp.packets if disp else 0,
            "alerts": disp.alerts if disp else 0,
            "pps": round(disp.pps(), 2) if disp else 0.0,
            "defended_host_ip":   settings.defended_host_ip,
            "defended_host_name": settings.defended_host_name,
            "monitoring_mode":    "live" if getattr(app.state, "sniffer", None) else "simulator",
            "sim_on_demand":      bool(sim.attacks_on_demand_only) if sim else None,
            "sim_attacks_fired":  sim.attacks_fired if sim else 0,
        }

    return app


app = create_app()
