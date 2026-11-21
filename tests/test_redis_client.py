import logging

from irmy_common import RedisClient


def test_responses_are_decoded_to_str():
    client = RedisClient(url="redis://localhost:6379", logger=logging.getLogger("test"))
    kwargs = client._pool.connection_kwargs
    assert kwargs["decode_responses"] is True
    assert kwargs["encoding"] == "utf-8"


def test_socket_timeouts_default_and_override():
    client = RedisClient(url="redis://localhost:6379", logger=logging.getLogger("test"))
    kwargs = client._pool.connection_kwargs
    assert kwargs["socket_timeout"] == 2.0
    assert kwargs["socket_connect_timeout"] == 2.0
    client = RedisClient(url="redis://localhost:6379", logger=logging.getLogger("test"),
                         socket_timeout=5, socket_connect_timeout=1)
    kwargs = client._pool.connection_kwargs
    assert (kwargs["socket_timeout"], kwargs["socket_connect_timeout"]) == (5, 1)


async def test_unreachable_redis_fails_fast():
    """A host that never answers: calls give up after the timeouts instead of hanging."""
    import time
    client = RedisClient(url="redis://10.255.255.1:6379", logger=logging.getLogger("test"),
                         socket_timeout=0.2, socket_connect_timeout=0.2)
    start = time.monotonic()
    assert await client.get("k") is None
    assert await client.healthcheck() is False
    assert time.monotonic() - start < 3


async def test_disconnect_closes_pool():
    client = RedisClient(url="redis://localhost:6379", logger=logging.getLogger("test"))
    closed = []

    async def fake_aclose():
        closed.append(True)

    client._pool.aclose = fake_aclose
    await client.disconnect()
    assert closed == [True]


# ── streams ──────────────────────────────────────────────────────────────────

import redis.asyncio as redis_asyncio  # noqa: E402

from irmy_common import StreamBatch  # noqa: E402


class _FakePipeline:
    def __init__(self, fail_times):
        self.fail_times = fail_times
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def xadd(self, *args, **kwargs):
        self.calls.append(("xadd", args, kwargs))

    def xtrim(self, *args, **kwargs):
        self.calls.append(("xtrim", args, kwargs))

    async def execute(self):
        if self.fail_times:
            self.fail_times.pop()
            raise redis_asyncio.ConnectionError("down")
        return []


def _stream_client(fail_times=0):
    client = RedisClient(url="redis://localhost:6379", logger=logging.getLogger("test"))
    failures = [True] * fail_times
    pipes = []

    def install():
        def pipeline(transaction=True):
            assert transaction is True
            pipe = _FakePipeline(failures)
            pipes.append(pipe)
            return pipe
        client._client.pipeline = pipeline

    install()

    async def fake_reconnect():
        install()

    client._reconnect = fake_reconnect
    return client, pipes


async def test_stream_add_writes_every_batch_in_one_transaction():
    client, pipes = _stream_client()
    ok = await client.stream_add([
        StreamBatch("logs:a", [{"m": "1"}, {"m": "2"}], max_len=1000, min_id="1700000000000-0"),
        StreamBatch("logs:b", [{"m": "3"}], max_len=200),
        StreamBatch("logs:c", []),  # nothing to do -- skipped
    ])
    assert ok is True and len(pipes) == 1
    assert pipes[0].calls == [
        ("xadd", ("logs:a", {"m": "1"}), {"maxlen": 1000, "approximate": False}),
        ("xadd", ("logs:a", {"m": "2"}), {"maxlen": 1000, "approximate": False}),
        ("xtrim", ("logs:a",), {"minid": "1700000000000-0", "approximate": False}),
        ("xadd", ("logs:b", {"m": "3"}), {"maxlen": 200, "approximate": False}),
    ]


async def test_stream_add_retries_once_after_reconnecting_then_reports_failure():
    client, pipes = _stream_client(fail_times=1)
    assert await client.stream_add([StreamBatch("k", [{"m": "1"}])]) is True
    assert len(pipes) == 2

    client, pipes = _stream_client(fail_times=2)
    assert await client.stream_add([StreamBatch("k", [{"m": "1"}])]) is False


async def test_stream_add_with_nothing_to_write_does_not_call_redis():
    client, pipes = _stream_client()
    assert await client.stream_add([]) is True
    assert pipes == []


async def test_stream_range_both_directions():
    client = RedisClient(url="redis://localhost:6379", logger=logging.getLogger("test"))
    calls = []

    async def xrange(key, **kw):
        calls.append(("xrange", key, kw))
        return [("1-0", {"m": "a"})]

    async def xrevrange(key, **kw):
        calls.append(("xrevrange", key, kw))
        return []

    client._client.xrange = xrange
    client._client.xrevrange = xrevrange
    assert await client.stream_range("k", start="(1-0") == [("1-0", {"m": "a"})]
    assert await client.stream_range("k", end="(5-0", count=10, reverse=True) == []
    assert calls == [("xrange", "k", {"min": "(1-0", "max": "+", "count": None}),
                     ("xrevrange", "k", {"max": "(5-0", "min": "-", "count": 10})]
