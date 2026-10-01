"""Service-level Prometheus metrics shared by every IRMy service.

Metrics are registered in the default ``prometheus_client`` registry, so they are
exposed by the service's ``/metrics`` endpoint next to the HTTP metrics of the
instrumentator and the metrics of irmy-messaging / irmy-db. Nothing is registered
on import: call the functions below once at service startup (repeated calls are
safe).
"""
import threading

from prometheus_client import Gauge

from ._config import Config

_lock = threading.Lock()
_build_info: Gauge | None = None
_up: Gauge | None = None


def register_build_info(config: Config, service_name: str) -> None:
    """Publish ``irmy_build_info{service, version, platform_version, chart_version} 1``.

    ``chart_version`` is an empty string when the service is not deployed by the chart.
    Calling it again replaces the previous label set, so there is always one series.
    """
    global _build_info
    with _lock:
        if _build_info is None:
            _build_info = Gauge(
                "irmy_build_info",
                "Build and deployment versions of the service, value is always 1",
                ["service", "version", "platform_version", "chart_version"],
            )
        _build_info.clear()
        _build_info.labels(
            service=service_name,
            version=config.service_version,
            platform_version=config.platform_version,
            chart_version=config.chart_version or "",
        ).set(1)


def set_up(is_up: bool) -> None:
    """Set the ``irmy_up`` gauge: 1 while the service is running, 0 when it stops."""
    global _up
    with _lock:
        if _up is None:
            _up = Gauge("irmy_up", "Indicates if service is up and running")
        _up.set(1 if is_up else 0)
