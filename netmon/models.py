"""Pydantic data models for netmon."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TrafficRecord(BaseModel):
    """Single traffic record from database."""
    
    id: int
    timestamp: datetime
    app_name: str
    remote_ip: Optional[str] = None
    bytes_sent: int
    bytes_recv: int


class AppTraffic(BaseModel):
    """Aggregated traffic for a single application."""
    
    name: str
    bytes_sent: int = 0
    bytes_recv: int = 0
    bytes_total: int = 0
    sent_formatted: str = ""
    recv_formatted: str = ""
    total_formatted: str = ""
    percentage: float = 0.0
    remote_ips: set[str] = Field(default_factory=set)


class TrafficBuffer(BaseModel):
    """In-memory traffic buffer entry."""
    
    sent: float = 0.0
    recv: float = 0.0
    ips: set[str] = Field(default_factory=set)
    
    class Config:
        arbitrary_types_allowed = True


class ExcludedIP(BaseModel):
    """Excluded IP entry."""
    
    ip: str
    description: str = ""
    added_at: Optional[datetime] = None


class WebhookConfig(BaseModel):
    """Webhook configuration."""
    
    url: Optional[str] = None
    interval_minutes: int = 60
    enabled: bool = False
    last_sent: Optional[datetime] = None


class WebhookPayload(BaseModel):
    """Webhook JSON payload structure."""
    
    version: str = "2.0"
    hostname: str
    timestamp: str
    report_period: str
    report_generated_at: str
    interfaces: list[str]
    summary: dict
    applications: list[dict]
    excluded_ips: list[dict]


class TrafficReport(BaseModel):
    """Traffic report summary."""
    
    title: str
    period_days: float
    total_sent: int = 0
    total_recv: int = 0
    total_bytes: int = 0
    total_formatted: str = ""
    applications: list[AppTraffic] = Field(default_factory=list)
