#!/bin/bash
set -e

gcloud secrets versions add ${GCP_SECRETS_NAME} --data-file .env