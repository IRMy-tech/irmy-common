import re
from typing import Optional, Literal
from pydantic import BaseModel, Field, model_validator, field_validator


_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
_EXCHANGE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]+$")


class GarbageCollectionRetention(BaseModel):
    """How many months of each kind of data to keep. A missing key means that kind
    of data is never purged."""

    alerts: Optional[int] = Field(None, ge=1)
    incidents: Optional[int] = Field(None, ge=1)
    auditLog: Optional[int] = Field(None, ge=1)
    onCall: Optional[int] = Field(None, ge=1)


class GarbageCollectionConfig(BaseModel):
    """The ``garbageCollection`` block of global_config.yaml. Read from the file only --
    environment variables do not override it. No block means disabled."""

    enabled: bool = False
    # Cron, 5 fields, evaluated in UTC by scheduler.
    schedule: str = "0 3 * * *"
    batchSize: int = Field(5000, ge=100, le=50000)
    # Below RabbitMQ's default consumer_timeout (30 min): the run holds its message unacked.
    maxDurationMinutes: int = Field(20, ge=1, le=25)
    retentionMonths: GarbageCollectionRetention = Field(default_factory=GarbageCollectionRetention)

    @field_validator("schedule")
    @classmethod
    def validate_schedule(cls, value: str) -> str:
        if len(value.split()) != 5:
            raise ValueError(f"garbageCollection.schedule must be a 5-field cron expression, got '{value}'")
        return value


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
    garbageCollection: Optional[GarbageCollectionConfig] = None

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


    @field_validator("rabbitmqVHost", mode="before")
    @classmethod
    def validate_vhost(cls, value):
        # Used as given ("dev" and "/dev" are different vhosts), the same rules as Irmy.Configuration.
        if value is None or value == "":
            raise ValueError(
                'RabbitMQ vhost (rabbitmqVHost / RABBITMQ_VHOST) must not be empty. Use "/" for the default vhost.'
            )
        if isinstance(value, str) and (value[0].isspace() or value[-1].isspace()):
            raise ValueError(
                f"RabbitMQ vhost (rabbitmqVHost / RABBITMQ_VHOST) must not start or end with whitespace, got '{value}'."
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
