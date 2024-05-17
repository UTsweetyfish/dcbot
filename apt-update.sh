#!/bin/sh

set -e

onexit(){
    echo exit
}

trap onexit EXIT


while true ; do
    # Update the package list

    echo "--------------------------------"
    echo "Running apt-get update on $(date -R)"

    if ! apt-get update; then
        echo "apt-get update failed. Retrying in 10 minutes..."
        echo "--------------------------------"
        sleep 10m
    else
        echo "apt-get update succeeded."
        echo "--------------------------------"
        date '+%s' > LAST-UPDATED
        sleep 1h
    fi
done
