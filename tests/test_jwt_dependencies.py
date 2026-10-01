import logging
import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.security import HTTPAuthorizationCredentials

from irmy_common import jwt_dependencies
from irmy_common.exceptions import IrmyHTTPException
from irmy_common.jwt_dependencies import GlobalPermission, verify_jwt

AUDIENCE = "https://app.example.com"
ISSUER = "usermanagement"

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_pem = _private_key.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
).decode()


class _FakeConfig:
    jwt_public_key = _public_pem
    jwt_aud = AUDIENCE


class _FakeRedis:
    def __init__(self, invalidated: set[str] | None = None, value=None):
        self._invalidated = invalidated or set()
        self._value = value

    async def get(self, key: str):
        if key.removeprefix("jwt:invalidated:") in self._invalidated:
            return "1"
        return self._value


class _CapturingHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record):
        self.messages.append(record.getMessage())


@pytest.fixture
def log():
    handler = _CapturingHandler()
    logger = logging.getLogger("jwt-test")
    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)
    return logger, handler


@pytest.fixture(autouse=True)
def reset_dependencies():
    yield
    jwt_dependencies._logger = None
    jwt_dependencies._config = None
    jwt_dependencies._redis = None


def _claims(**overrides) -> dict:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": now + 300,
        "jti": str(uuid.uuid4()),
        "accessType": "user",
        "userEmail": "user@example.com",
        "userId": str(uuid.uuid4()),
        "userGroups": [],
        "roleId": str(uuid.uuid4()),
        "roleName": "Owner",
        "rolePermissions": int(GlobalPermission.CAN_LOGIN | GlobalPermission.MANAGE_ALL_ALERTS_INCIDENTS),
    }
    claims.update(overrides)
    return {k: v for k, v in claims.items() if v is not None}


def _credentials(claims: dict) -> HTTPAuthorizationCredentials:
    token = jwt.encode(claims, _private_key, algorithm="RS256")
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


async def _verify(claims: dict, logger, redis=None):
    jwt_dependencies.init_dependencies(logger=logger, config=_FakeConfig(), redis_client=redis or _FakeRedis())
    return await verify_jwt(credentials=_credentials(claims), config=_FakeConfig(), logger=logger)


async def _assert_401(claims: dict, logger, redis=None):
    with pytest.raises(IrmyHTTPException) as exc:
        await _verify(claims, logger, redis)
    assert exc.value.status_code == 401


async def test_valid_token(log):
    logger, _ = log
    data = await _verify(_claims(), logger)
    assert data.AccessType == "user"
    assert data.has_permission(GlobalPermission.VIEW_ALL_ALERTS_INCIDENTS)  # implied
    assert not data.has_permission(GlobalPermission.MANAGE_PLUGINS)


@pytest.mark.parametrize("claim", ["exp", "iat", "jti", "iss", "aud"])
async def test_required_claims(log, claim):
    logger, handler = log
    await _assert_401(_claims(**{claim: None}), logger)
    assert any(claim in m for m in handler.messages)


async def test_expired_token(log):
    logger, _ = log
    await _assert_401(_claims(exp=int(time.time()) - 10, iat=int(time.time()) - 100, nbf=None), logger)


async def test_invalidated_token(log):
    logger, handler = log
    claims = _claims()
    await _assert_401(claims, logger, _FakeRedis(invalidated={claims["jti"]}))
    assert any("invalidated" in m for m in handler.messages)


async def test_redis_unavailable_does_not_reject(log):
    # RedisClient returns None when Redis is down; tokens are accepted by design.
    logger, _ = log
    data = await _verify(_claims(), logger, _FakeRedis(value=None))
    assert data.RoleName == "Owner"


@pytest.mark.parametrize("permissions", [None, "abc", -1, 1 << 20])
async def test_invalid_role_permissions_is_401(log, permissions):
    logger, handler = log
    await _assert_401(_claims(rolePermissions=permissions), logger)
    assert any("rolePermissions" in m for m in handler.messages)


async def test_invalid_claims_is_401(log):
    logger, handler = log
    await _assert_401(_claims(userEmail=None), logger)
    assert any("invalid claims" in m and "accessType='user'" in m for m in handler.messages)


async def test_unknown_access_type_is_401(log):
    logger, handler = log
    await _assert_401(_claims(accessType="robot"), logger)
    assert any("invalid claims" in m for m in handler.messages)


async def test_missing_credentials_is_401(log):
    logger, _ = log
    with pytest.raises(IrmyHTTPException) as exc:
        await verify_jwt(credentials=None, config=_FakeConfig(), logger=logger)
    assert exc.value.status_code == 401


async def test_not_initialized_redis_raises(log):
    # Guard: using verify_jwt without init_dependencies() must fail loudly.
    logger, _ = log
    with pytest.raises(AttributeError):
        await verify_jwt(credentials=_credentials(_claims()), config=_FakeConfig(), logger=logger)
