#!/usr/bin/env python3

import psutil
import argparse
import time
import os
import pprint
import requests

from opentelemetry.sdk.resources import SERVICE_NAME, Resource

# otel libs for trace
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as OTLPSpanExporterGRPC
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as OTLPSpanExporterHTTP
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# otel libs for metrics
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from typing import Iterable
from opentelemetry.metrics import CallbackOptions, Observation

# otel libs for propagation
from opentelemetry import propagators
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

# otel libs for baggage
from opentelemetry import baggage
from opentelemetry.baggage.propagation import W3CBaggagePropagator

hostname = os.uname()[1]


def cpu_usage_callback(options: CallbackOptions) -> Iterable[Observation]:
    cpu_percents = psutil.cpu_percent(percpu=True)
    observations = []

    for i, cpu_percent in enumerate(cpu_percents):
        # unit is %
        observations.append(
            Observation(
                cpu_percent, {
                    "hostname": hostname, "cpu": i}))
    print("[cpu_usage_callback]")
    pprint.pprint(observations)
    return observations


def memory_usage_callback(options: CallbackOptions) -> Iterable[Observation]:
    mem = psutil.virtual_memory()

    observations = []
    # unit is MB
    observations.append(Observation(mem.used / 1024 / 1024,
                        {"hostname": hostname, "kind": "used"}))
    observations.append(Observation(mem.available / 1024 /
                        1024, {"hostname": hostname, "kind": "available"}))
    observations.append(Observation(mem.total / 1024 / 1024,
                        {"hostname": hostname, "kind": "total"}))
    print("[memory_usage_callback]")
    pprint.pprint(observations)
    return observations


def cpu_time_callback(options: CallbackOptions) -> Iterable[Observation]:
    observations = []
    with open("/proc/stat") as procstat:
        procstat.readline()  # skip the first line
        for line in procstat:
            if not line.startswith("cpu"):
                break
            cpu, *states = line.split()
            observations.append(Observation(
                int(states[0]) // 100, {"hostname": hostname, "cpu": cpu, "state": "user"}))
            observations.append(Observation(
                int(states[1]) // 100, {"hostname": hostname, "cpu": cpu, "state": "nice"}))
            observations.append(Observation(
                int(states[2]) // 100, {"hostname": hostname, "cpu": cpu, "state": "system"}))
    print("[cpu_time_callback]")
    pprint.pprint(observations)
    return observations


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-g', '--grpc', action='store_true')
    parser.add_argument('-m', '--metrics', action='store_true')
    parser.add_argument('-c', '--context-propagation', action='store_true')
    parser.add_argument('args', nargs='*')

    args, extra_args = parser.parse_known_args()

    # NOTE: SERVICE_NAME is "service.name"
    resource = Resource(attributes={
        SERVICE_NAME: "your-service-name"
    })
    trace.set_tracer_provider(TracerProvider(resource=resource))

    if args.metrics:
        meter = metrics.get_meter("example-meter")
        example_counter = meter.create_counter("example-counter")
        cpu_time_counter = meter.create_observable_counter(
            "system.cpu.time",
            callbacks=[cpu_time_callback],
            unit="s",
            description="CPU time"
        )
        cpu_usage_counter = meter.create_observable_counter(
            "system.cpu.usage",
            callbacks=[cpu_usage_callback],
            unit="percent",
            description="CPU usage"
        )
        memory_usage_counter = meter.create_observable_counter(
            "system.memory.usage",
            callbacks=[memory_usage_callback],
            unit="MBy",
            description="CPU memory usage"
        )

        # NOTE: There is not currently an OTLP/HTTP metric exporter.
        reader = PeriodicExportingMetricReader(
            exporter=OTLPMetricExporter(
                endpoint="localhost:4317", insecure=True),
            export_interval_millis=1000,
        )
        provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(provider)

    if args.grpc:
        otlp_exporter = OTLPSpanExporterGRPC(
            endpoint="localhost:4317", insecure=True)
    else:
        otlp_exporter = OTLPSpanExporterHTTP(
            endpoint="http://localhost:4318/v1/traces")
    trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))

    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("rootSpan"):
        with tracer.start_as_current_span("childSpan"):
            print("Hello world!")

    with tracer.start_as_current_span("my_span-with-attributes") as span:
        attributes = {"name": "hoge", "x": 123.4}
        for key, value in attributes.items():
            span.set_attribute(key, value)

    if args.context_propagation:
        with tracer.start_as_current_span("client operation"):
            try:
                url = "http://localhost:12345/hello"
                carrier = {}
                TraceContextTextMapPropagator().inject(carrier)
                # NOTE: example of carrier output
                # {
                #  'traceparent': '00-9345d022dfad27da68daeb28b2a7fba0-a85d9f58ddd66a4f-01'
                # }
                ctx = baggage.set_baggage("context", "parent")
                ctx = baggage.set_baggage("key1", "value1", context=ctx)
                print("context:", ctx)
                # NOTE: W3CBaggagePropagator adds below header
                # {'baggage': 'context=parent,key1=value1'}
                W3CBaggagePropagator().inject(carrier=carrier, context=ctx)
                print("carrier:", carrier)
                header = {
                    "traceparent": carrier["traceparent"],
                    "baggage": carrier["baggage"]
                }
                res = requests.get(url, headers=header)
                print(f"send a request to {url}, got {len(res.content)} bytes")
            except Exception as e:
                print(f"send a request to {url} failed {e}")

    if args.metrics:
        while True:
            example_counter.add(1, {"environment": "testing"})
            print("[LOG] add example_counter 1")
            time.sleep(1)


if __name__ == '__main__':
    main()
