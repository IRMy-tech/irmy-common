import pytest
from pydantic import ValidationError

from irmy_common import Config
from conftest import BASE_YAML


def test_reads_yaml(config_env):
    config = Config()
    assert config.irmy_host == "app.example.com"
    assert config.jwt_aud == "https://app.example.com"
    assert config.rabbitmq_exchange_name == "irmy"
    assert config.service_version == "1.2.3"
    assert config.platform_version == "2026.9.1"


def test_env_overrides_yaml(config_env, monkeypatch):
    monkeypatch.setenv("RABBITMQ_EXCHANGE_NAME", "custom-exchange")
    monkeypatch.setenv("IRMY_HOST", "other.example.com")
    config = Config()
    assert config.rabbitmq_exchange_name == "custom-exchange"
    assert config.irmy_host == "other.example.com"


def test_exchange_name_is_required(config_env):
    config_env.write_yaml(BASE_YAML.replace("rabbitmqExchangeName: irmy\n", ""))
    with pytest.raises(ValidationError, match="rabbitmqExchangeName"):
        Config()


@pytest.mark.parametrize("name", ["", "with space", "a/b"])
def test_exchange_name_is_validated(config_env, monkeypatch, name):
    monkeypatch.setenv("RABBITMQ_EXCHANGE_NAME", name)
    with pytest.raises(ValidationError, match="rabbitmqExchangeName"):
        Config()


def test_default_database_name(config_env):
    config_env.write_yaml(BASE_YAML.replace("postgreSQLDatabaseName: irmy\n", ""))
    assert Config().get_postgres_url().endswith("/irmy")


def test_port_accepts_full_range(config_env, monkeypatch):
    monkeypatch.setenv("REDIS_PORT", "65535")
    assert Config().get_redis_url() == "redis://redis:65535"


def test_missing_config_file(config_env, monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_LOCATION", str(tmp_path / "nope.yaml"))
    with pytest.raises(ValueError, match="not found"):
        Config()


def test_empty_config_file(config_env):
    config_env.write_yaml("")
    with pytest.raises(ValueError, match="is empty"):
        Config()


def test_non_mapping_config_file(config_env):
    config_env.write_yaml("- a\n- b\n")
    with pytest.raises(ValueError, match="YAML mapping"):
        Config()


def test_credentials_are_url_encoded(config_env):
    config_env.secret("postgreSQLUser", "svc")
    config_env.secret("postgreSQLPassword", "p@ss:w/rd#?")
    config_env.secret("rabbitUser", "rab@bit")
    config_env.secret("rabbitPassword", "x/y")
    config = Config()
    assert config.get_postgres_url() == "postgresql+asyncpg://svc:p%40ss%3Aw%2Frd%23%3F@pg:5432/irmy"
    assert config.get_postgres_url(synchronous=True).startswith("postgresql://svc:p%40ss")
    assert config.get_rabbit_url() == "amqp://rab%40bit:x%2Fy@rabbit:5672/"


def test_rabbit_vhost_in_url(config_env, monkeypatch):
    monkeypatch.setenv("RABBITMQ_VHOST", "dev")
    assert Config().get_rabbit_url() == "amqp://rabbit:5672/dev"


def test_redis_url_without_credentials_keeps_port(config_env, monkeypatch):
    monkeypatch.setenv("REDIS_PORT", "6380")
    assert Config().get_redis_url() == "redis://redis:6380"


def test_redis_url_with_user_and_password(config_env):
    config_env.secret("redisUser", "default")
    config_env.secret("redisPassword", "s3cr@t")
    assert Config().get_redis_url() == "redis://default:s3cr%40t@redis:6379"


def test_redis_url_password_only(config_env):
    config_env.secret("redisPassword", "s3cret")
    assert Config().get_redis_url() == "redis://:s3cret@redis:6379"


def test_secrets_location_captured_at_construction(config_env, monkeypatch, tmp_path):
    config_env.secret("hmacSecret", "0123456789abcdef")
    config = Config()
    monkeypatch.setenv("SECRETS_LOCATION", str(tmp_path / "elsewhere"))
    assert config._read_secret("hmacSecret") == "0123456789abcdef"


def test_dependencies_property_removed(config_env):
    assert not hasattr(Config(), "dependencies")


@pytest.mark.parametrize("vhost", ["dev", "Team_1", ""])
def test_vhost_valid(config_env, monkeypatch, vhost):
    monkeypatch.setenv("RABBITMQ_VHOST", vhost)
    assert Config().get_rabbit_url().endswith(f":5672/{vhost}")


@pytest.mark.parametrize("vhost", ["a/b", "my-vhost", "v host", "v.h"])
def test_vhost_invalid(config_env, monkeypatch, vhost):
    monkeypatch.setenv("RABBITMQ_VHOST", vhost)
    with pytest.raises(ValidationError, match="rabbitmqVHost"):
        Config()


def test_secrets_location_default(config_env, monkeypatch):
    monkeypatch.delenv("SECRETS_LOCATION")
    assert Config()._secrets_path == "/var/run"
