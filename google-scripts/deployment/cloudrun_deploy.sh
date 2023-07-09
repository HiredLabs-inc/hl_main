#!/bin/bash

set -e

# Pause task queue
gcloud tasks queues pause $GCP_TASK_QUEUE --location=$GCP_REGION

gcloud run jobs execute migrate --region $GCP_REGION --wait
gcloud run jobs execute collectstatic --region $GCP_REGION --wait

# Deploy Built Image to Cloud Run
gcloud run deploy $GCP_CLOUDRUN_NAME \
    --region $GCP_REGION \
    --image ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${GCP_CLOUDRUN_NAME}-repo/${GCP_CLOUDRUN_NAME}-image \
    --service-account $GCP_SERVICE_ACCOUNT

gcloud run deploy $GCP_CLOUDRUN_WORKER_NAME \
    --region $GCP_REGION \
    --image ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${GCP_CLOUDRUN_NAME}-repo/${GCP_CLOUDRUN_NAME}-image \
    --service-account $GCP_SERVICE_ACCOUNT

# Restart task
gcloud tasks queues resume $GCP_TASK_QUEUE --location=$GCP_REGION
