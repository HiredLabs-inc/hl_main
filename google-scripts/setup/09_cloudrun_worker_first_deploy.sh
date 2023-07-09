#!/bin/bash

set -e

gcloud run deploy $GCP_CLOUDRUN_WORKER_NAME \
    --platform managed \
    --region $GCP_REGION \
    --image ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${GCP_CLOUDRUN_NAME}-repo/${GCP_CLOUDRUN_NAME}-image \
    --set-cloudsql-instances $GCP_PROJECT_ID:$GCP_REGION:$GCP_CLOUDSQL_INSTANCE_NAME \
    --set-env-vars "DJANGO_ROLE=worker,GCP_SECRETS_NAME=$GCP_SECRETS_NAME,GCP_PROJECT_ID=$GCP_PROJECT_ID" \
    --no-allow-unauthenticated \
    --service-account $GCP_SERVICE_ACCOUNT  \
    --vpc-connector $GCP_SERVERLESS_VPC_ACCESS_CONNECTOR 

gcloud org-policies delete iam.allowedPolicyMemberDomains --project=$GCP_PROJECT_ID