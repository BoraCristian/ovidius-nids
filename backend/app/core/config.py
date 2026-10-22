"""Runtime configuration loaded from environment / .env file."""
from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Values that mean "no real secret configured" (empty, or the placeholders
# shipped in older .env.example files). Any of these triggers a generated key.
_PLACEHOLDER_SECRETS = {"", "dev-secret-change-me", "change-me-to-a-long-random-string"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "NIDS SIEM"
    debug: bool = True

    # --- Security ---
    # JWT signing key. Leave empty to get a random key generated on first
    # boot and persisted to data/.secret_key (see ensure_secret_key).
    secret_key: str = ""
    access_token_expire_minutes: int = 60 * 24
    algorithm: str = "HS256"

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///./nids.db"

    # --- CORS ---
    frontend_origin: str = "http://localhost:5173"

    # --- Sniffer ---
    sniffer_interface: str = ""
    sniffer_bpf_filter: str = ""
    simulate_traffic: bool = True

    # --- Demo / simulator ---
    # The "defended host": every synthetic packet (benign or attack) targets
    # this IP, so the dashboard shows a single, clear target the NIDS is
    # protecting.  Default 10.0.0.10 is a typical private-LAN address.
    defended_host_ip: str = "10.0.0.10"
    defended_host_name: str = "ovidius-nids-sensor"
    # When True the TrafficSimulator only emits attacks on demand (no random
    # 5-second attack bursts).  Default ON, so the dashboard stays quiet
    # until the analyst clicks an attack button.
    sim_attacks_on_demand_only: bool = True
    # When True the simulator continuously emits a benign-traffic baseline
    # (24--40 pps to the defended host).  Default OFF so the live-packet
    # graph stays flat until an attack is fired — that makes the demo
    # cause/effect obvious to the audience.  Flip to True for a more
    # realistic "always-on" environment.
    sim_benign_traffic: bool = False

    # --- Paths ---
    data_dir: Path = Path("./data")
    rules_file: Path = Path("./data/rules/default_rules.yaml")
    pcap_dir: Path = Path("./data/pcaps")
    ml_model_dir: Path = Path("./data/models")

    # --- Default admin ---
    admin_username: str = "admin"
    admin_password: str = "admin"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.pcap_dir.mkdir(parents=True, exist_ok=True)
        self.ml_model_dir.mkdir(parents=True, exist_ok=True)
        self.rules_file.parent.mkdir(parents=True, exist_ok=True)

    def ensure_secret_key(self) -> None:
        """Replace a missing/placeholder SECRET_KEY with a random per-install key.

        The key is stored in data/.secret_key (git-ignored) and reused on later
        boots, so issued tokens survive restarts but no two installs share a key.
        """
        if self.secret_key not in _PLACEHOLDER_SECRETS:
            return
        key_file = self.data_dir / ".secret_key"
        key = key_file.read_text(encoding="utf-8").strip() if key_file.exists() else ""
        if not key:
            key = secrets.token_urlsafe(48)
            key_file.write_text(key, encoding="utf-8")
        self.secret_key = key


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    settings.ensure_secret_key()
    return settings
