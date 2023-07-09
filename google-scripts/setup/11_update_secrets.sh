#!/bin/bash

# set the in .env file
# CLOUDRUN_SERVICE_URL
# CLOUDRUN_WORKER_URL

set -e
source "$(dirname "$0")/../deploy/secrets_update.sh"