# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Use an official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.8-slim


ENV APP_HOME /app
WORKDIR $APP_HOME

# Removes output stream buffering, allowing for more efficient logging
ENV PYTHONUNBUFFERED 1


RUN apt-get update && \
    apt install -y postgresql-client && \
    # install psycopg3 build dependencies
    apt install  -y build-essential build-essential gcc libc-dev libpq-dev musl-dev 
# install django requirements

COPY ./requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# remove temporary build dependencies
RUN apt-get remove -y build-essential libffi-dev gcc libc-dev libpq-dev musl-dev
# Install dependencies

# Copy local code to the container image.
COPY . .


# Run the web service on container startup. Here we use the gunicorn
# webserver, with one worker process and 8 threads.
# For environments with multiple CPU cores, increase the number of workers
# to be equal to the cores available.
# Timeout is set to 0 to disable the timeouts of the workers to allow Cloud Run to handle instance scaling.
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 0 hl_main.wsgi:application