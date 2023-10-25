
# build frontend using node image
FROM node as frontend_builder

WORKDIR /app/frontend

COPY ./frontend/package.json ./package.json

RUN npm install

COPY . /app

RUN npm run build

FROM ubuntu:jammy
# Environment variable declaration for Google Cloud Build.
# see cloudbuild.yaml for usage in this project
# Reference to this solution:
# https://stackoverflow.com/questions/39597925/how-do-i-set-environment-variables-during-the-build-in-docker
ARG DEBIAN_FRONTEND=noninteractive
ARG TZ=America/Los_Angeles
ARG DOCKER_IMAGE_NAME_TEMPLATE="mcr.microsoft.com/playwright:v1.35.0-jammy"
ARG GCP_PROJECT_ID=hl-main-dev
# ENV GCP_PROJECT_ID=$GCP_PROJECT_ID

ARG GCP_SECRETS_NAME=squirrel-dev-002
# ENV GCP_SECRETS_NAME=$GCP_SECRETS_NAME

ARG GCP_PROJECT_ID=hl-main-dev
ARG GCP_SECRETS_NAME=squirrel-dev-002

ENV APP_HOME /app
WORKDIR $APP_HOME

# Removes output stream buffering, allowing for more efficient logging
ENV PYTHONUNBUFFERED 1
RUN apt-get -y update && apt-get -y upgrade && apt-get install -y software-properties-common && add-apt-repository --yes ppa:deadsnakes/ppa && apt-get update && apt-get install -y python3.8 python3-pip
#python3-dev libcairo2-dev
# update-alternatives --install /usr/bin/python python /usr/bin/python3.8 1

# alias python to python3
RUN ln -s /usr/bin/python3 /usr/bin/python

COPY ./requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# === INSTALL Node.js ===

RUN apt-get update && \
    # Install Node 18
    apt-get install -y curl wget gpg ca-certificates && \
    mkdir -p /etc/apt/keyrings && \
    curl -sL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_18.x nodistro main" >> /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y nodejs && \
    # Feature-parity with node.js base images.
    apt-get install -y --no-install-recommends git openssh-client && \
    npm install -g yarn && \
    # clean apt cache
    rm -rf /var/lib/apt/lists/* && \
    # Create the pwuser
    adduser pwuser

# === BAKE BROWSERS INTO IMAGE ===

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# 2. Bake in browsers & deps.
#    Browsers will be downloaded in `/ms-playwright`.
#    Note: make sure to set 777 to the registry so that any user can access
#    registry.
RUN mkdir /ms-playwright && \
    mkdir /ms-playwright-agent && \
    cd /ms-playwright-agent && npm init -y && \
    npm i playwright && \
    npm exec --no -- playwright-core mark-docker-image "${DOCKER_IMAGE_NAME_TEMPLATE}" && \
    npm exec --no -- playwright-core install --with-deps && rm -rf /var/lib/apt/lists/* && \
    rm -rf /ms-playwright-agent && \
    rm -rf ~/.npm/ && \
    chmod -R 777 /ms-playwright

RUN playwright install-deps
RUN playwright install

# Copy local code to the container image.
COPY . .
COPY --from=frontend_builder /app/frontend/build ./frontend/build

# https://github.com/canonical/base-2204-python38/blob/main/Dockerfile

RUN python -m nltk.downloader stopwords -d /usr/local/nltk_data

# arg DJANGO_SETTINGS_MODULE needed to run collectstatic in docker build step
ARG DJANGO_SETTINGS_MODULE

COPY ./creds ./creds
ARG GOOGLE_APPLICATION_CREDENTIALS=./creds/application_default_credentials.json
RUN python manage.py collectstatic --no-input


# Run the web service on container startup. Here we use the gunicorn
# webserver, with one worker process and 8 threads.
# For environments with multiple CPU cores, increase the number of workers
# to be equal to the cores available.
# Timeout is set to 0 to disable the timeouts of the workers to allow Cloud Run to handle instance scaling.


CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 0 hl_main.wsgi:application
