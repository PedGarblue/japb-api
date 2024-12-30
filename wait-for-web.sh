#!/bin/bash
set -e

host="$1"
shift
cmd="$@"

echo "Waiting for web service at $host..."
until curl -s "$host" >/dev/null; do
  sleep 2
done

echo "Web service is up, starting Celery..."
exec $cmd