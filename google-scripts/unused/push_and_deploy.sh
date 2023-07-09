#!/bin/bash

set -e

# For some reason running migrations and collectstatic in cloud build
# is incredibly slow so instead for collectstatic and migrate we
# spin up docker-compose that has cloudsqlproxy and gcloud cli
# and we run the commands from there
# https://github.com/GoogleCloudPlatform/python-docs-samples/issues/5174

# push image
docker-compose -f docker-compose.prod.yml run --rm gcloud sh ./scripts/deploy/push_image.sh

# collectstatic
docker-compose -f docker-compose.prod.yml run --rm \
    django python manage.py collectstatic --noinput --verbosity=2
# migrate
docker-compose -f docker-compose.prod.yml run --rm \
    django python manage.py migrate --noinput

# deploy cloud run instances
docker-compose -f docker-compose.prod.yml run --rm gcloud ./scripts/deploy/cloudrun_deploy.sh