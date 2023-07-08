#!/bin/bash

set -e
gcloud compute networks create $GCP_VPC_NAME \
    --subnet-mode=auto \
    --bgp-routing-mode=regional \
    --mtu=1460

gsutil mb -l $GCP_REGION gs://$GCP_PROJECT_ID-$GCP_BUCKET_SUFFIX




  