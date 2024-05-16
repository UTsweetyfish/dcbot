#!/bin/sh

set -e

/app/apt-update.sh &

exec "$@"