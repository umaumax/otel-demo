#!/usr/bin/env python3

import asyncio
import argparse

from fastapi import FastAPI, HTTPException, Request

from opentelemetry.sdk.resources import SERVICE_NAME, Resource

# otel libs for trace
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as OTLPSpanExporterGRPC
# from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as OTLPSpanExporterHTTP
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# otel libs for propagation
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

app = FastAPI()

resource = Resource(attributes={
    SERVICE_NAME: "otel-demo-server"
})
otlp_exporter = OTLPSpanExporterGRPC(endpoint="localhost:4317", insecure=True)
trace.set_tracer_provider(TracerProvider(resource=resource))
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))
tracer = trace.get_tracer(__name__)


@app.get("/hello")
async def hello(request: Request):
    traceparent = request.headers.get('traceparent')
    carrier = {"traceparent": traceparent}
    ctx = TraceContextTextMapPropagator().extract(carrier)

    with tracer.start_as_current_span("/hello", context=ctx):
        # for logs
        print(request.headers)
        return {"message": "hello world!"}


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-p', '--port', default=12345)
    parser.add_argument('args', nargs='*')

    args, extra_args = parser.parse_known_args()

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=args.port)


if __name__ == '__main__':
    main()
