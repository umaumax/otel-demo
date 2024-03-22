# otel-demo

## how to setup
``` bash
pip3 install 'opentelemetry-api==1.21.0'
pip3 install 'opentelemetry-sdk==1.21.0'
pip3 install 'opentelemetry-exporter-otlp==1.21.0'
```

## how to run otel servers environment
``` bash
chmod 0777 ./data/
docker compose up
```

`./data/dump.json` includes trace and metrics data

## how to access web GUI
* Jaeger UI: http://localhost:16686/search
* Zipkin: http://localhost:9411/zipkin/

## how to stop
``` bash
docker compose down
```

## how to debug containers
``` bash
wget https://busybox.net/downloads/binaries/1.35.0-x86_64-linux-musl/busybox
chmod 755 busybox

CONTAINER_ID=$(docker ps -q -f "name=otel-demo-otel-collector-1")
docker cp busybox $CONTAINER_ID:/busybox

docker exec -it $CONTAINER_ID /busybox ash
# /busybox ls
```

## how to run demo app
``` bash
# to test trace span
./otel-client.py
./otel-client.py --grpc

# to test metrics
./otel-client.py --grpc --metrics

# to test context-propagation
./otel-client.py -c
```
