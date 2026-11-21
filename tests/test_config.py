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
    assert config.get_rabbit_url() == "amqp://rab%40bit:x%2Fy@rabbit:5672/%2F"


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


# Same cases as SharedConfigurationTests in Irmy.Configuration: both libraries must read the vhost alike.
@pytest.mark.parametrize(
    "yaml_line, env_value, expected_vhost, expected_path",
    [
        ('rabbitmqVHost: dev', None, "dev", "dev"),
        ('rabbitmqVHost: dev', "", "dev", "dev"),
        ('rabbitmqVHost: dev', "qa", "qa", "qa"),
        ('rabbitmqVHost: /dev', None, "/dev", "%2Fdev"),
        ('rabbitmqVHost: dev', "/dev", "/dev", "%2Fdev"),
        ('rabbitmqVHost: /', None, "/", "%2F"),
        ('rabbitmqVHost: a/b', None, "a/b", "a%2Fb"),
        ('rabbitmqVHost: irmy-dev.v1', None, "irmy-dev.v1", "irmy-dev.v1"),
        ('rabbitmqVHost: ""', "dev", "dev", "dev"),
        ('', None, "/", "%2F"),
        ('', "", "/", "%2F"),
    ],
)
def test_vhost_used_as_given(config_env, monkeypatch, yaml_line, env_value, expected_vhost, expected_path):
    config_env.write_yaml(BASE_YAML.replace('rabbitmqVHost: "/"\n', f"{yaml_line}\n"))
    if env_value is not None:
        monkeypatch.setenv("RABBITMQ_VHOST", env_value)
    config = Config()
    assert config._config.rabbitmqVHost == expected_vhost
    assert config.get_rabbit_url() == f"amqp://rabbit:5672/{expected_path}"


def test_vhost_other_spelling_is_not_read(config_env):
    config_env.write_yaml(BASE_YAML.replace('rabbitmqVHost: "/"\n', "rabbitmqVhost: dev\n"))
    assert Config()._config.rabbitmqVHost == "/"


@pytest.mark.parametrize(
    "yaml_line, env_value",
    [('rabbitmqVHost: ""', None), ('rabbitmqVHost: ""', ""), ("rabbitmqVHost:", None)],
)
def test_vhost_empty_rejected(config_env, monkeypatch, yaml_line, env_value):
    config_env.write_yaml(BASE_YAML.replace('rabbitmqVHost: "/"\n', f"{yaml_line}\n"))
    if env_value is not None:
        monkeypatch.setenv("RABBITMQ_VHOST", env_value)
    with pytest.raises(ValidationError, match="vhost .* must not be empty"):
        Config()


@pytest.mark.parametrize(
    "yaml_line, env_value",
    [
        ('rabbitmqVHost: " dev"', None),
        ('rabbitmqVHost: "dev "', None),
        ('rabbitmqVHost: "\\tdev"', None),
        ("rabbitmqVHost: dev", " dev"),
        ("rabbitmqVHost: dev", "dev "),
        ("rabbitmqVHost: dev", "   "),
    ],
)
def test_vhost_surrounding_whitespace_rejected(config_env, monkeypatch, yaml_line, env_value):
    config_env.write_yaml(BASE_YAML.replace('rabbitmqVHost: "/"\n', f"{yaml_line}\n"))
    if env_value is not None:
        monkeypatch.setenv("RABBITMQ_VHOST", env_value)
    with pytest.raises(ValidationError, match="must not start or end with whitespace"):
        Config()


def test_secrets_location_default(config_env, monkeypatch):
    monkeypatch.delenv("SECRETS_LOCATION")
    assert Config()._secrets_path == "/var/run"


def test_garbage_collection_defaults_to_disabled_without_block(config_env):
    gc = Config().garbage_collection
    assert gc.enabled is False
    assert gc.schedule == "0 3 * * *"
    assert gc.retentionMonths.alerts is None


def test_garbage_collection_reads_block(config_env):
    config_env.write_yaml(BASE_YAML + """\
garbageCollection:
  enabled: true
  schedule: "30 2 * * *"
  batchSize: 1000
  maxDurationMinutes: 10
  retentionMonths:
    alerts: 6
    auditLog: 24
""")
    gc = Config().garbage_collection
    assert gc.enabled is True
    assert gc.schedule == "30 2 * * *"
    assert gc.batchSize == 1000
    assert gc.maxDurationMinutes == 10
    assert gc.retentionMonths.alerts == 6
    assert gc.retentionMonths.auditLog == 24
    assert gc.retentionMonths.incidents is None
    assert gc.retentionMonths.onCall is None


def test_garbage_collection_empty_block_is_disabled(config_env):
    config_env.write_yaml(BASE_YAML + "garbageCollection:\n")
    assert Config().garbage_collection.enabled is False


@pytest.mark.parametrize("block", [
    "garbageCollection:\n  schedule: \"0 3 * *\"\n",
    "garbageCollection:\n  batchSize: 10\n",
    "garbageCollection:\n  maxDurationMinutes: 30\n",
    "garbageCollection:\n  retentionMonths:\n    alerts: 0\n",
])
def test_garbage_collection_is_validated(config_env, block):
    config_env.write_yaml(BASE_YAML + block)
    with pytest.raises(ValidationError, match="garbageCollection"):
        Config()
