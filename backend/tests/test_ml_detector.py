"""ML detector: features, training quality, false positives and detection rate.

Timing matters (inter-arrival is a feature), so the detector's clock is replaced
with a fake one and traffic is replayed with the same pacing as the simulator.
"""
from __future__ import annotations

import random

import pytest

from app.engine import ml_detector as mlmod
from app.engine.dispatcher import ML_ALERT_THRESHOLD
from app.engine.packet import Packet
from app.engine.sniffer import TrafficSimulator
from helpers import FakeClock, noop_handler

ATTACKER = "203.0.113.66"


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(mlmod, "time", fake)
    return fake


@pytest.fixture
def sim():
    random.seed(7)
    return TrafficSimulator(handler=noop_handler)


@pytest.fixture(scope="module", params=["random_forest", "isolation_forest"])
def trained(request):
    detector = mlmod.MLDetector()
    result = detector.train_synthetic(algorithm=request.param)
    return detector, result


def count_alerts(detector, clock, packets_with_gaps) -> int:
    """How many packets would raise an ML-only alert in the dispatcher."""
    detector._state.last_ts = {}
    alerts = 0
    for pkt, gap_s in packets_with_gaps:
        clock.now += gap_s
        label, score = detector.score(pkt)
        alerts += label == 1 and score >= ML_ALERT_THRESHOLD
    return alerts


def benign_stream(sim, n):
    """Same pacing as TrafficSimulator._loop: 6-10 back-to-back packets every 0.25 s."""
    out = []
    while len(out) < n:
        burst = random.randint(6, 10)
        out += [(sim._benign(), 0.25 if i == 0 else 0.00005) for i in range(burst)]
    return out[:n]


# --------------------------------------------------------------------------- #
# Features                                                                     #
# --------------------------------------------------------------------------- #
def test_flag_mask_parsing():
    assert mlmod._flag_mask("A,P") == 16 + 8
    assert mlmod._flag_mask("S") == 2
    assert mlmod._flag_mask("") == 0


def test_first_packet_from_a_source_is_not_treated_as_a_flood(clock):
    detector = mlmod.MLDetector()
    pkt = Packet(src_ip="10.0.0.20", src_port=40000, dst_ip="10.0.0.10", dst_port=443,
                 length=500, flags="A,P")
    first = detector._featurize(pkt)
    clock.now += 0.005
    second = detector._featurize(pkt)
    assert first[5] == mlmod.NEW_SOURCE_INTERARRIVAL_MS
    assert second[5] == pytest.approx(5.0)


# --------------------------------------------------------------------------- #
# Training and live behaviour                                                  #
# --------------------------------------------------------------------------- #
def test_training_reports_good_holdout_metrics(trained):
    _, result = trained
    floor = 0.95 if result["algorithm"] == "random_forest" else 0.85
    assert result["metrics"]["accuracy"] >= floor


def test_benign_traffic_raises_no_ml_alerts(trained, clock, sim):
    """Benign traffic must not trip the ML detector: at most 1 % of packets may alert."""
    detector, _ = trained
    n = 2000
    assert count_alerts(detector, clock, benign_stream(sim, n)) / n <= 0.01


@pytest.mark.parametrize("kind", ["_nmap_scan", "_ssh_brute", "_icmp_flood"])
def test_scan_and_flood_bursts_are_flagged(trained, clock, sim, kind):
    detector, _ = trained
    burst = getattr(sim, kind)(ATTACKER)
    flagged = count_alerts(detector, clock, [(p, 0.002) for p in burst])
    assert flagged / len(burst) >= 0.85


def test_saved_model_scores_identically(trained, tmp_path, clock, sim):
    detector, _ = trained
    path = tmp_path / "model.joblib"
    detector.save(path)
    reloaded = mlmod.MLDetector()
    reloaded.load(path)

    packets = [sim._benign() for _ in range(20)] + sim._nmap_scan(ATTACKER)

    def scores(d):
        d._state.last_ts = {}
        clock.now = 1_000.0
        out = []
        for p in packets:
            clock.now += 0.01
            out.append(d.score(p))
        return out

    assert scores(reloaded) == scores(detector)
