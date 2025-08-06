#!/bin/bash
set -xe
echo "-- Building image..."
docker build -t flask-debugger-demo -f Dockerfile .
