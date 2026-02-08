"""
Metrics Collector

Collects and exposes Prometheus-compatible metrics for observability.

Supports Gold Tier requirements:
- FR-028: Emit structured logs (JSON format) for all significant operations
- FR-029: Expose key metrics (latencies, error rates, queue depths)
- FR-030: Provide health check endpoint aggregating MCP server statuses
"""

import time
from typing import Dict, Optional
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest


class MetricsCollector:
    """
    Prometheus-compatible metrics collector.

    Tracks:
    - API call latencies (p50, p95, p99) per integration
    - Error rates per integration and error type
    - Retry queue depth

    Per FR-029: Expose key metrics for observability
    """

    # Default histogram buckets for latency (in seconds)
    LATENCY_BUCKETS = (0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)

    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """
        Initialize metrics collector.

        Args:
            registry: Prometheus registry. Uses default if not provided.
        """
        self.registry = registry or CollectorRegistry()
        self._init_metrics()

    def _init_metrics(self) -> None:
        """Initialize all metric collectors."""

        # API call latency histogram
        self.api_call_latency = Histogram(
            "api_call_latency_seconds",
            "API call latency in seconds",
            ["integration", "operation"],
            buckets=self.LATENCY_BUCKETS,
            registry=self.registry,
        )

        # API error counter
        self.api_error_total = Counter(
            "api_error_total",
            "Total API errors",
            ["integration", "error_type"],
            registry=self.registry,
        )

        # API success counter
        self.api_success_total = Counter(
            "api_success_total",
            "Total successful API calls",
            ["integration", "operation"],
            registry=self.registry,
        )

        # Retry queue depth gauge
        self.retry_queue_depth = Gauge(
            "retry_queue_depth",
            "Current number of items in retry queue",
            ["status"],  # pending, retrying, failed
            registry=self.registry,
        )

        # MCP server health gauge
        self.mcp_server_health = Gauge(
            "mcp_server_health",
            "MCP server health status (1=healthy, 0=unhealthy)",
            ["server_id", "domain"],
            registry=self.registry,
        )

        # OAuth token status gauge
        self.oauth_token_status = Gauge(
            "oauth_token_status",
            "OAuth token status (1=valid, 0=expired/missing)",
            ["service"],
            registry=self.registry,
        )

        # CEO briefing generation gauge
        self.briefing_generation_status = Gauge(
            "briefing_generation_status",
            "Last CEO briefing generation status (1=success, 0=failure)",
            registry=self.registry,
        )

        # Audit log entries counter
        self.audit_entries_total = Counter(
            "audit_entries_total",
            "Total audit log entries",
            ["action_type", "result"],
            registry=self.registry,
        )

    def record_api_latency(
        self,
        integration: str,
        operation: str,
        latency_seconds: float,
    ) -> None:
        """
        Record API call latency.

        Args:
            integration: Service name (e.g., "xero", "twitter")
            operation: Operation type (e.g., "list_invoices", "post_tweet")
            latency_seconds: Call duration in seconds
        """
        self.api_call_latency.labels(
            integration=integration,
            operation=operation,
        ).observe(latency_seconds)

    def record_api_error(
        self,
        integration: str,
        error_type: str,
    ) -> None:
        """
        Record API error.

        Args:
            integration: Service name
            error_type: Error category (e.g., "rate_limit", "auth_expired", "server_error")
        """
        self.api_error_total.labels(
            integration=integration,
            error_type=error_type,
        ).inc()

    def record_api_success(
        self,
        integration: str,
        operation: str,
    ) -> None:
        """
        Record successful API call.

        Args:
            integration: Service name
            operation: Operation type
        """
        self.api_success_total.labels(
            integration=integration,
            operation=operation,
        ).inc()

    def set_retry_queue_depth(self, pending: int, retrying: int, failed: int) -> None:
        """
        Update retry queue depth metrics.

        Args:
            pending: Number of pending retries
            retrying: Number currently being retried
            failed: Number permanently failed
        """
        self.retry_queue_depth.labels(status="pending").set(pending)
        self.retry_queue_depth.labels(status="retrying").set(retrying)
        self.retry_queue_depth.labels(status="failed").set(failed)

    def set_mcp_server_health(
        self,
        server_id: str,
        domain: str,
        is_healthy: bool,
    ) -> None:
        """
        Update MCP server health metric.

        Args:
            server_id: Server identifier
            domain: Server domain (financial, social, communication)
            is_healthy: Whether server is healthy
        """
        self.mcp_server_health.labels(
            server_id=server_id,
            domain=domain,
        ).set(1 if is_healthy else 0)

    def set_oauth_token_status(self, service: str, is_valid: bool) -> None:
        """
        Update OAuth token status metric.

        Args:
            service: Service name
            is_valid: Whether token is valid (not expired)
        """
        self.oauth_token_status.labels(service=service).set(1 if is_valid else 0)

    def set_briefing_status(self, success: bool) -> None:
        """Update CEO briefing generation status."""
        self.briefing_generation_status.set(1 if success else 0)

    def record_audit_entry(self, action_type: str, result: str) -> None:
        """
        Record audit log entry creation.

        Args:
            action_type: Type of action logged
            result: Action result (success, failure, pending)
        """
        self.audit_entries_total.labels(
            action_type=action_type,
            result=result,
        ).inc()

    def get_metrics(self) -> bytes:
        """
        Get all metrics in Prometheus format.

        Returns:
            Prometheus-formatted metrics as bytes
        """
        return generate_latest(self.registry)

    def get_metrics_text(self) -> str:
        """
        Get all metrics as text.

        Returns:
            Prometheus-formatted metrics as string
        """
        return self.get_metrics().decode("utf-8")


class TimedOperation:
    """Context manager for timing operations."""

    def __init__(
        self,
        metrics: MetricsCollector,
        integration: str,
        operation: str,
    ):
        self.metrics = metrics
        self.integration = integration
        self.operation = operation
        self.start_time: Optional[float] = None

    def __enter__(self) -> "TimedOperation":
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.start_time:
            latency = time.time() - self.start_time
            self.metrics.record_api_latency(
                self.integration,
                self.operation,
                latency,
            )

            if exc_type is None:
                self.metrics.record_api_success(self.integration, self.operation)
            else:
                error_type = exc_type.__name__ if exc_type else "unknown"
                self.metrics.record_api_error(self.integration, error_type)


# Global metrics instance (can be overridden)
_metrics: Optional[MetricsCollector] = None


def get_metrics() -> MetricsCollector:
    """Get or create global metrics collector."""
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics


def set_metrics(metrics: MetricsCollector) -> None:
    """Set global metrics collector."""
    global _metrics
    _metrics = metrics
