#!/bin/bash
set -e

source "$(dirname "$0")/../deploy/push_image.sh"

gcloud run jobs create migrate \
  --region $GCP_REGION \
  --image ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${GCP_CLOUDRUN_NAME}-repo/${GCP_CLOUDRUN_NAME}-image \
  --service-account $GCP_SERVICE_ACCOUNT \
  --vpc-connector $GCP_SERVERLESS_VPC_ACCESS_CONNECTOR \
  --set-env-vars "GCP_SECRETS_NAME=$GCP_SECRETS_NAME,GCP_PROJECT_ID=$GCP_PROJECT_ID,DJANGO_SETTINGS_MODULE=hl_main.settings.prod" \
  --command=python \
  --args=manage.py,migrate

# gcloud run jobs create collectstatic \
#   --region $GCP_REGION \
#   --image ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${GCP_CLOUDRUN_NAME}-repo/${GCP_CLOUDRUN_NAME}-image \
#   --service-account $GCP_SERVICE_ACCOUNT \
#   --vpc-connector $GCP_SERVERLESS_VPC_ACCESS_CONNECTOR \
#   --set-env-vars "GCP_SECRETS_NAME=$GCP_SECRETS_NAME,GCP_PROJECT_ID=$GCP_PROJECT_ID,DJANGO_SETTINGS_MODULE=hl_main.settings.prod" \
#   --command=python \
#   --args=manage.py,collecstatic,--no-input,--clear

  # update jobs