import time
import logging
from typing import Dict, Any, Callable, TypeVar, Optional
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
import functools

logger = logging.getLogger(__name__)

class TelemetryException(Exception):
    """Base exception for telemetry operations."""
    pass

class TracerInitializationException(TelemetryException):
    """Raised when the TracerProvider fails to initialize."""
    pass

class SpanInjectionException(TelemetryException):
    """Raised when span context injection fails."""
    pass

def exponential_backoff_telemetry(max_retries: int = 3, base_delay: float = 0.5):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if i == max_retries - 1:
                        logger.error(f"Telemetry operation {func.__name__} failed: {str(e)}")
                        raise SpanInjectionException(f"Failed after retries: {e}")
                    logger.warning(f"Telemetry operation {func.__name__} failed, retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= 2
        return wrapper
    return decorator

class AgentTelemetry:
    """
    OpenTelemetry SDK wrapper for distributed tracing of Multi-Agent workflows.
    """
    def __init__(self, service_name: str = "AlignmentEngine"):
        try:
            provider = TracerProvider()
            processor = BatchSpanProcessor(ConsoleSpanExporter())
            provider.add_span_processor(processor)
            trace.set_tracer_provider(provider)
            self.tracer = trace.get_tracer(service_name)
            logger.info(f"Initialized OpenTelemetry Tracer for {service_name}")
        except Exception as e:
            raise TracerInitializationException(f"Could not init OTEL: {e}")

    @exponential_backoff_telemetry(max_retries=3)
    def inject_span(self, span_name: str, attributes: Dict[str, Any] = None) -> Any:
        """
        Creates and returns a context manager for a new span.
        Usage: with telemetry.inject_span("my_op") as span: ...
        """
        try:
            span = self.tracer.start_as_current_span(span_name)
            if attributes:
                for k, v in attributes.items():
                    span.set_attribute(k, str(v))
            return span
        except Exception as e:
            raise SpanInjectionException(f"Failed to start span {span_name}: {e}")

    def trace_method(self, span_name: str):
        """Decorator to trace class methods automatically."""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with self.inject_span(span_name, {"func": func.__name__}):
                    return func(*args, **kwargs)
            return wrapper
        return decorator
