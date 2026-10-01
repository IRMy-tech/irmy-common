import re
from typing import Optional, Literal
from pydantic import BaseModel, Field, model_validator, field_validator


_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
_EXCHANGE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]+$")
_VHOST_PATTERN = re.compile(r"^[A-Za-z0-9_]*$")


class ConfigSchema(BaseModel):
    # Basic configs from config file
    version: Literal[1]
    irmyHost: str
    irmyProtocol: Literal["http", "https"]
    postgreSQLHost: str
    postgreSQLPort: int = Field(ge=1, le=65535)
    postgreSQLDatabaseName: str
    postgreSQLSchemaName: str
    rabbitmqHost: str
    rabbitmqPort: int = Field(ge=1, le=65535)
    rabbitmqVHost: str
    rabbitmqExchangeName: str
    redisHost: str
    redisPort: int = Field(ge=1, le=65535)

    # Secrets
    encryptionKey: Optional[str] = None
    jwtPrivateKey: Optional[str] = None
    jwtPublicKey: Optional[str] = None
    postgreSQLPassword: Optional[str] = None
    postgreSQLUser: Optional[str] = None
    rabbitPassword: Optional[str] = None
    rabbitUser: Optional[str] = None
    hmacSecret: Optional[str] = Field(None, min_length=16, max_length=64)
    redisUser: Optional[str] = None
    redisPassword: Optional[str] = None

    # general environment variables
    logLevel: str
    appPort: int = Field(ge=1, le=65535)
    platformVersion: str
    chartVersion: Optional[str] = None
    serviceVersion: str


    @field_validator("rabbitmqVHost")
    @classmethod
    def validate_vhost(cls, value: str):
        if not _VHOST_PATTERN.match(value):
            raise ValueError(
                f"RabbitMQ Vhost may contain only letters, digits and underscores, got '{value}'"
            )
        return value

    @field_validator("rabbitmqExchangeName")
    @classmethod
    def validate_exchange_name(cls, value: str) -> str:
        if not _EXCHANGE_NAME_PATTERN.match(value):
            raise ValueError(
                "RabbitMQ exchange name must be non-empty and contain only letters, digits, "
                f"'-', '_', '.' or ':', got '{value}'"
            )
        return value

    @field_validator("platformVersion", "serviceVersion")
    @classmethod
    def validate_required_version(cls, value: str, info) -> str:
        if not _VERSION_PATTERN.match(value):
            raise ValueError(
                f"{info.field_name} must match format '<int>.<int>.<int>' "
                f"(e.g. '1.4.2' or '2026.08.1'), got '{value}'"
            )
        return value

    @field_validator("chartVersion")
    @classmethod
    def validate_optional_version(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not _VERSION_PATTERN.match(value):
            raise ValueError(
                f"chartVersion must match format '<int>.<int>.<int>' "
                f"(e.g. '1.4.2' or '2026.08.1'), got '{value}'"
            )
        return value

    @model_validator(mode="after")
    def validate_config_model(self):
        if self.logLevel.upper() not in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            raise ValueError("Log level must be one of 'DEBUG', 'INFO', 'WARNING' or 'ERROR'")
        return self
