#!/bin/bash

set -e

gcloud artifacts repositories create $GCP_CLOUDRUN_NAME-repo \
    --repository-format=docker \
    --location=$GCP_REGION \
    --description="$GCP_CLOUDRUN_NAME Cloud Run Repository"