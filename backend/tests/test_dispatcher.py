"""Dispatcher live metrics."""
from __future__ import annotations

import pytest

from app.engine import dispatcher as dispmod
from helpers import FakeClock


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(dispmod, "time", fake)
    return fake


def test_idle_dispatcher_reports_zero_pps(clock, tmp_path):
    assert dispmod.Dispatcher(pcap_dir=tmp_path, enable_ml=False).pps() == 0.0


def test_pps_measures_rate_then_drops_to_zero_when_traffic_stops(clock, tmp_path):
    d = dispmod.Dispatcher(pcap_dir=tmp_path, enable_ml=False)
    for _ in range(30):              # 25 packets/s for 1.2 s
        clock.now += 0.04
        d._tick_pps()
    assert d.pps() == pytest.approx(25.0)

    clock.now += 3                   # no packets for 3 s
    assert d.pps() == 0.0
