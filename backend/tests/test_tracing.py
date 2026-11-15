from app.core import tracing


def test_tracing_stays_off_without_an_endpoint(monkeypatch):
    monkeypatch.setattr(tracing.settings, "OTEL_EXPORTER_OTLP_ENDPOINT", None)
    assert tracing.setup_tracing("test") is False
