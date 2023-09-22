# History Output from command line
## Unsorted
git fetch origin pull/39/head:bullet-point-generation
  568  git checkout bullet-point-generation
  569  clear
  570  atom .
  571  cp -t hl_main/ ../.env ../.env.dev
  572  cat ../docker-compose.yml
  573  vi hl_main/.env
  574  clear
  575  docker-compose build
  576  mv -t . hl_main/.env hl_main/.env.dev

 **MAKE a directory for ssl certs downloaded from Cloud SQL instance**

 mkdir certs
 mv -t certs ~/Downloads/*.pem && showme certs/
  641  docker-compose build
  642  docker-compose up

docker-compose build
docker-compose run --rm django python manage.py migrate
docker-compose run --rm django python manage.py loaddata dev_data

docker-compose up

xdg-open http://127.0.0.1:8000/

**CHECKPOINT: The site should be running on the local machine**

### Build an Image with Docker

`docker tag hl_main_frontend us-west1-docker.pkg.dev/hl-main-dev/hl-dev-repo/hl_main_frontend`

### Push the image to Artifact Registry
`docker push us-west1-docker.pkg.dev/hl-main-dev/hl-dev-repo/hl_main_frontend`

### Let the Service Account be Itself
Stop oppressing the service account! Let it identify as itself. Not clear why this is needed, but I
gcloud iam service-accounts add-iam-policy-binding $GCP_SERVICE_ACCOUNT --member serviceAccount:$GCP_SERVICE_ACCOUNT --role roles/iam.serviceAccountUser

# This Fails
## Using Google buildpacks to creat the image supposedly makes it easier to run migrations through run jobs
- this failed trying to load backzones, so Python version is suspected culprit
 instead of debugging, waived of and used cloudbuild.yaml (default) as --config property to `gcloud builds submit --region=us-west2`
# gcloud builds submit --pack image=us-west1-docker.pkg.dev/hl-main-dev/hl-dev-repo/hl_main_django

# THIS WORKS
# Everything below this line works (as of 08/30/2023)

# Connecting to cloud proxy
# supposedly makes it possible to use one sql instance for all things local
# migrate and other 'server admin' functions failed, so they were implemented through cloud run jobs
# Still works and may be useful

./cloud-sql-proxy --port 4242 --credentials-file /home/janton42/.config/gcloud/application_default_credentials.json hl-main-dev:us-west1:sql-dev-001 &

## Build with cloud build
- default is --config cloudbuild.yaml, which includes build from cache, push to Artifact Registry, and Deploy steps
- us-west2 is required if we want the build in the west at all

`gcloud builds submit --region=us-west2`

## Create a job
- jobs can be used for 'server admin' functions
- current job functions:
  1. migrate (migrate-database)
  2. createcachetable
  3. createsuperuser
  4. loaddata

### Command Line
`gcloud beta run jobs create JOB_NAME \
--image us-west1-docker.pkg.dev/hl-main-dev/hl-dev-repo/hl_main_django \
--region us-west1 \
--set-cloudsql-instances hl-main-dev:us-west1:sql-dev-001 \
--set-secrets APPLICATION_SETTINGS=squirrel-dev-002:latest \
--vpc-connector projects/vpc-host-staging-yk380-hm150/locations/us-west1/connectors/dev-connector-1`


## From Yaml
1. For new jobs, copy the template jobs.yaml file

2. Run this command to both create new jobs and update existing ones

`gcloud run jobs replace CONFIG_FILENAME.yaml`

### Run a job

`gcloud beta run jobs execute JOBNAME`


## Create a task queue
gcloud tasks queues create --location=us-west1 task-queue-dev-001

## Update Secrets
1. Add any necessary env variables to the .env file
2. Update secret in secrets manager

`gcloud secrets versions add ${GCP_SECRETS_NAME} --data-file .env`
