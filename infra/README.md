# infra/

| Path | What |
|---|---|
| `TARGET_DESIGN.md` | Why the infrastructure looks like this (costs, decisions) |
| `terraform/shared` | Shared VPC attachments, prod Cloud SQL peering range, `hl-images` Artifact Registry repo |
| `terraform/modules/hl-env` | One environment: SAs, Cloud SQL, secret, bucket, queue, Cloud Run web/worker/jobs, deploy trigger |
| `terraform/modules/hl-lb` | Prod load balancer, Cloud CDN, Certificate Manager cert |
| `terraform/envs/{stage,prod}` | Environment roots |
| `cloudbuild/deploy.yaml` | Build → migrate → deploy. `staging` → stage, `main` → prod |

Conventions: resources are named `hl-<env>-<thing>`. There are no service account keys anywhere. Cloud Build owns container images and Terraform owns everything else. Secrets and DB passwords never go through Terraform, so they stay out of state.

## One-time bootstrap
```bash
# State bucket
gcloud storage buckets create gs://hiredlabs-tf-state --project=hl-main-prod \
  --location=us-west1 --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets update gs://hiredlabs-tf-state --versioning

# Cloud Build GitHub App: install it on HiredLabs-inc/hl_main and connect the repo
# in BOTH hl-main-stage and hl-main-prod (Console → Cloud Build → Triggers → Connect repository, 1st gen).
```

## Stand up an environment (stage first, then prod)
```bash
cd infra/terraform/shared && terraform init && terraform apply
cd ../envs/stage          && terraform init && terraform apply
```
The shared root's Org Policy resources bill quota to `hl-main-stage` (provider alias `google.quota`), because user ADC has no quota project.

Then, using the values from `terraform output`:
1. **DB user** (password stays out of state). The instance is created running:
   `gcloud sql users create hiredlabs --instance=hl-stage-sql --password='<generated>' --project=hl-main-stage`
2. **App secret:** write a `.env` file with the keys below, then run
   `gcloud secrets versions add hl-stage-app-env --data-file=.env --project=hl-main-stage` and delete the file.
   ```
   DJANGO_SECRET_KEY=            # new random value per environment
   VA_API_KEY=
   EMAIL_HOST_USER=
   EMAIL_HOST_PASSWORD=
   GCP_REGION=us-west1
   GCP_TASK_QUEUE=hl-stage-tasks
   GCP_SERVICE_ACCOUNT=<output app_service_account>
   GCP_CLOUDSQL_DB_NAME=hiredlabs
   GCP_CLOUDSQL_USER=hiredlabs
   GCP_CLOUDSQL_PASSWORD=<from step 1>
   GCP_CLOUDSQL_PRIVATE_IP=<output sql_private_ip>
   GS_BUCKET_NAME=<output media_bucket>
   CLOUDRUN_SERVICE_URL=<output web_url>
   CLOUDRUN_WORKER_URL=<output worker_url>   # the deterministic *-<project number>.<region>.run.app hosts are added automatically
   TURNSTILE_SITE_KEY=<from Cloudflare Turnstile>
   TURNSTILE_SECRET_KEY=<from Cloudflare Turnstile>
   ALLOWED_HOSTS=                # prod: hiredlabs.org,www.hiredlabs.org ; stage: leave empty
   ```
3. **First deploy:** push to `staging` (stage) or `main` (prod). The trigger reads `infra/cloudbuild/deploy.yaml` from that branch on GitHub, so it has to be pushed there first. After that, you can re-run by hand:
   `gcloud builds triggers run hl-stage-deploy --branch=staging --project=hl-main-stage`
4. **Seed stage data:**
   `gcloud run jobs execute hl-stage-manage --region=us-west1 --project=hl-main-stage --args=manage.py,loaddata,concentrations,degrees,titles,skills,states,countries_hdi,step_seed`

### Promoting to stage
Pushes to `develop` don't deploy. To deploy what's on `develop` to stage, fast-forward `staging` to it:
`git push origin develop:staging`

### Stage database on demand
The stage database is created running and is stopped every night at 02:00 PT. Deploys to stage start it automatically. To start it by hand:
`gcloud sql instances patch hl-stage-sql --activation-policy=ALWAYS --project=hl-main-stage` (use `NEVER` to stop it).

## Prod cut-over (TARGET_DESIGN.md §7, steps 3–6)
The old stack stays untouched throughout. Rollback is pointing DNS back to `34.95.124.115`.
1. Apply `envs/prod`. Add the `dns_authorization_records` CNAMEs in Namecheap and wait for
   `gcloud certificate-manager certificates describe hl-prod-cert --project=hl-main-prod` to show ACTIVE.
2. Do steps 1–3 above for prod (`ALLOWED_HOSTS=hiredlabs.org,www.hiredlabs.org`). Restore last night's dump to test:
   `gcloud sql import sql hl-prod-sql gs://hl-main-dev-fallback-20261013/sql/hired-labs-dev.sql.gz --database=hiredlabs --user=hiredlabs`.
   First grant the instance's service account `roles/storage.objectViewer` on the fallback bucket.
   Then smoke-test with `curl -H 'Host: hiredlabs.org' https://<lb_ip_address> -k`.
3. One day before: set the Namecheap TTL on `@` and `www` to 5 minutes.
4. **Downtime window:**
   ```bash
   gcloud tasks queues pause hl-main-dev-queue-001 --location=us-west1 --project=hl-main-dev
   gcloud tasks queues pause task-queue-dev-001     --location=us-west1 --project=hl-main-dev
   # stop writes: point the old LB's backend at a maintenance page, or scale run-service-dev-001 down
   gcloud sql export sql sql-dev-001 gs://hl-main-dev-fallback-20261013/sql/cutover-hired-labs-dev.sql.gz --database=hired-labs-dev --project=hl-main-dev
   # recreate the empty DB on the new instance, then import:
   gcloud sql databases delete hiredlabs --instance=hl-prod-sql --project=hl-main-prod
   gcloud sql databases create hiredlabs --instance=hl-prod-sql --project=hl-main-prod
   gcloud sql import sql hl-prod-sql gs://hl-main-dev-fallback-20261013/sql/cutover-hired-labs-dev.sql.gz --database=hiredlabs --user=hiredlabs --project=hl-main-prod
   gcloud storage rsync -r gs://hl-main-dev-media gs://hiredlabs-prod-media
   gcloud run jobs execute hl-prod-migrate --region=us-west1 --project=hl-main-prod --wait
   ```
   Change the Namecheap A records for `@` and `www` to `lb_ip_address`, then smoke-test logins, resume upload/view (signed URLs) and a background task.
5. Watch for 14 days, then decommission (TARGET_DESIGN.md step 7).

## Disaster recovery to us-east1
Cloud SQL backups are stored multi-region (US), so prod can be rebuilt on the east coast:
1. `gcloud sql backups list --instance=hl-prod-sql --project=hl-main-prod`, then restore the latest one into a new instance in `us-east1` on `vpc-prod-shared`. Alternatively, import the latest export.
2. Deploy `hl-prod-web` and `hl-prod-worker` in `us-east1` with Direct VPC egress on `subnet-prod-2`, using the current `:prod` image. Update the secret's `GCP_CLOUDSQL_PRIVATE_IP`.
3. Add `"us-east1" = "hl-prod-web"` to `module.lb.backends` in `envs/prod` and apply.

Test this once a year with a throwaway instance; it costs a few dollars for the test.
