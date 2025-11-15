from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, List
from urllib.parse import urlparse

from loguru import logger
from redis.asyncio import Redis

from .config import get_settings
from .schemas import HistoryEntry

_redis: Redis | None = None


def _get_client() -> Redis:
    global _redis
    if _redis is not None:
        return _redis
    settings = get_settings()
    parsed = urlparse(settings.redis_url)
    use_ssl = parsed.scheme == "rediss" or (parsed.hostname or "").endswith("upstash.io")
    _redis = Redis.from_url(settings.redis_url, decode_responses=True, ssl=use_ssl)
    return _redis


def _key(session_id: str) -> str:
    return f"history:{session_id}"


async def save_history_entry(session_id: str, payload: dict[str, Any]) -> None:
    if not session_id:
        logger.warning("Missing session id, skip history persistence.")
        return
    client = _get_client()
    settings = get_settings()
    entry = {
        "id": payload.get("id") or str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    record = json.dumps(entry)
    key = _key(session_id)
    await client.lpush(key, record)
    await client.ltrim(key, 0, 49)
    await client.expire(key, settings.history_ttl_seconds)


async def fetch_history_entries(session_id: str) -> List[HistoryEntry]:
    if not session_id:
        return []
    client = _get_client()
    key = _key(session_id)
    rows = await client.lrange(key, 0, 49)
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=get_settings().history_ttl_seconds)
    entries: list[HistoryEntry] = []
    for raw in rows:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Dropping corrupt history payload: %s", raw)
            continue
        created_at_raw = data.get("created_at")
        if not created_at_raw:
            continue
        try:
            created_at = datetime.fromisoformat(created_at_raw)
        except ValueError:
            logger.warning("Unable to parse history timestamp: %s", created_at_raw)
            continue
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if created_at < cutoff:
            continue
        data["created_at"] = created_at
        entries.append(HistoryEntry(**data))
    return entries
