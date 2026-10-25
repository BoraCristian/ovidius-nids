"""Classical-ML anomaly detector.

Trains a RandomForest (or IsolationForest) on flow-level features computed
from observed packets. Works out-of-the-box on synthetic traffic so the
dashboard shows ML-powered alerts even before a real dataset is loaded.

Feature vector (per packet for the demo, per-flow later):
    [src_port, dst_port, length, protocol_id, tcp_flags_mask, interarrival_ms]
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer

from .packet import Packet

PROTO_ID = {"tcp": 6, "udp": 17, "icmp": 1, "any": 0}
FLAG_BITS = {"F": 1, "S": 2, "R": 4, "P": 8, "A": 16, "U": 32, "E": 64, "C": 128}
NEW_SOURCE_INTERARRIVAL_MS = 1000.0
SERVICE_PORTS = [443, 80, 53, 22]


def _anomaly_features(X: np.ndarray) -> np.ndarray:
    """Isolation Forest view of the raw feature vector.

    Isolation Forest isolates one feature at a time, but no single feature of
    a scan/flood packet is unusual on its own (normal traffic also has small
    packets, SYNs and back-to-back segments). What is unusual is the
    combination — "small, ACK-less, and much faster than normal" — so we hand
    it those interactions, on a log scale. Module-level so joblib can pickle it.
    """
    X = np.asarray(X, dtype=float)
    length, proto, flags, gap = np.log1p(X[:, 2]), X[:, 3], X[:, 4].astype(int), np.log1p(X[:, 5])
    no_ack = ((flags & FLAG_BITS["A"]) == 0).astype(float)    # SYN-only / RST / ICMP / UDP
    fast = np.clip(np.log1p(1000) - gap, 0, None)             # how much quicker than 1 s
    small = np.clip(np.log1p(200) - length, 0, None)          # how much smaller than 200 B
    return np.column_stack([no_ack * fast, no_ack * small, fast * small, (proto == PROTO_ID["icmp"]) * fast])


def _flag_mask(flags: str) -> int:
    m = 0
    for tok in (flags or "").split(","):
        t = tok.strip().upper()[:1]
        m |= FLAG_BITS.get(t, 0)
    return m


@dataclass
class MLDetectorState:
    model: Any = None
    is_anomaly: bool = False           # True if model is IsolationForest (unsupervised)
    feature_names: list[str] | None = None
    threshold: float = 0.5
    active: bool = False
    last_ts: dict[str, float] | None = None    # per-src interarrival tracker


class MLDetector:
    def __init__(self) -> None:
        self._state = MLDetectorState(last_ts={})
        self._lock = threading.Lock()

    # --- feature extraction ---
    def _featurize(self, pkt: Packet) -> np.ndarray:
        now = time.monotonic()
        prev = self._state.last_ts.get(pkt.src_ip) if self._state.last_ts else None
        # First packet from a source has no history: treat it as "quiet source",
        # not as 0 ms (which looks exactly like a flood to the model).
        inter = (now - prev) * 1000 if prev else NEW_SOURCE_INTERARRIVAL_MS
        if self._state.last_ts is not None:
            self._state.last_ts[pkt.src_ip] = now
        return np.array([
            pkt.src_port or 0,
            pkt.dst_port or 0,
            pkt.length or 0,
            PROTO_ID.get(pkt.protocol.lower(), 0),
            _flag_mask(pkt.flags),
            inter,
        ], dtype=float)

    @property
    def feature_names(self) -> list[str]:
        return ["src_port", "dst_port", "length", "proto_id", "flag_mask", "inter_arrival_ms"]

    # --- training ---
    def train_synthetic(
        self, n_samples: int = 4000, algorithm: str = "random_forest"
    ) -> dict[str, Any]:
        rng = np.random.default_rng(42)

        # Normal traffic: web + DNS + SSH sessions, in both directions.
        # Clients talk from ephemeral ports, so src_port alone must NOT
        # separate the classes (attackers use ephemeral ports too).
        n_normal = int(n_samples * 0.7)
        service = rng.choice(SERVICE_PORTS, n_normal)
        ephemeral = rng.integers(30000, 61000, n_normal)
        to_server = rng.random(n_normal) < 0.5
        normal_proto = np.where(service == 53, 17, 6)
        # TCP packet kind: 5% session-opening SYN, 25% pure ACK, 70% data.
        kind = rng.choice(["syn", "ack", "data"], n_normal, p=[0.05, 0.25, 0.70])
        is_tcp = normal_proto == 6
        normal_len = np.where(
            is_tcp & (kind != "data"),
            rng.integers(40, 80, n_normal),                                    # bare SYN / ACK
            rng.normal(600, 300, n_normal).clip(80, 1500),                     # payload-carrying
        )
        normal_flags = np.where(kind == "syn", 2, np.where(kind == "ack", 16, rng.choice([16, 24], n_normal)))
        # Segments inside a session arrive back-to-back; new sessions (SYN)
        # start at a human pace — a burst of SYNs is what a scan looks like.
        back_to_back = (kind != "syn") & (rng.random(n_normal) < 0.3)
        normal = np.column_stack([
            np.where(to_server, ephemeral, service),                           # src_port
            np.where(to_server, service, ephemeral),                           # dst_port
            normal_len,                                                        # length
            normal_proto,                                                      # proto_id
            np.where(is_tcp, normal_flags, 0),                                 # SYN / ACK / PSH-ACK (UDP: none)
            np.where(back_to_back,                                             # inter_arrival_ms:
                     rng.exponential(1, n_normal),                             #   back-to-back segments
                     rng.lognormal(np.log(400), 1.2, n_normal)),               #   or ~40 ms .. 5 s apart
        ])
        normal_y = np.zeros(n_normal, dtype=int)

        # Malicious: scans / brute / DoS patterns — tiny packets, SYN/RST-only
        # handshakes or ICMP, fired in tight bursts.
        n_bad = n_samples - n_normal
        bad_proto = rng.choice([1, 6, 17], n_bad, p=[0.2, 0.75, 0.05])
        is_icmp = bad_proto == 1
        bad = np.column_stack([
            np.where(is_icmp, 0, rng.integers(1024, 65535, n_bad)),            # ephemeral src_port
            np.where(is_icmp, 0, rng.choice([22, 23, 3389, 445, 21, 80, 443, 3306], n_bad)),
            np.where(rng.random(n_bad) < 0.9,                                  # very small OR very large
                     rng.integers(40, 100, n_bad), 1500),
            bad_proto,                                                         # proto_id
            np.where(bad_proto == 6, rng.choice([2, 4, 20], n_bad), 0),        # SYN / RST / RST-ACK
            rng.exponential(5, n_bad),                                         # very short inter-arrival
        ])
        bad_y = np.ones(n_bad, dtype=int)

        X = np.vstack([normal, bad])
        y = np.concatenate([normal_y, bad_y])

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42)

        metrics: dict[str, Any] = {}
        if algorithm == "isolation_forest":
            # Trained on normal traffic only, so the expected outlier share of
            # the training set is tiny — 0.3 here would flag 30% of benign traffic.
            X_normal = X_train[y_train == 0]
            model = make_pipeline(
                FunctionTransformer(_anomaly_features),
                IsolationForest(n_estimators=200, contamination=0.01, random_state=42),
            )
            model.fit(X_normal)   # train on normal only
            # Keep the normal-traffic anomaly scores so live scores can be
            # reported as a 0..1 percentile ("more unusual than X% of normal").
            model.train_scores_ = np.sort(-model.score_samples(X_normal))
            preds = (model.predict(X_test) == -1).astype(int)  # -1 = anomaly -> 1
            is_anomaly = True
        else:
            algorithm = "random_forest"
            model = RandomForestClassifier(n_estimators=200, max_depth=12, random_state=42)
            model.fit(X_train, y_train)
            preds = model.predict(X_test)
            is_anomaly = False

        metrics["accuracy"] = float(accuracy_score(y_test, preds))
        metrics["precision"] = float(precision_score(y_test, preds, zero_division=0))
        metrics["recall"] = float(recall_score(y_test, preds, zero_division=0))
        metrics["f1"] = float(f1_score(y_test, preds, zero_division=0))

        feature_importance = None
        if hasattr(model, "feature_importances_"):
            feature_importance = {
                n: float(v) for n, v in zip(self.feature_names, model.feature_importances_)
            }

        with self._lock:
            self._state.model = model
            self._state.is_anomaly = is_anomaly
            self._state.feature_names = self.feature_names
            self._state.active = True

        return {"algorithm": algorithm, "metrics": metrics, "feature_importance": feature_importance}

    # --- persistence ---
    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            joblib.dump(
                {
                    "model": self._state.model,
                    "is_anomaly": self._state.is_anomaly,
                    "feature_names": self._state.feature_names,
                    "threshold": self._state.threshold,
                },
                path,
            )

    def load(self, path: str | Path) -> None:
        blob = joblib.load(Path(path))
        with self._lock:
            self._state.model = blob["model"]
            self._state.is_anomaly = bool(blob.get("is_anomaly", False))
            self._state.feature_names = blob.get("feature_names") or self.feature_names
            self._state.threshold = float(blob.get("threshold", 0.5))
            self._state.active = True

    # --- live inference ---
    def is_active(self) -> bool:
        return self._state.active and self._state.model is not None

    def score(self, pkt: Packet) -> tuple[int, float]:
        """Return (label, score). 1 = malicious, 0 = benign."""
        if not self.is_active():
            return 0, 0.0
        x = self._featurize(pkt).reshape(1, -1)
        model = self._state.model
        if self._state.is_anomaly:
            pred = model.predict(x)[0]      # -1 anomaly, 1 normal
            ref = getattr(model, "train_scores_", None)
            if ref is not None:
                raw = -model.score_samples(x)[0]
                score = float(np.searchsorted(ref, raw, side="right") / len(ref))
            else:                           # uncalibrated model (no training scores)
                score = float(-model.decision_function(x)[0])
            return (1 if pred == -1 else 0), score
        if hasattr(model, "predict_proba"):
            probs = model.predict_proba(x)[0]
            pos = float(probs[1]) if len(probs) > 1 else float(probs[0])
            label = 1 if pos >= self._state.threshold else 0
            return label, pos
        label = int(model.predict(x)[0])
        return label, float(label)


# Singleton
detector = MLDetector()
