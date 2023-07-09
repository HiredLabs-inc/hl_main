#!/bin/bash

set -e

gcloud gcloud auth login

gcloud config set project $GCP_PROJECT_ID


gcloud services enable \
  run.googleapis.com \
  sql-component.googleapis.com \
  sqladmin.googleapis.com \
  compute.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  cloudtasks.googleapis.com \
  vpcaccess.googleapis.com \
  servicenetworking.googleapis.com \
  firestore.googleapis.com \
  orgpolicy.googleapis.com \
  accesscontextmanager.googleapis.com