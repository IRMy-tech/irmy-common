import jwt
from uuid import UUID
from enum import IntFlag, StrEnum
from logging import Logger
from fastapi import Depends
from typing import Optional, Literal, List
from pydantic import BaseModel, ValidationError, model_validator
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ._config import Config
from ._redis_client import RedisClient
from .exceptions import IrmyHTTPException
from .response_codes import ApiErrorCodes


class GlobalPermission(IntFlag):
    CAN_LOGIN                    = 1
    VIEW_ALL_ALERTS_INCIDENTS    = 2
    MANAGE_ALL_ALERTS_INCIDENTS  = 4
    MANAGE_SERVICES_APPS_ENVS    = 8
    MANAGE_CONNECTIONS_TEMPLATES = 16
    MANAGE_IDENTITY              = 32
    MANAGE_PLUGINS               = 64
    VIEW_AUDIT_LOG               = 128


class _GlobalPermissionNames(StrEnum):
    CAN_LOGIN                    = "Can Login"
    VIEW_ALL_ALERTS_INCIDENTS    = "View All Alerts & Incidents"
    MANAGE_ALL_ALERTS_INCIDENTS  = "Manage All Alerts & Incidents"
    MANAGE_SERVICES_APPS_ENVS    = "Manage Services, Applications, Environments + Global & Environment-scoped Rules"
    MANAGE_CONNECTIONS_TEMPLATES = "Manage Connections & Templates"
    MANAGE_IDENTITY              = "Manage Identity"
    MANAGE_PLUGINS               = "Manage Plugins"
    VIEW_AUDIT_LOG               = "View Audit Log"


# Permissions that, when granted, imply another permission's bit for `has_permission()`
# checks (e.g. managing alerts/incidents implies the ability to view them), per the
# "Includes" column of the platform's permissions model.
_IMPLIED_PERMISSIONS: dict[GlobalPermission, GlobalPermission] = {
    GlobalPermission.MANAGE_ALL_ALERTS_INCIDENTS: GlobalPermission.VIEW_ALL_ALERTS_INCIDENTS,
}


def _get_permission_names(bitmask: str) -> List[str]:
    try:
        bitmask = int(bitmask)
    except (TypeError, ValueError):
        raise ValueError("Bitmask must be an integer, got {!r}".format(bitmask))
    if bitmask < 0:
        raise ValueError("Bitmask must be non-negative, got {}".format(bitmask))

    known_mask = 0
    for perm in GlobalPermission:
        known_mask |= int(perm.value)  # type: ignore[operator]

    unknown_bits = bitmask & ~known_mask
    if unknown_bits:
        raise ValueError(
            "Bitmask 0x{:x} contains unknown bits: 0x{:x}".format(bitmask, unknown_bits)
        )

    result = []  # type: List[str]
    for perm in GlobalPermission:
        perm_value = int(perm.value)  # type: ignore[operator]
        if not (perm_value & bitmask):
            continue
        perm_name = perm.name  # type: ignore[operator]
        result.append(str(_GlobalPermissionNames[perm_name].value))  # type: ignore[operator]

    return result


class JWTData(BaseModel):
    TokenId: UUID
    AccessType: Literal["user", "serviceAccount"]
    UserEmail: Optional[str] = None
    UserId: Optional[UUID] = None
    ServiceAccount: Optional[str] = None
    ServiceAccountId: Optional[UUID] = None
    UserGroups: Optional[List[UUID]] = None
    RoleId: Optional[UUID]
    RoleName: str
    Permissions: int
    PermissionNames: list[str]

    @model_validator(mode="before")
    @classmethod
    def validate_fields(cls, values: dict):
        if values.get("AccessType") == "user":
            if values.get("UserEmail") is None:
                raise ValueError("User email must be specified for accessType 'user'")
            if values.get("UserId") is None:
                raise ValueError("User ID must be specified for accessType 'user'")
            if values.get("UserGroups") is None:
                raise ValueError("User groups must be specified for accessType 'user'")
        elif values.get("AccessType") == "serviceAccount":
            if values.get("ServiceAccount") is None:
                raise ValueError("Service account name must be specified for accessType 'serviceAccount'")
            if values.get("ServiceAccountId") is None:
                raise ValueError("Service account ID must be specified for accessType 'serviceAccount'")
        else:
            raise ValueError("Invalid accessType")
        return values

    def has_permission(self, permission: GlobalPermission) -> bool:
        granted = self.Permissions or 0
        for held, implied in _IMPLIED_PERMISSIONS.items():
            if granted & held:
                granted |= implied
        return bool(granted & permission)

    @property
    def requester(self) -> str:
        return f"{self.AccessType.capitalize()} '{self.UserId if self.AccessType == 'user' else self.ServiceAccount}'"



