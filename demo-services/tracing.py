"""Bounded trace retention for the disposable demo; never retain headers/bodies."""

from collections import deque
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import (
    SpanExporter,
    SpanExportResult,
    SimpleSpanProcessor,
)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor


class BoundedExporter(SpanExporter):
    def __init__(self):
        self.spans = deque(maxlen=100)

    def export(self, spans):
        for span in spans:
            self.spans.append(
                {
                    "trace_id": format(span.context.trace_id, "032x"),
                    "span_id": format(span.context.span_id, "016x"),
                    "parent_span_id": format(span.parent.span_id, "016x")
                    if span.parent
                    else None,
                    "name": span.name[:120],
                    "start_time_ns": span.start_time,
                    "duration_ms": (span.end_time - span.start_time) / 1e6,
                    "status": span.status.status_code.name,
                    "attributes": {
                        key: value
                        for key, value in span.attributes.items()
                        if key
                        in {
                            "http.route",
                            "http.status_code",
                            "http.response.status_code",
                            "http.method",
                            "http.request.method",
                        }
                    },
                }
            )
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass


def configure(app, service):
    exporter = BoundedExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": service}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=provider, excluded_urls="health,ready,metrics,control"
    )
    app.state.trace_provider = provider
    app.state.trace_exporter = exporter
    return provider
