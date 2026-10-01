# irmy-common

Common building blocks for IRMy Python services: configuration, logging, an async Redis
client, FastAPI JWT authentication and standard API error/response handling.

```bash
pip install irmy-common
```

Requires Python 3.12+. The import package is `irmy_common`.

Contents:
* [Logging](#logging)
* [Config Usage](#class-config-usage)
* [Redis client](#redis-client)
* [JWT dependencies](#jwt-dependencies)
* [Exceptions](#exceptions)
* [Metrics](#metrics)

## Usage

### Logging

```python
import uuid
from irmy_common import get_logger

logger = get_logger(log_level="DEBUG",
                    name="app_logger",
                    app_name="my-application",
                    app_id=str(uuid.uuid4()))
logger.info("Some info message")
logger.error("Some error message")
```

### class Config usage

```python
from irmy_common import Config

config = Config()

# Get PostgreSQL URL
print(config.get_postgres_url())

# Specific component property
print(config.postgres_schema)

# Specific secret:
print(config.hmac_secret)

# RabbitMQ exchange to publish/consume on
print(config.rabbitmq_exchange_name)
```

`Config` reads `global_config.yaml` (path from `CONFIG_LOCATION`, default `/global_config.yaml`),
secret files (directory from `SECRETS_LOCATION`, default `/var/run`) and environment variables.
Precedence for every field: **env var > YAML/secret file > default**.

| Field | YAML key / secret file | Env var | Default |
|---|---|---|---|
| Public host | `irmyHost` | `IRMY_HOST` | required |
| Public protocol | `irmyProtocol` | `IRMY_PROTOCOL` | `https` |
| PostgreSQL | `postgreSQLHost`, `postgreSQLPort`, `postgreSQLDatabaseName`, `postgreSQLSchemaName` | `POSTGRESQL_HOST`, `POSTGRESQL_PORT`, `POSTGRESQL_DATABASE`, `POSTGRESQL_SCHEMA` | host required, `5432`, `irmy`, `public` |
| RabbitMQ | `rabbitmqHost`, `rabbitmqPort`, `rabbitmqVHost`, `rabbitmqExchangeName` | `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_VHOST`, `RABBITMQ_EXCHANGE_NAME` | host required, `5672`, `""`, exchange required |
| Redis | `redisHost`, `redisPort` | `REDIS_HOST`, `REDIS_PORT` | host required, `6379` |
| Secrets | `postgreSQLUser`, `postgreSQLPassword`, `rabbitUser`, `rabbitPassword`, `redisUser`, `redisPassword`, `jwtPrivateKey`, `jwtPublicKey`, `encryptionKey`, `hmacSecret` (files) | upper snake case, e.g. `POSTGRESQL_PASSWORD`, `RABBITMQ_USER`, `HMAC_SECRET` | none |
| Service | — | `APP_PORT`, `LOG_LEVEL`, `PLATFORM_VERSION`, `CHART_VERSION` | `80`, `INFO`, required, none |

The service version is read from `version=<x.y.z>` in `Release.txt` in the working directory.

### Redis client

```python
import uuid
from irmy_common import RedisClient, Config, get_logger

# Create logger instance
logger = get_logger(log_level="DEBUG",
                    name="app_logger",
                    app_name="my-application",
                    app_id=str(uuid.uuid4()))

config = Config()
redis_client = RedisClient(url=config.get_redis_url(), logger=logger)

async def main():
    await redis_client.put(key="test", value="test", expire=10)
    await redis_client.get("test")
    await redis_client.healthcheck()
    await redis_client.disconnect()
```

### JWT dependencies
During start of the application:

```python
import uuid
from irmy_common import jwt_dependencies, Config, RedisClient, get_logger

logger = get_logger(log_level="DEBUG",
                    name="app_logger",
                    app_name="my-application",
                    app_id=str(uuid.uuid4()))
config = Config()
redis_client = RedisClient(url=config.get_redis_url(), logger=logger)

jwt_dependencies.init_dependencies(logger=logger, config=config, redis_client=redis_client)
```
Then, in your API endpoints:
```python
from fastapi import Depends
from irmy_common.jwt_dependencies import JWTData, verify_jwt, GlobalPermission

async def my_api(jwt_data: JWTData = Depends(verify_jwt)):
    print(f"{jwt_data.requester} requests something")
    print(f"Permissions: {jwt_data.Permissions}")
    print(f"Does user has write permissions to Applications: {jwt_data.has_permission(GlobalPermission.MANAGE_SERVICES_APPS_ENVS)}")
```

### Exceptions

Raise HTTP Exception:
```python
from irmy_common.exceptions import IrmyHTTPException
from irmy_common.response_codes import ApiErrorCodes

raise IrmyHTTPException(status_code=ApiErrorCodes.BAD_REQUEST, message="Bad request")
```

Raise general exception:
```python
from irmy_common.exceptions import IrmyException

raise IrmyException(message="Some exception")
```

Register API exceptions handlers
```python
from fastapi import FastAPI
from irmy_common.exceptions import register_exceptions_handler

app = FastAPI()
register_exceptions_handler(app)
```

Usage of API response for CREATE, UPDATE and DELETE actions:

```python
import uuid
from fastapi import FastAPI
from irmy_common.responses import basic_http_response
from irmy_common.response_codes import ApiResponseCodes, COMMON_RESPONSES, COMMON_UPDATE_RESPONSES, COMMON_CREATE_RESPONSES


app = FastAPI()

@app.post("/update", responses={**COMMON_RESPONSES, **COMMON_UPDATE_RESPONSES})
async def do_update_request():
    return basic_http_response(response_code=ApiResponseCodes.UPDATE_DELETE)


@app.post("/create_one", responses={**COMMON_RESPONSES, **COMMON_CREATE_RESPONSES})
async def do_create_request():
    return basic_http_response(response_code=ApiResponseCodes.CREATE, resource_id=uuid.uuid4())


@app.post("/create_many", responses={**COMMON_RESPONSES, **COMMON_CREATE_RESPONSES})
async def create_many_resources():
    return basic_http_response(response_code=ApiResponseCodes.CREATE, many_resource_ids=[uuid.uuid4()])
```

### Metrics

Service-level metrics, registered in the default `prometheus_client` registry, so
they are served by the service's `/metrics` endpoint together with the HTTP
metrics of the instrumentator and the metrics of irmy-messaging / irmy-db.
Call once at startup; repeated calls are safe.

```python
from irmy_common import Config
from irmy_common.metrics import register_build_info, set_up

config = Config()
register_build_info(config, service_name="my-service")
set_up(True)   # and set_up(False) on shutdown
```

| Metric | Type | Labels |
|---|---|---|
| `irmy_build_info` | Gauge, always `1` | `service`, `version`, `platform_version`, `chart_version` (empty when not set) |
| `irmy_up` | Gauge, `1` / `0` | — |
