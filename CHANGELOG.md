# Changelog
## 1.6.1
* `[project.urls]` in `pyproject.toml`: the package metadata links to the home page, the
  documentation, the source, the issue tracker and the changelog (the "Project links" of the
  package page on PyPI).

## 1.6.0
* `validation.storable_text(value)` / `validation.storable(value)`: NUL (`\u0000`) and lone
  UTF-16 surrogates (`\ud800`..`\udfff`), which PostgreSQL cannot store, are replaced by their
  escape written out as text (the six characters `\u0000`). `storable` walks a JSON-like value
  (dicts — keys included — lists, strings).
* `text_str` applies `storable_text` before trimming and the length check: such a value is
  saved with the escape text instead of reaching the database as is. The escape counts towards
  the length limit.

## 1.5.0
* `RedisClient` gives up on an unreachable Redis instead of hanging: connecting and every
  command time out after 2 s (`socket_connect_timeout` / `socket_timeout`, overridable in the
  constructor). Before, a Redis host that did not answer (a dead node, a network partition)
  blocked every call — and with it JWT checks and health checks — for the OS TCP timeout.
  A failed call still returns `None` (`stream_add`: `False`, `healthcheck`: `False`).
* `ApiErrorCodes.BAD_GATEWAY` (502) and `ApiErrorCodes.GATEWAY_TIMEOUT` (504);
  `error_responses()` accepts 502 and 504.
* `Release.txt` matches the package version again (it still said 1.3.0 in 1.4.0).

## 1.4.0
* `Config.garbage_collection` (`GarbageCollectionConfig`): the optional `garbageCollection`
  block of `global_config.yaml` — `enabled`, `schedule` (5-field cron, UTC), `batchSize`,
  `maxDurationMinutes`, `retentionMonths.{alerts,incidents,auditLog,onCall}`. Read from the
  file only, no env overrides; no block = disabled.

## 1.3.0
* RabbitMQ vhost: the default is `/` (was `""`) and any vhost name is accepted, as given —
  `dev` and `/dev` are different vhosts; `get_rabbit_url()` percent-encodes it (`/` → `%2F`).
  The rule "letters, digits and underscores only" is removed, so the chart default `/`, and
  names such as `irmy-dev`, no longer fail validation.
* The vhost is required: an empty value (`rabbitmqVHost: ""` or an empty key) or one that
  starts or ends with whitespace fails validation, with a message naming
  `rabbitmqVHost / RABBITMQ_VHOST`. An empty `RABBITMQ_VHOST` counts as not set, and the
  value is no longer stripped.
* Same rules as `Irmy.Configuration` 1.1.0.

## 1.2.0
* `RedisClient.stream_add(batches)` — append to Redis streams in one `MULTI`/`EXEC` round trip,
  each `StreamBatch` trimmed to `max_len` entries (exact `MAXLEN`) and, optionally, to entries newer
  than `min_id` (`XTRIM MINID`). Returns False instead of raising when Redis fails again after
  reconnecting, so the caller can keep its entries.
* `RedisClient.stream_range(key, start, end, count, reverse)` — `XRANGE` / `XREVRANGE`.

## 1.1.0
* `openapi` — documentation helpers for the "API documentation (OpenAPI)" standard:
  `ErrorResponse` / `ValidationErrorResponse` body models, `error_responses(*codes)`
  for an endpoint's exact error codes (schema, description, example), and
  `configure_openapi(app)`, which removes FastAPI's auto-generated 422 response.
* `validation` — constrained request types per "User input validation", trimmed
  before validation: `name_str()`, `text_str()`, `key_str()`, `Tags`, `TimeZoneName`.
* `COMMON_*` responses in `response_codes` now carry the error body schema and an
  example (descriptions unchanged). They are legacy: prefer `error_responses`.
* `CreateResourceModel` / `CreateManyResourcesModel` fields have descriptions and examples.

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
