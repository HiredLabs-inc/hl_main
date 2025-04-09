# Hired Labs, Inc. 
## Main Website and Tools

This is the main website for Hired Labs, Inc. It serves as a platform for web applications and tools to help accomplish
our mission of ending veteran underemployment.

## 1. Installation

#### 1.1. Preliminary Setup
Create a .env.dev file containing the environment variables below in the hl_main/ subdirectory
```bash
# hl_main/.env.dev
DJANGO_SECRET_KEY=long-string-of-characters
GCP_PROJECT_ID=whatever-project-id-you-want
GOOGLE_APPLICATION_CREDENTIALS=gcloud/application_default_credentials.json
```

Create /hl_main/creds subdirectory
Create SSH key for local environment

#### 1.2. Install docker, python, gitbash
https://docs.docker.com/
https://www.python.org/downloads/
https://git-scm.com/downloads

#### 1.3. Setup gcloud
Create login for gcloud environment with IAM server credentials + billing account

```bash
docker compose build
docker compose run --rm gcloud bash
```
You should now be in the gcloud container
```bash

gcloud init
```
Follow the prompts to log in and set your default project region to us-west1-a

```bash
gcloud auth application-default login
```

#### 1.4. Run migrations
```bash
docker compose run --rm django python manage.py migrate
```

#### 1.5. Create a superuser
```bash
docker compose run --rm django python manage.py createsuperuser
```

#### 1.6. Load development seed data
```bash
docker compose run --rm django python manage.py loaddata dev_seed
```

## 2. Usage


#### 2.1. Start the development server
```bash
docker compose up
```
With the development server running, you'll be able to access the web apps by logging in with these credentials:

        username: admin
        password: admin

Your browser may warn you that this password is not secure. You can create another superuser with a more secure password,
if you wish. Simply run the command below and follow the prompts:

```bash
docker compose run --rm django python manage.py createsuperuser 
```

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss the change. Please see
CODE_OF_CONDUCT.md for details on our code of conduct.

[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](code_of_conduct.md)
## License
[GPL-3.0 license](https://www.gnu.org/licenses/gpl-3.0.en.html)_
