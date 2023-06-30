#!/bin/bash
set -e
gcloud iam service-accounts create $GCP_SERVICE_ACCOUNT_NAME


# set GCP_SERVICE_ACCOUNT in .env file to the email returned here
echo "$(gcloud iam service-accounts list \
    --filter $GCP_SERVICE_ACCOUNT --format 'value(email)')"

export GCP_SERVICE_ACCOUNT="$(gcloud iam service-accounts list \
    --filter $GCP_SERVICE_ACCOUNT --format 'value(email)')"

#TODO: get service account keys?