_logger: Optional[Logger] = None
_config: Optional[Config] = None
_jwt_issuer = "usermanagement"
_redis: Optional[RedisClient] = None


def init_dependencies(logger: Logger, config: Config, redis_client: RedisClient | None):
    global _logger, _config, _jwt_issuer, _redis
    _logger = logger
    _config = config
    _redis = redis_client


def get_logger() -> Logger:
    if _logger is None:
        raise RuntimeError("Logger not initialized")
    return _logger


def get_config() -> Config:
    if _config is None:
        raise RuntimeError("Config not initialized")
    return _config


async def verify_jwt(
        credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
        config: Config = Depends(get_config),
        logger: Logger = Depends(get_logger)
) -> JWTData:
    """Validates JWT token and returns user data"""
    if not credentials:
        raise IrmyHTTPException(status_code=ApiErrorCodes.UNAUTHORIZED, message="Unauthorized")

    token = credentials.credentials

    try:
        payload: dict = jwt.decode(
            jwt=token,
            key=config.jwt_public_key,
            algorithms=["RS256"],
            audience=config.jwt_aud,
            issuer=_jwt_issuer,
            options={
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "verify_aud": True,
                "verify_iss": True,
                # PyJWT only verifies a claim that is present; without "require" a token
                # lacking e.g. "exp" would be accepted and never expire.
                "require": ["exp", "iat", "jti", "iss", "aud"],
            }
        )
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token has expired")
        raise IrmyHTTPException(status_code=ApiErrorCodes.UNAUTHORIZED, message="Unauthorized")
    except jwt.InvalidTokenError as e:
        logger.warning(f"JWT validation failed. Error: {e}")
        raise IrmyHTTPException(status_code=ApiErrorCodes.UNAUTHORIZED, message="Unauthorized")

    token_id = payload.get("jti")
    if await _redis.get(f"jwt:invalidated:{token_id}"):
        logger.warning(f"JWT token with ID {token_id} was invalidated")
        raise IrmyHTTPException(status_code=ApiErrorCodes.UNAUTHORIZED, message="Unauthorized")

    try:
        return JWTData(
            TokenId=token_id,
            AccessType=payload.get("accessType"),
            UserEmail=payload.get("userEmail"),
            UserId=payload.get("userId"),
            ServiceAccount=payload.get("serviceAccount"),
            ServiceAccountId=payload.get("serviceAccountId"),
            UserGroups=payload.get("userGroups"),
            RoleId=payload.get("roleId"),
            RoleName=payload.get("roleName"),
            Permissions=payload.get("rolePermissions"),
            PermissionNames=_get_permission_names(payload.get("rolePermissions"))
        )
    except ValidationError as e:
        # Signature is valid, so this is a token usermanagement issued with unexpected content.
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or 'token'}: {err['msg']}" for err in e.errors()
        )
        logger.warning(
            f"JWT token with ID {token_id} has invalid claims "
            f"(accessType={payload.get('accessType')!r}): {problems}"
        )
        raise IrmyHTTPException(status_code=ApiErrorCodes.UNAUTHORIZED, message="Unauthorized")
    except ValueError as e:
        logger.warning(
            f"JWT token with ID {token_id} has invalid rolePermissions "
            f"{payload.get('rolePermissions')!r}: {e}"
        )
        raise IrmyHTTPException(status_code=ApiErrorCodes.UNAUTHORIZED, message="Unauthorized")
