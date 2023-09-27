# This is just a separate Dockerfile just for running 
# vite build --watch in development

# The reason why it is separated is because the main Django
# Dockerfile uses a multi-stage build, that drops node
# and ends with only python installed so we cant run node commands

# In order to run npm run watch in development
# we need this dockerfile with node installed
# so docker-compose can do this:

# services:
#   frontend:
#       build:
#           context: .
#           dockerfile: ./frontend/Dockerfile
#       volumes:
#           - .:/app
#       command: npm run watch

# If the steps are exactly the same as the main Dockerfile's
# frontend_builder stage, then docker-compose build will reuse the cache

FROM node

WORKDIR /app/frontend

COPY ./frontend/package.json ./package.json

RUN npm install

COPY . /app

CMD [ "npm", "run", "build" ]
