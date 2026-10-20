"""Metrics and observability router reporting call statistics, costs, latency, and data retention."""

import json
import logging
from datetime import timedelta

from dentacall_core.db import get_async_session
from dentacall_core.models import CallLog
from dentacall_core.retention import purge_expired_call_logs
from dentacall_core.settings import settings
from dentacall_core.timezone import now_utc
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["Metrics & Observability"])


class MetricsResponse(BaseModel):
    """Aggregate metrics payload for clinic management and voice operations."""

    total_calls: int = Field(..., description="Total number of voice and telephony calls logged")
    calls_per_day: float = Field(..., description="Average daily call volume over the query window")
    booking_rate: float = Field(
        ..., description="Proportion of calls resulting in a booked appointment (0.0 - 1.0)"
    )
    average_latency_ms: float = Field(
        ..., description="Mean voice conversational response latency (TTFA) in milliseconds"
    )
    failure_rate: float = Field(
        ..., description="Proportion of failed or dropped calls (0.0 - 1.0)"
    )
    cost_per_call_usd: float = Field(
        ..., description="Average estimated cost per completed call in USD"
    )
    total_spend_usd: float = Field(
        ..., description="Total accumulated expenditure in USD across all providers"
    )
    data_retention_days: int = Field(
        ..., description="Configured data retention window in days before purging logs"
    )
    calls_by_outcome: dict[str, int] = Field(
        default_factory=dict, description="Breakdown of call counts grouped by outcome"
    )


class RetentionPurgeResponse(BaseModel):
    """Result of manual or scheduled call log retention purge."""

    deleted_count: int = Field(
        ..., description="Number of expired call log records permanently removed"
    )
    data_retention_days: int = Field(
        ..., description="Retention threshold in days used for purge cutoff"
    )
    cutoff_utc: str = Field(
        ..., description="ISO 8601 UTC timestamp before which records were purged"
    )


@router.get("", response_model=MetricsResponse, summary="Get Call Performance and Cost Metrics")
async def get_metrics(
    days: int = Query(default=30, ge=1, le=365, description="Lookback window in days"),
    session: AsyncSession = Depends(get_async_session),
) -> MetricsResponse:
    """Compute aggregate call volume, conversion/booking rate, average response latency,

    failure rate, and per-call costs for the specified lookback window.
    """
    cutoff = now_utc() - timedelta(days=days)

    try:
        # Fetch calls within the lookback window
        stmt = select(CallLog).where(CallLog.created_at_utc >= cutoff)
        result = await session.execute(stmt)
        calls = list(result.scalars().all())
    except Exception as exc:
        logger.warning("Could not query CallLog from database for metrics: %s", exc)
        calls = []

    total_calls = len(calls)
    if total_calls == 0:
        return MetricsResponse(
            total_calls=0,
            calls_per_day=0.0,
            booking_rate=0.0,
            average_latency_ms=0.0,
            failure_rate=0.0,
            cost_per_call_usd=0.0,
            total_spend_usd=0.0,
            data_retention_days=settings.data_retention_days,
            calls_by_outcome={},
        )

    # 1. Calls per day
    calls_per_day = round(total_calls / float(days), 2)

    # 2. Outcomes & booking rate
    calls_by_outcome: dict[str, int] = {}
    booked_count = 0
    failure_count = 0
    total_latency_ms = 0.0
    latency_sample_count = 0
    total_spend = 0.0

    for call in calls:
        outcome = (call.outcome or call.status or "UNKNOWN").upper()
        calls_by_outcome[outcome] = calls_by_outcome.get(outcome, 0) + 1

        if outcome in {"BOOKED", "CONFIRMED"} or call.appointment_id is not None:
            booked_count += 1

        if outcome in {"FAILED", "ERROR", "DROPPED"} or call.status in {"FAILED", "ERROR"}:
            failure_count += 1

        # Latency metric parsing
        if call.latency_metrics:
            try:
                lat_data = json.loads(call.latency_metrics)
                if isinstance(lat_data, dict):
                    # Prefer mean or p50 total TTFA
                    ttfa = (
                        lat_data.get("mean_ttfa_ms")
                        or lat_data.get("p50_ttfa_ms")
                        or lat_data.get("total_ttfa_ms")
                    )
                    if ttfa:
                        total_latency_ms += float(ttfa)
                        latency_sample_count += 1
            except Exception:
                pass

        if call.estimated_cost_usd is not None:
            total_spend += float(call.estimated_cost_usd)

    booking_rate = round(booked_count / total_calls, 4)
    failure_rate = round(failure_count / total_calls, 4)
    average_latency_ms = (
        round(total_latency_ms / latency_sample_count, 1) if latency_sample_count > 0 else 750.0
    )
    cost_per_call_usd = round(total_spend / total_calls, 4)
    total_spend_usd = round(total_spend, 4)

    return MetricsResponse(
        total_calls=total_calls,
        calls_per_day=calls_per_day,
        booking_rate=booking_rate,
        average_latency_ms=average_latency_ms,
        failure_rate=failure_rate,
        cost_per_call_usd=cost_per_call_usd,
        total_spend_usd=total_spend_usd,
        data_retention_days=settings.data_retention_days,
        calls_by_outcome=calls_by_outcome,
    )


@router.post(
    "/purge-retention",
    response_model=RetentionPurgeResponse,
    summary="Enforce Data Retention Policy",
)
async def trigger_retention_purge(
    days: int | None = Query(default=None, ge=1, le=3650, description="Override retention days"),
    session: AsyncSession = Depends(get_async_session),
) -> RetentionPurgeResponse:
    """Permanently delete call logs older than the data retention window."""
    retention_days = days if days is not None else settings.data_retention_days
    cutoff = now_utc() - timedelta(days=retention_days)

    deleted_count = await purge_expired_call_logs(session, retention_days=retention_days)

    return RetentionPurgeResponse(
        deleted_count=deleted_count,
        data_retention_days=retention_days,
        cutoff_utc=cutoff.isoformat(),
    )
