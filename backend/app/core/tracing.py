"""OpenTelemetry traces for the API, the workers and every OpenAI call.

Off unless OTEL_EXPORTER_OTLP_ENDPOINT is set. Any OTLP backend works: Jaeger in
docker-compose, or Langfuse by pointing the endpoint and headers at it (see
.env.example). OpenAI spans carry model, token counts and latency; prompts and
completions are only captured if OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT
is turned on, because they hold customer and scraped text.
"""

from app.core.config import settings

_configured = False


def setup_tracing(service_name: str) -> bool:
    """Start exporting this process's spans. True if tracing is on."""
    global _configured
    if not settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        return False
    if _configured:
        return True
    # imported here so processes with tracing off don't load any of it
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT.rstrip("/")
    # headers (Langfuse auth) come from OTEL_EXPORTER_OTLP_HEADERS
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"))
    )
    trace.set_tracer_provider(provider)
    OpenAIInstrumentor().instrument()
    # in the API too: it links a request to the tasks it enqueues
    CeleryInstrumentor().instrument()
    _configured = True
    return True
