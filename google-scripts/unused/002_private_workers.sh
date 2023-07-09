
gcloud builds worker-pools create $GCP_PROJECT_ID-private-pool \
        --project=$GCP_PROJECT_ID \
        --region=$GCP_REGION \
        --worker-machine-type=e2-medium \
        --peered-network=projects/$GCP_PROJECT_ID/global/networks/$GCP_VPC_NAME \
        --no-public-egress
public ips

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
      --member=serviceAccount:$GCP_PROJECT_NUMBER@cloudbuild.gserviceaccount.com \
      --role=roles/cloudbuild.workerPoolUser
