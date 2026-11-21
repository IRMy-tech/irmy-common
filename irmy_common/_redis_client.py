import logging
from collections.abc import Sequence
from dataclasses import dataclass, field

import redis.asyncio as redis


@dataclass(frozen=True)
class StreamBatch:
    """Entries to append to one Redis stream (``XADD``), oldest first. Every
    add trims the stream to ``max_len`` entries (exact ``MAXLEN``); after the
    adds, entries older than ``min_id`` are removed (``XTRIM MINID``). A stream
    id is ``<milliseconds>-<sequence>``, so ``min_id="1760430000000-0"`` drops
    everything added before that time."""
    key: str
    entries: Sequence[dict[str, str]] = field(default_factory=tuple)
    max_len: int | None = None
    min_id: str | None = None


# Seconds to open a connection and to wait for an answer. Without them an unreachable
# Redis (a dead node, a network partition) blocks every call for the OS TCP timeout
# (a minute or more) instead of failing fast; with them a failed call (one retry after
# reconnecting included) returns within about 2 x DEFAULT_SOCKET_TIMEOUT_SECONDS.
DEFAULT_SOCKET_TIMEOUT_SECONDS = 2.0


class RedisClient:
    def __init__(self, url: str, logger: logging.Logger, *,
                 socket_timeout: float = DEFAULT_SOCKET_TIMEOUT_SECONDS,
                 socket_connect_timeout: float = DEFAULT_SOCKET_TIMEOUT_SECONDS):
        self._logger = logger
        self._url = url
        self._socket_timeout = socket_timeout
        self._socket_connect_timeout = socket_connect_timeout
        self._init_pool_and_client()

    def _init_pool_and_client(self) -> None:
        self._logger.info("Connecting to Redis...")
        # Connection kwargs such as decode_responses only take effect on the pool — Redis()
        # ignores them when given an existing connection_pool.
        self._pool = redis.ConnectionPool.from_url(
            self._url, decode_responses=True, encoding="utf-8",
            socket_timeout=self._socket_timeout, socket_connect_timeout=self._socket_connect_timeout,
        )
        self._client = redis.Redis(connection_pool=self._pool)
        self._logger.info("Connected to Redis successfully")

    async def _execute(self, method: str, *args, **kwargs):
        try:
            return await getattr(self._client, method)(*args, **kwargs)
        except redis.RedisError as e:
            self._logger.warning(f"[Redis] Error for `{method}`: {e!r}, reconnecting...")
            await self._reconnect()
            try:
                return await getattr(self._client, method)(*args, **kwargs)
            except redis.RedisError as e2:
                self._logger.error(f"[Redis] After reconnecting: `{method}` Error again: {e2!r}")
                return None

    async def _reconnect(self) -> None:
        try:
            await self._pool.disconnect()
        except Exception as e:
            self._logger.info(f"Redis: Exception while closing redis pool: '{e}'")
            pass
        self._init_pool_and_client()

    async def get(self, key: str):
        return await self._execute('get', key)

    async def put(self, key: str, value, expire: int = None):
        return await self._execute('set', key, value, ex=expire)

    async def delete(self, key: str):
        return await self._execute('delete', key)

    async def stream_add(self, batches: Sequence[StreamBatch]) -> bool:
        """Append to one or more streams in a single ``MULTI``/``EXEC`` round
        trip -- all of it is written or none. True when written; False when
        Redis failed again after reconnecting, so the caller can keep the
        entries and retry later."""
        batches = [b for b in batches if b.entries or b.min_id is not None]
        if not batches:
            return True

        async def write() -> None:
            async with self._client.pipeline(transaction=True) as pipe:
                for batch in batches:
                    for entry in batch.entries:
                        pipe.xadd(batch.key, entry, maxlen=batch.max_len, approximate=False)
                    if batch.min_id is not None:
                        pipe.xtrim(batch.key, minid=batch.min_id, approximate=False)
                await pipe.execute()

        try:
            await write()
            return True
        except redis.RedisError as e:
            self._logger.warning(f"[Redis] Error for `stream_add`: {e!r}, reconnecting...")
            await self._reconnect()
            try:
                await write()
                return True
            except redis.RedisError as e2:
                self._logger.error(f"[Redis] After reconnecting: `stream_add` Error again: {e2!r}")
                return False

    async def stream_range(
        self, key: str, *, start: str = "-", end: str = "+", count: int | None = None, reverse: bool = False,
    ) -> list[tuple[str, dict[str, str]]] | None:
        """Stream entries with ids from ``start`` to ``end`` (inclusive; ``(id``
        excludes ``id``), oldest first -- newest first with ``reverse``. At
        most ``count``. ``[]`` for a missing stream, None when Redis failed."""
        if reverse:
            return await self._execute('xrevrange', key, max=end, min=start, count=count)
        return await self._execute('xrange', key, min=start, max=end, count=count)

    async def disconnect(self):
        await self._client.aclose()
        await self._pool.aclose()

    async def healthcheck(self) -> bool:
        try:
            return await self._client.ping()
        except Exception as e:
            self._logger.warning(f"Redis: Can not execute ping command: {e}")
            await self._reconnect()
            return False
