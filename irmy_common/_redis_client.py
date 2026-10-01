import logging
import redis.asyncio as redis


class RedisClient:
    def __init__(self, url: str, logger: logging.Logger):
        self._logger = logger
        self._url = url
        self._init_pool_and_client()

    def _init_pool_and_client(self) -> None:
        self._logger.info("Connecting to Redis...")
        # Connection kwargs such as decode_responses only take effect on the pool — Redis()
        # ignores them when given an existing connection_pool.
        self._pool = redis.ConnectionPool.from_url(self._url, decode_responses=True, encoding="utf-8")
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
