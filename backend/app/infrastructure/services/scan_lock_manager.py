import asyncio
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.core.config import get_settings


_IN_MEMORY_LOCKS: dict[str, tuple[str, float]] = {}
_IN_MEMORY_GUARD = asyncio.Lock()


@dataclass(slots=True)
class ScanLockLease:
    session_id: str
    source_fingerprint: str
    owner: str
    session_key: str
    source_key: str
    session_ttl_seconds: int
    source_ttl_seconds: int


class ScanLockManager:
    def __init__(self) -> None:
        settings = get_settings()
        self.backend = settings.scan_lock_backend
        self.redis_url = settings.redis_url
        self.session_ttl_seconds = settings.session_scan_lock_ttl_seconds
        self.source_ttl_seconds = settings.source_scan_lock_ttl_seconds
        self._redis_client: Any | None = None

    async def acquire_submission_locks(self, *, session_id: str, source_fingerprint: str) -> ScanLockLease | None:
        owner = str(uuid4())
        lease = ScanLockLease(
            session_id=session_id,
            source_fingerprint=source_fingerprint,
            owner=owner,
            session_key=f"codeguard:lock:scan:session:{session_id}",
            source_key=f"codeguard:lock:scan:source:{source_fingerprint}",
            session_ttl_seconds=self.session_ttl_seconds,
            source_ttl_seconds=self.source_ttl_seconds,
        )
        source_acquired = await self._acquire_key(lease.source_key, owner, lease.source_ttl_seconds)
        if not source_acquired:
            return None
        session_acquired = await self._acquire_key(lease.session_key, owner, lease.session_ttl_seconds)
        if not session_acquired:
            await self._release_key(lease.source_key, owner)
            return None
        return lease

    async def refresh_submission_locks(self, lease: ScanLockLease | None) -> None:
        if lease is None:
            return
        await self._refresh_key(lease.source_key, lease.owner, lease.source_ttl_seconds)
        await self._refresh_key(lease.session_key, lease.owner, lease.session_ttl_seconds)

    async def release_submission_locks(self, lease: ScanLockLease | None) -> None:
        if lease is None:
            return
        await self._release_key(lease.source_key, lease.owner)
        await self._release_key(lease.session_key, lease.owner)

    async def build_lease_from_job(self, *, session_id: str, source_fingerprint: str | None, owner: str | None) -> ScanLockLease | None:
        if not source_fingerprint or not owner:
            return None
        return ScanLockLease(
            session_id=session_id,
            source_fingerprint=source_fingerprint,
            owner=owner,
            session_key=f"codeguard:lock:scan:session:{session_id}",
            source_key=f"codeguard:lock:scan:source:{source_fingerprint}",
            session_ttl_seconds=self.session_ttl_seconds,
            source_ttl_seconds=self.source_ttl_seconds,
        )

    async def _acquire_key(self, key: str, owner: str, ttl_seconds: int) -> bool:
        client = await self._get_redis_client()
        if client is not None:
            result = await client.set(key, owner, ex=ttl_seconds, nx=True)
            return bool(result)
        async with _IN_MEMORY_GUARD:
            now = time.monotonic()
            current = _IN_MEMORY_LOCKS.get(key)
            if current is not None and current[1] > now and current[0] != owner:
                return False
            _IN_MEMORY_LOCKS[key] = (owner, now + ttl_seconds)
            return True

    async def _refresh_key(self, key: str, owner: str, ttl_seconds: int) -> None:
        client = await self._get_redis_client()
        if client is not None:
            await client.eval(
                """
                if redis.call('get', KEYS[1]) == ARGV[1] then
                    return redis.call('expire', KEYS[1], ARGV[2])
                end
                return 0
                """,
                1,
                key,
                owner,
                ttl_seconds,
            )
            return
        async with _IN_MEMORY_GUARD:
            current = _IN_MEMORY_LOCKS.get(key)
            if current is None or current[0] != owner:
                return
            _IN_MEMORY_LOCKS[key] = (owner, time.monotonic() + ttl_seconds)

    async def _release_key(self, key: str, owner: str) -> None:
        client = await self._get_redis_client()
        if client is not None:
            await client.eval(
                """
                if redis.call('get', KEYS[1]) == ARGV[1] then
                    return redis.call('del', KEYS[1])
                end
                return 0
                """,
                1,
                key,
                owner,
            )
            return
        async with _IN_MEMORY_GUARD:
            current = _IN_MEMORY_LOCKS.get(key)
            if current is None or current[0] != owner:
                return
            _IN_MEMORY_LOCKS.pop(key, None)

    async def _get_redis_client(self) -> Any | None:
        backend = self.backend
        if backend == "in_memory":
            return None
        if backend == "auto" and not self.redis_url:
            return None
        if backend == "redis" and not self.redis_url:
            raise RuntimeError("SCAN_LOCK_BACKEND='redis' requires REDIS_URL.")
        if not self.redis_url:
            return None
        if self._redis_client is not None:
            return self._redis_client
        try:
            from redis.asyncio import Redis
        except ModuleNotFoundError:
            if backend == "redis":
                raise RuntimeError("Redis scan locks require the optional redis dependency in this Python environment.")
            return None
        self._redis_client = Redis.from_url(self.redis_url)
        return self._redis_client
