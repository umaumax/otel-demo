# otel-demo

## how to run
``` bash
chmod 0777 ./data/
docker compose up
```

`./data/dump.json` includes trace and metrics data

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
