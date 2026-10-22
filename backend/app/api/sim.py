"""Attack Console — on-demand attack injection into the running simulator.

Exposes:
  GET  /api/sim/info         metadata: defended host, mode, available attacks
  GET  /api/sim/attacks      catalog of attack kinds the simulator can emit
  POST /api/sim/attack       fire one attack of a given kind
  POST /api/sim/benign       toggle the benign-traffic baseline

These endpoints exist so the demo can be driven from the SIEM UI itself:
the analyst presses a button on the *Attack Console* page and a burst of
malicious-looking packets is pushed through the dispatcher just like real
traffic would, producing real alerts in real time.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.engine import dispatcher as _disp
from app.engine.sniffer import TrafficSimulator

router = APIRouter(
    prefix="/api/sim",
    tags=["sim"],
    dependencies=[Depends(get_current_user)],
)


# --------------------------------------------------------------------------- #
# Schemas                                                                      #
# --------------------------------------------------------------------------- #
class AttackKind(BaseModel):
    kind: str
    label: str
    description: str
    burst: bool


class SimInfo(BaseModel):
    enabled: bool
    monitoring_mode: str           # "simulator" | "live"
    defended_host_ip: str
    defended_host_name: str
    attacks_on_demand_only: bool
    benign_traffic: bool
    attacks_fired: int
    last_attack_ts: str | None = None
    last_attack_kind: str | None = None
    attacker_pool: list[str]
    available_attacks: list[AttackKind]


class ToggleBenignRequest(BaseModel):
    enabled: bool


class FireAttackRequest(BaseModel):
    kind: str = Field(..., description="One of the keys returned by /api/sim/attacks")
    attacker: str | None = Field(
        default=None,
        description="Optional override for the attacker IP. If omitted, a random "
                    "address from the simulator's attacker pool is used.",
    )


class FireAttackResult(BaseModel):
    kind: str
    attacker: str
    target: str
    packet_count: int
    ts: str
    # How many real alerts the dispatcher created from this burst — surfaced
    # in the UI so the user gets immediate confirmation of cause/effect.
    alerts_generated: int = 0


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def _require_simulator(request: Request) -> TrafficSimulator:
    sim: TrafficSimulator | None = getattr(request.app.state, "simulator", None)
    if sim is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The simulator is not running (this backend is configured for live "
            "packet capture). The Attack Console only works in simulator mode.",
        )
    return sim


# --------------------------------------------------------------------------- #
# Endpoints                                                                    #
# --------------------------------------------------------------------------- #
@router.get("/info", response_model=SimInfo)
async def sim_info(request: Request) -> SimInfo:
    """Snapshot of the simulator + defended-host metadata."""
    from app.core.config import get_settings
    settings = get_settings()
    sim: TrafficSimulator | None = getattr(request.app.state, "simulator", None)
    attacks = [
        AttackKind(kind=k, **v) for k, v in TrafficSimulator.ATTACK_CATALOG.items()
    ]
    return SimInfo(
        enabled=sim is not None,
        monitoring_mode="simulator" if sim else "live",
        defended_host_ip=settings.defended_host_ip,
        defended_host_name=settings.defended_host_name,
        attacks_on_demand_only=bool(sim.attacks_on_demand_only) if sim else True,
        benign_traffic=bool(sim.benign_traffic) if sim else False,
        attacks_fired=sim.attacks_fired if sim else 0,
        last_attack_ts=sim.last_attack_ts if sim else None,
        last_attack_kind=sim.last_attack_kind if sim else None,
        attacker_pool=list(TrafficSimulator.ATTACKERS),
        available_attacks=attacks,
    )


@router.post("/benign", response_model=SimInfo)
async def toggle_benign(payload: ToggleBenignRequest, request: Request) -> SimInfo:
    """Turn the benign-traffic baseline on or off without restarting."""
    sim = _require_simulator(request)
    sim.benign_traffic = bool(payload.enabled)
    return await sim_info(request)


@router.get("/attacks", response_model=list[AttackKind])
async def list_attacks() -> list[AttackKind]:
    """Available attack kinds, for populating the UI buttons."""
    return [
        AttackKind(kind=k, **v) for k, v in TrafficSimulator.ATTACK_CATALOG.items()
    ]


@router.post("/attack", response_model=FireAttackResult)
async def fire_attack(payload: FireAttackRequest, request: Request) -> FireAttackResult:
    """Inject one attack into the running simulator and report how many
    alerts the dispatcher created during the burst."""
    sim = _require_simulator(request)
    dispatcher = _disp.dispatcher
    alerts_before = dispatcher.alerts if dispatcher else 0
    try:
        result = await sim.fire_attack(payload.kind, attacker=payload.attacker)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    # Brief settle so any async DB writes triggered by the burst land before
    # we read the alert count.  Each per-packet handle() awaits its own
    # persistence, but the alert_bus broadcast is fire-and-forget; sleep a
    # tick so the count is stable.
    await asyncio.sleep(0.15)
    alerts_after = dispatcher.alerts if dispatcher else 0
    result["alerts_generated"] = max(0, alerts_after - alerts_before)
    return FireAttackResult(**result)
