#!/bin/bash

set -e

# https://cloud.google.com/sql/docs/mysql/configure-private-services-access#configure-access
# create ip range for cloudsql
gcloud compute addresses create $GCP_CLOUDSQL_IPRANGE_NAME \
    --global \
    --purpose=VPC_PEERING \
    --prefix-length=20 \
    --network=projects/$GCP_PROJECT_ID/global/networks/$GCP_VPC_NAME

# connect cloudsql ip range to vpc
gcloud services vpc-peerings connect \
    --service=servicenetworking.googleapis.com \
    --ranges=$GCP_CLOUDSQL_IPRANGE_NAME \
    --network=$GCP_VPC_NAME \
    --project=$GCP_PROJECT_ID
    
# cloudsql instance
gcloud sql instances create $GCP_CLOUDSQL_INSTANCE_NAME \
    --database-version POSTGRES_15 \
    --tier db-f1-micro \
    --no-assign-ip \
    --network projects/$GCP_PROJECT_ID/global/networks/$GCP_VPC_NAME \
    --region $GCP_REGION

# database
gcloud sql databases create $GCP_CLOUDSQL_DB_NAME \
    --instance $GCP_CLOUDSQL_INSTANCE_NAME

# database user
gcloud sql users create $GCP_CLOUDSQL_USER \
    --instance $GCP_CLOUDSQL_INSTANCE_NAME \
    --password $GCP_CLOUDSQL_PASSWORD
 
#https://codelabs.developers.google.com/connecting-to-private-cloudsql-from-cloud-run#5
 
# add allow Serverless VPC connector service to connect to cloudsql
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
    --member="serviceAccount:$GCP_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
    --role="roles/cloudsql.client"

# create serverless vpc connector
gcloud compute networks vpc-access connectors create $GCP_SERVERLESS_VPC_ACCESS_CONNECTOR \
    --region=$GCP_REGION \
    --range=10.8.0.0/28 \
    --network=$GCP_VPC_NAME