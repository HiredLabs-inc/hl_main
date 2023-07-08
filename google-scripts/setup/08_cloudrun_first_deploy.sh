#!/bin/bash
# Run this when first creating the Cloud Run service
set -e

gcloud org-policies describe \
  constraints/iam.allowedPolicyMemberDomains \
 --effective \
  --project=$GCP_PROJECT_ID

gcloud org-policies set-policy ./google-scripts/policies/turn_off_drs.yaml 

gcloud run deploy $GCP_CLOUDRUN_NAME \
    --platform managed \
    --region $GCP_REGION \
    --image ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${GCP_CLOUDRUN_NAME}-repo/${GCP_CLOUDRUN_NAME}-image \
    --allow-unauthenticated \
    --service-account $GCP_SERVICE_ACCOUNT \
    --set-env-vars "GCP_SECRETS_NAME=$GCP_SECRETS_NAME,GCP_PROJECT_ID=$GCP_PROJECT_ID" \
    --vpc-connector $GCP_SERVERLESS_VPC_ACCESS_CONNECTOR 

