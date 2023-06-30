#!/bin/bash

set -e

gcloud builds submit  \
-t ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${GCP_CLOUDRUN_NAME}-repo/${GCP_CLOUDRUN_NAME}-image 


