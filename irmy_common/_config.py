import os
from pathlib import Path
from urllib.parse import quote

import yaml
from ._models import ConfigSchema


class Config:
    def __init__(self):
        self._secrets_path = self._get_env("SECRETS_LOCATION", "/var/run")
        self._yaml_config = self._read_yaml_file(self._get_env("CONFIG_LOCATION", "/global_config.yaml"))
        self._config = self._get_configs()

    def _get_configs(self) -> ConfigSchema:
        return ConfigSchema(
            version=self._yaml_config.get("version"),
            irmyHost=self._get_env("IRMY_HOST", self._yaml_config.get("irmyHost")),
            irmyProtocol=self._get_env("IRMY_PROTOCOL", self._yaml_config.get("irmyProtocol", "https")),
            postgreSQLHost=self._get_env("POSTGRESQL_HOST", self._yaml_config.get("postgreSQLHost")),
            postgreSQLPort=self._get_env("POSTGRESQL_PORT", self._yaml_config.get("postgreSQLPort", 5432)),
            postgreSQLDatabaseName=self._get_env("POSTGRESQL_DATABASE", self._yaml_config.get("postgreSQLDatabaseName", "irmy")),
            postgreSQLSchemaName=self._get_env("POSTGRESQL_SCHEMA", self._yaml_config.get("postgreSQLSchemaName", "public")),
            rabbitmqHost=self._get_env("RABBITMQ_HOST", self._yaml_config.get("rabbitmqHost")),
            rabbitmqPort=self._get_env("RABBITMQ_PORT", self._yaml_config.get("rabbitmqPort", 5672)),
            rabbitmqVHost=self._get_env("RABBITMQ_VHOST", self._yaml_config.get("rabbitmqVHost", "")),
            rabbitmqExchangeName=self._get_env("RABBITMQ_EXCHANGE_NAME", self._yaml_config.get("rabbitmqExchangeName")),
            redisHost=self._get_env("REDIS_HOST", self._yaml_config.get("redisHost")),
            redisPort=self._get_env("REDIS_PORT", self._yaml_config.get("redisPort", 6379)),
            postgreSQLUser=self._get_env("POSTGRESQL_USER", self._read_secret("postgreSQLUser")),
            postgreSQLPassword=self._get_env("POSTGRESQL_PASSWORD", self._read_secret("postgreSQLPassword")),
            rabbitUser=self._get_env("RABBITMQ_USER", self._read_secret("rabbitUser")),
            rabbitPassword=self._get_env("RABBITMQ_PASSWORD", self._read_secret("rabbitPassword")),
            redisUser=self._get_env("REDIS_USER", self._read_secret("redisUser")),
            redisPassword=self._get_env("REDIS_PASSWORD", self._read_secret("redisPassword")),
            jwtPrivateKey=self._get_env("JWT_PRIVATE_KEY", self._read_secret("jwtPrivateKey")),
            jwtPublicKey=self._get_env("JWT_PUBLIC_KEY", self._read_secret("jwtPublicKey")),
            encryptionKey=self._get_env("ENCRYPTION_KEY", self._read_secret("encryptionKey")),
            hmacSecret=self._get_env("HMAC_SECRET", self._read_secret("hmacSecret")),
            appPort=self._get_env("APP_PORT", 80),
            logLevel=self._get_env("LOG_LEVEL", "INFO"),
            platformVersion=self._get_env("PLATFORM_VERSION"),
            chartVersion=self._get_env("CHART_VERSION"),
            serviceVersion=self._get_service_version()
        )

    @staticmethod
    def _get_env(key: str, default=None) -> str | None:
        value = os.getenv(key, default)
        return value.strip() if isinstance(value, str) else value

    @staticmethod
    def _read_yaml_file(config_file_location: str) -> dict:
        try:
            with open(config_file_location, "r") as f:
                result = yaml.safe_load(f)
        except FileNotFoundError:
            raise ValueError(f"Config file {config_file_location} not found. Set CONFIG_LOCATION to its path")
        except yaml.YAMLError as e:
            raise ValueError(f"There was an error reading {config_file_location}. Is it yaml-formatted? Error: {e}")
        if result is None:
            raise ValueError(f"Config file {config_file_location} is empty")
        if not isinstance(result, dict):
            raise ValueError(f"Config file {config_file_location} must contain a YAML mapping, got {type(result).__name__}")
        return result

    def _read_secret(self, secret_name: str) -> str | None:
        prefix = self._secrets_path
        if len(prefix) > 1 and not prefix.endswith("/"):
            prefix += "/"
        try:
            with open(f"{prefix}{secret_name}", "r") as f:
                return f.read().strip()
        except FileNotFoundError:
            return None

    @classmethod
    def _get_service_version(cls) -> str:
        path = Path("Release.txt")
        content = path.read_text(encoding="utf-8")

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            if key.strip() == "version":
                return value.strip()

        raise ValueError(f"'version' key not found in {path}")

    @property
    def irmy_host(self) -> str:
        return self._config.irmyHost

    @property
    def postgres_schema(self) -> str:
        return self._config.postgreSQLSchemaName

    @property
    def rabbitmq_exchange_name(self) -> str:
        return self._config.rabbitmqExchangeName

    @property
    def jwt_private_key(self) -> str:
        return self._config.jwtPrivateKey

    @property
    def jwt_public_key(self) -> str:
        return self._config.jwtPublicKey

    @property
    def encryption_key(self) -> str:
        return self._config.encryptionKey

    @property
    def hmac_secret(self) -> str:
        return self._config.hmacSecret

    @property
    def jwt_aud(self) -> str:
        return f"{self._config.irmyProtocol}://{self._config.irmyHost}"

    @property
    def log_level(self) -> str:
        return self._config.logLevel

    @property
    def app_port(self) -> int:
        return self._config.appPort

    @property
    def service_version(self) -> str:
        return self._config.serviceVersion

    @property
    def platform_version(self) -> str:
        return self._config.platformVersion

    @property
    def chart_version(self) -> str | None:
        return self._config.chartVersion

    @staticmethod
    def _credentials(user: str | None, password: str | None) -> str:
        """``user:password@`` for a URL, percent-encoded so that characters like ``@ : / # ?``
        in credentials can't break URL parsing. Empty when neither is set."""
        if not user and not password:
            return ""
        userinfo = quote(user or "", safe="")
        if password:
            userinfo += f":{quote(password, safe='')}"
        return f"{userinfo}@"

    def get_postgres_url(self, synchronous: bool = False) -> str:
        credentials = self._credentials(self._config.postgreSQLUser, self._config.postgreSQLPassword)
        host = f"{credentials}{self._config.postgreSQLHost}:{self._config.postgreSQLPort}/{self._config.postgreSQLDatabaseName}"
        if synchronous:
            return f"postgresql://{host}"
        return f"postgresql+asyncpg://{host}"

    def get_rabbit_url(self) -> str:
        credentials = self._credentials(self._config.rabbitUser, self._config.rabbitPassword)
        return f"amqp://{credentials}{self._config.rabbitmqHost}:{self._config.rabbitmqPort}/{quote(self._config.rabbitmqVHost, safe='')}"

    def get_redis_url(self) -> str:
        credentials = self._credentials(self._config.redisUser, self._config.redisPassword)
        return f"redis://{credentials}{self._config.redisHost}:{self._config.redisPort}"
