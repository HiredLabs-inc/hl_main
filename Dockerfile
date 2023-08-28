
# build frontend using node image
FROM node as frontend_builder

WORKDIR /app/frontend

COPY ./frontend/package.json ./package.json

RUN npm install

COPY . /app

RUN npm run build

FROM ubuntu:20.04
# Environment variable declaration for Google Cloud Build.
# see cloudbuild.yaml for usage in this project
# Reference to this solution:
# https://stackoverflow.com/questions/39597925/how-do-i-set-environment-variables-during-the-build-in-docker

ARG GCP_PROJECT_ID=hl-main-dev
# ENV GCP_PROJECT_ID=$GCP_PROJECT_ID

ARG GCP_SECRETS_NAME=squirrel-dev-002
# ENV GCP_SECRETS_NAME=$GCP_SECRETS_NAME

ENV APP_HOME /app
WORKDIR $APP_HOME

# Removes output stream buffering, allowing for more efficient logging
ENV PYTHONUNBUFFERED 1
RUN apt-get update
RUN apt install -y software-properties-common
RUN add-apt-repository --yes ppa:deadsnakes/ppa
RUN apt-get update && apt-get install -y python3.8 python3-pip
#python3-dev libcairo2-dev
# update-alternatives --install /usr/bin/python python /usr/bin/python3.8 1

# alias python to python3
RUN ln -s /usr/bin/python3 /usr/bin/python

COPY ./requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium --with-deps

# Copy local code to the container image.
COPY . .
COPY --from=frontend_builder /app/frontend/build ./frontend/build
# https://github.com/canonical/base-2204-python38/blob/main/Dockerfile

RUN python -m nltk.downloader all -d /usr/local/nltk_data

# arg DJANGO_SETTINGS_MODULE needed to run collectstatic in docker build step
ARG DJANGO_SETTINGS_MODULE

#=hl_main.settings.prod

COPY ./creds ./creds
ARG GOOGLE_APPLICATION_CREDENTIALS=./creds/application_default_credentials.json

RUN python manage.py collectstatic --no-input

# Run the web service on container startup. Here we use the gunicorn
# webserver, with one worker process and 8 threads.
# For environments with multiple CPU cores, increase the number of workers
# to be equal to the cores available.
# Timeout is set to 0 to disable the timeouts of the workers to allow Cloud Run to handle instance scaling.


CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 0 hl_main.wsgi:application
