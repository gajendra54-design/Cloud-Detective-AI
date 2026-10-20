import os
from functools import lru_cache
from pydantic import BaseModel, Field


class Settings(BaseModel):
    database_url: str
    prometheus_url: str = "http://prometheus:9090"
    checkout_url: str = "http://checkout:8000"
    payment_url: str = "http://payment:8000"
    poll_seconds: float = Field(default=5, ge=1, le=60)
    error_threshold: float = Field(default=0.1, gt=0, lt=1)
    latency_threshold: float = Field(default=0.25, gt=0, le=10)
    persistence_polls: int = Field(default=2, ge=1, le=12)
    control_token: str = ""
    investigator_token: str = ""
    approver_token: str = ""
    worker_enabled: bool = True
    legacy_tokens_enabled: bool = True

    @property
    def targets(self):
        return {"checkout": self.checkout_url, "payment": self.payment_url}


@lru_cache
def settings():
    if os.getenv("APP_MODE", "local-demo") != "local-demo":
        raise RuntimeError(
            "Only local-demo authentication is supported; production mode is disabled"
        )
    return Settings(
        database_url=os.environ["DATABASE_URL"],
        prometheus_url=os.getenv("PROMETHEUS_URL", "http://prometheus:9090"),
        checkout_url=os.getenv("CHECKOUT_URL", "http://checkout:8000"),
        payment_url=os.getenv("PAYMENT_URL", "http://payment:8000"),
        poll_seconds=float(os.getenv("POLL_SECONDS", "5")),
        error_threshold=float(os.getenv("ERROR_THRESHOLD", ".1")),
        latency_threshold=float(os.getenv("LATENCY_THRESHOLD", ".25")),
        persistence_polls=int(os.getenv("PERSISTENCE_POLLS", "2")),
        control_token=os.getenv("DEMO_CONTROL_TOKEN", ""),
        investigator_token=os.getenv("INVESTIGATOR_TOKEN", ""),
        approver_token=os.getenv("APPROVER_TOKEN", ""),
        legacy_tokens_enabled=os.getenv("LEGACY_TOKENS_ENABLED", "true").lower()
        == "true",
        worker_enabled=os.getenv("WORKER_ENABLED", "true").lower() == "true",
    )
