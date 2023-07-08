import os

# CURRENTLY UNUSED

# Adds env variables listed in subs_list to --substitutions flag
# on gcloud builds submit command

# result is "gcloud builds submit --substitutions _GCP_REGION=us-central1,...etc"


def read_env_file(filename=".env"):
    vars = {}
    with open(filename) as f:
        for line in f:
            if line.startswith("#"):
                continue
            if not line.strip() == "":
                key, value = line.strip().split("=")
                vars[key] = value
    return vars


substitutions_list = [
    "GCP_REGION",
    "GCP_CLOUDRUN_NAME",
    "GCP_CLOUDSQL_INSTANCE_NAME",
    "GCP_SECRETS_NAME",
]
gcloud_vars = read_env_file()

#
substitutions = ",".join(
    [f"_{k}={v}" for k, v in gcloud_vars.items() if k in substitutions_list]
)

exit_status = os.system(
    f"gcloud builds submit --config scripts/deploy/migrations.yaml --substitutions {substitutions} "
)
if exit_status != 0:
    exit(1)
