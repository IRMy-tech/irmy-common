import pytest


BASE_YAML = """\
version: 1
irmyHost: app.example.com
irmyProtocol: https
postgreSQLHost: pg
postgreSQLPort: 5432
postgreSQLDatabaseName: irmy
postgreSQLSchemaName: public
rabbitmqHost: rabbit
rabbitmqPort: 5672
rabbitmqVHost: ""
rabbitmqExchangeName: irmy
redisHost: redis
redisPort: 6379
"""


@pytest.fixture
def config_env(tmp_path, monkeypatch):
    """Isolated config environment: YAML file, empty secrets dir, Release.txt in cwd.

    Returns a helper to (re)write the YAML and add secret files."""
    for var in (
        "IRMY_HOST", "IRMY_PROTOCOL", "POSTGRESQL_HOST", "POSTGRESQL_PORT", "POSTGRESQL_DATABASE",
        "POSTGRESQL_SCHEMA", "RABBITMQ_HOST", "RABBITMQ_PORT", "RABBITMQ_VHOST", "RABBITMQ_EXCHANGE_NAME",
        "REDIS_HOST", "REDIS_PORT", "POSTGRESQL_USER", "POSTGRESQL_PASSWORD", "RABBITMQ_USER",
        "RABBITMQ_PASSWORD", "REDIS_USER", "REDIS_PASSWORD", "JWT_PRIVATE_KEY", "JWT_PUBLIC_KEY",
        "ENCRYPTION_KEY", "HMAC_SECRET", "APP_PORT", "LOG_LEVEL", "CHART_VERSION",
    ):
        monkeypatch.delenv(var, raising=False)

    secrets = tmp_path / "secrets"
    secrets.mkdir()
    config_file = tmp_path / "global_config.yaml"
    config_file.write_text(BASE_YAML)
    (tmp_path / "Release.txt").write_text("version=1.2.3\n")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CONFIG_LOCATION", str(config_file))
    monkeypatch.setenv("SECRETS_LOCATION", str(secrets))
    monkeypatch.setenv("PLATFORM_VERSION", "2026.9.1")

    class Env:
        yaml_path = config_file

        @staticmethod
        def write_yaml(text: str) -> None:
            config_file.write_text(text)

        @staticmethod
        def secret(name: str, value: str) -> None:
            (secrets / name).write_text(value)

    return Env
