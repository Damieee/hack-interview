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
HISTORY_KEY = "history:global"


def _get_client() -> Redis:
    global _redis
    if _redis is not None:
        return _redis
    settings = get_settings()
    parsed = urlparse(settings.redis_url)
    use_ssl = parsed.scheme == "rediss" or (parsed.hostname or "").endswith("upstash.io")
    _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def save_history_entry(payload: dict[str, Any]) -> None:
    client = _get_client()
    settings = get_settings()
    entry = {
        "id": payload.get("id") or str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    record = json.dumps(entry)
    await client.lpush(HISTORY_KEY, record)
    await client.ltrim(HISTORY_KEY, 0, 99)
    await client.expire(HISTORY_KEY, settings.history_ttl_seconds)


async def fetch_history_entries() -> List[HistoryEntry]:
    client = _get_client()
    rows = await client.lrange(HISTORY_KEY, 0, 99)
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
