# Changelog
## 1.0.0
Initial release.

* `Config` — service configuration from `global_config.yaml`, secret files and
  environment variables (env > YAML/secret file > default), validated with pydantic.
  Includes PostgreSQL, RabbitMQ (with `rabbitmqExchangeName`) and Redis settings and
  URL builders with percent-encoded credentials.
* `get_logger()` — stdout logger with JSON or plain string output.
* `RedisClient` — async Redis wrapper returning `str`, with a single
  reconnect-and-retry on errors.
* `jwt_dependencies` — FastAPI dependency `verify_jwt` for RS256 tokens (required
  `exp`, `iat`, `jti`, `iss`, `aud` claims, revocation check in Redis) and the
  `GlobalPermission` bitmask.
* `exceptions`, `response_codes`, `responses` — `IrmyException` / `IrmyHTTPException`,
  FastAPI exception handlers and standard 201/204 responses.
* `metrics` — service-level Prometheus metrics: `irmy_build_info` (service,
  version, platform and chart version) and `irmy_up`.
