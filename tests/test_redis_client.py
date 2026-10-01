import logging

from irmy_common import RedisClient


def test_responses_are_decoded_to_str():
    client = RedisClient(url="redis://localhost:6379", logger=logging.getLogger("test"))
    kwargs = client._pool.connection_kwargs
    assert kwargs["decode_responses"] is True
    assert kwargs["encoding"] == "utf-8"


async def test_disconnect_closes_pool():
    client = RedisClient(url="redis://localhost:6379", logger=logging.getLogger("test"))
    closed = []

    async def fake_aclose():
        closed.append(True)

    client._pool.aclose = fake_aclose
    await client.disconnect()
    assert closed == [True]
