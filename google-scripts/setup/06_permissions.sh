#!/bin/bash
set -e

# Grant access to secrets for the cloud build service account
gcloud secrets add-iam-policy-binding $GCP_SECRETS_NAME \
    --member serviceAccount:$GCP_PROJECT_NUMBER@cloudbuild.gserviceaccount.com \
    --role roles/secretmanager.secretAccessor

# Grant access to queue tasks service account
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
    --member serviceAccount:$GCP_SERVICE_ACCOUNT \
    --role roles/cloudtasks.enqueuer

# Grant access to invoke cloud run
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
    --member serviceAccount:$GCP_SERVICE_ACCOUNT \
    --role roles/run.invoker

gcloud secrets add-iam-policy-binding $GCP_SECRETS_NAME \
    --member serviceAccount:$GCP_SERVICE_ACCOUNT \
    --role roles/secretmanager.secretAccessor

# # Grant cloud sql to cloud build
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
    --member serviceAccount:$GCP_SERVICE_ACCOUNT \
    --role roles/cloudsql.client

# TODO: review
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
    --member serviceAccount:$GCP_PROJECT_NUMBER@cloudbuild.gserviceaccount.com \
    --role roles/cloudsql.client

# let the service account act as itself? required apparently for queueing tasks
# via the python api
gcloud iam service-accounts add-iam-policy-binding $GCP_SERVICE_ACCOUNT \
    --member=serviceAccount:$GCP_SERVICE_ACCOUNT --role=roles/iam.serviceAccountUser

    
# if google storages or collect static doesn't work
gsutil iam ch \
    serviceAccount:$GCP_SERVICE_ACCOUNT:roles/storage.objectAdmin \
    gs://$GCP_PROJECT_ID-$GCP_BUCKET_SUFFIX

# firestore
# gcloud projects add-iam-policy-binding $GCP_PROJECT_ID --member=serviceAccount:$GCP_SERVICE_ACCOUNT \
#     --role=roles/datastore.user

# gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
#     --member="serviceAccount:$GCP_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
#     --role="roles/datastore.user"
