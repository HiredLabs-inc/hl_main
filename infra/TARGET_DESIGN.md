# hl_main GCP Target Design

Status: **approved direction**, 2026-10-13 (decisions recorded at the end). Based on the live export in `../terraform/live-export-20261013/`.
Fallback point: `../terraform/live-export-20261013/FALLBACK.md`.

## Constraints that drive the design
1. **Budget comes first.** Cloud SQL is the largest cost, so no change may raise the monthly bill without a decision.
2. hl-main-dev currently serves production. Changes must not risk it until a verified replacement exists.
3. Shared VPC (`vpc-host-prod-*`, `vpc-host-staging-*`) is the target network model.
4. Short downtime is acceptable. Resources can be recreated.
5. Asia is removed. US coverage includes the east coast (see §6, decision needed).

## 1. What the live data says (30-day window)
| Signal | Value | Implication |
|---|---|---|
| Prod requests | ~15k per 30 days (US), ~13k (Asia) | Very low traffic. Shared-core DB and scale-to-zero are realistic |
| Stage requests | 0 | Stage can be off almost all the time |
| DB disk used / provisioned | **155 MB / 100 GB SSD** | About $15/mo spent on empty disk. Cloud SQL disks can't shrink, so a new instance fixes this |
| DB CPU max | 60% (f1-micro) | f1-micro is adequate for now |
| Prod web memory p99 | 9% of 4 GiB | Right-size to 1 GiB |
| Asia p95 latency | **17 s** | A region far from the DB is slower, not faster |
| Real prod database | **`hired-labs-dev`** (7,905 users). `hired-labs-prod` is empty | Rename during migration |

## 2. Database: separate instances that cost less than today
The current single instance is about **$25–27/mo**: f1-micro $7.67 + 100 GB SSD $17 + backups. These are list-price estimates; see §8.

| | Prod instance | Stage instance |
|---|---|---|
| Project / network | hl-main-prod, private IP on `vpc-prod-shared` | hl-main-stage, private IP on `vpc-staging-shared` |
| Tier / disk | db-f1-micro, **10 GB SSD**, auto-resize | db-f1-micro, **10 GB HDD** |
| Availability | Zonal (HA would double the cost) | Zonal |
| Backups | Daily, 7 retained, PITR, deletion protection | 1 retained, no PITR |
| Running | Always | **Stopped by default** (`activation-policy=NEVER`). Start on demand; nightly Cloud Scheduler stop as a safety net |
| Public IP | None (admin through Cloud SQL Auth Proxy + IAM) | None |
| Est. cost | ~$10/mo | ~$1/mo stopped, ~$2–3 at typical use, $8.60 if left on |

**Total: about $11–13/mo, down from about $26.** We get real isolation (separate blast radius, maintenance and upgrades, IAM boundary) and still save money, because the oversized disk costs more than a second, mostly-stopped instance.

- **Dev** uses the local docker-compose Postgres, as it already does. There is no cloud dev database.
- **Stage data** is seeded from fixtures (the existing `loaddata` job) or a scrubbed prod dump. It never uses live PII.
- **Fallback if even +$1 is unacceptable:** keep one instance (the new right-sized one in hl-main-prod) with per-env databases and **per-env DB users**, so the stage user can't connect to the prod database. Cost is lower than today, but stage still shares the prod blast radius and connects across projects into the prod network. I don't recommend it.
- **Upgrade path when traffic grows:** f1-micro → g1-small (~$26) → dedicated core. HA only when downtime starts costing more than about $10/mo.

## 3. Other cost changes
| Change | Est. monthly effect |
|---|---|
| Replace 2 Serverless VPC Access connectors (each runs ≥2 e2-micro VMs) with **Direct VPC egress** (free) | **−$25–30** |
| Prod web min-instance 4 GiB → 1 GiB (keep min 1, because the Playwright image cold-starts slowly) | **−$15–20** |
| Remove Asia: service with min 1, connector, AR repo, NEG | **−$10–15** |
| Remove the duplicate stage stack in hl-main-dev. Stage in hl-main-stage scales to zero | small |
| Artifact Registry cleanup policy (keep last 10 + tagged), using `hl_build_files/utils/artifact-registry-cleanup-policy.json` | small, ongoing |
| Remove the public IP on the SQL instance | small |
| Global external LB (~$18/mo) | unchanged: needed for the custom domain, CDN and multi-region |
| Cloud Build triggers (2,500 free build-minutes per month) | ~$0 |
| Terraform state bucket | cents |

Rough net change: **about −$65 to −$85/mo** before east-coast work. Confirm against real billing (§8).

## 4. Target layout
```
Org hiredlabs.org
├── Common/      vpc-host-prod (vpc-prod-shared: us-west1, us-east1)
│                vpc-host-staging (vpc-staging-shared: us-west1, us-east1)   ← asia subnet removed
│                logging, monitoring-*
├── Production/  hl-main-prod   ← all prod workloads (service project of vpc-host-prod)
├── Staging/     hl-main-stage  ← all stage workloads (service project of vpc-host-staging)
└── Development/ hl-main-dev    ← retired after cut-over and the fallback window; kept empty or deleted
```

Per environment (`<env>` = `prod` | `stage`), identical shape and parameterised by Terraform:
| Resource | Name | Notes |
|---|---|---|
| Cloud Run web | `hl-<env>-web` | us-west1. Direct VPC egress (private ranges). Ingress internal + LB (prod). Prod min 1 / 1 GiB; stage min 0 |
| Cloud Run worker | `hl-<env>-worker` | Same image, `DJANGO_ROLE=worker`. Ingress internal. Min 0 |
| Cloud Run jobs | `hl-<env>-migrate` (migrate + createcachetable, runs on every deploy), `hl-<env>-manage` (any management command, args given at execution) | Replace the 17 ad-hoc jobs. collectstatic now runs at image build time |
| Cloud SQL | `hl-<env>-sql`, db `hiredlabs` | See §2 |
| Cloud Tasks | `hl-<env>-tasks` | us-west1 |
| Secret | `hl-<env>-app-env` | Same `.env`-blob pattern the settings already read |
| Bucket | `hiredlabs-<env>-media` (bucket names are global) | us-west1, uniform access |
| Service accounts | `hl-<env>-app` (web, worker and jobs run the same code), `hl-<env>-deploy` (Cloud Build) | **No keys.** Least privilege. The default compute SA isn't used. Signed URLs use IAM signBlob (`hl_main/gcs.py`) |
| Artifact Registry | `hl-images` (one repo, in hl-main-prod) | Each branch trigger builds its own image, tagged `:<sha>` and `:<env>`. A merge commit on `main` has no stage build to promote. Cleanup keeps the last 10 images plus the env tags |

Prod only: global external ALB `hl-prod-lb` with a Certificate Manager cert for hiredlabs.org and www. The cert is pre-provisioned through DNS authorization, so cut-over doesn't wait on cert issuance. Cloud CDN covers `/static/` and media.

## 5. Security and hygiene (code changes in this repo)
- **Dockerfile:** drop `COPY ./creds` and `GOOGLE_APPLICATION_CREDENTIALS`. Cloud Run uses the metadata server; local dev uses `gcloud auth application-default login`. Then **delete all 7 user-managed SA keys**.
- **Settings:** merge `stage.py` and `prod.py` into one env-driven module that connects to the DB over private IP.
- **Superuser password:** rotate it (it's in git history), and remove the hardcoded value from `google-scripts/job-createsuperuser.yaml`.
- **Public access:** use Cloud Run `--no-invoker-iam-check` instead of an `allUsers` binding. This lets the `iam.allowedPolicyMemberDomains` org policy stay **on** permanently, so no more toggling it in setup scripts.
- **Firewall:** delete `allow-8080-all` (0.0.0.0/0) and the dead `hl-main-ssl-cert`.
- **Stale definitions:** archive `google-scripts/`, `cloudbuild.yaml` and `../hl_build_files/*/yaml`. They're superseded by `infra/`.

## 6. East coast (decision needed)
The app is DB-bound: Django runs many queries per page. Every request served in us-east1 would make each query a ~65 ms round trip to us-west1, which adds 0.5–2 s per page. Asia's 17 s p95 is the extreme version of this. Options, cheapest first:

| Option | What it gives east users | Est. cost |
|---|---|---|
| **A. CDN + DR (recommended)** | Cloud CDN edge caching for static and media, which is the main latency win. Plus a tested **disaster-recovery path in us-east1**: Terraform is region-parameterised, us-east1 subnets already exist, and Cloud SQL backups are stored multi-region, so prod can be restored to us-east1 in under an hour | ~$0–2 |
| B. Warm standby web tier in us-east1 | Cloud Run service (min 0) in the LB as a second backend. Only useful as failover; for most east users it is *slower* than west | ~$0 idle |
| C. Active east region | Cross-region read replica + Django DB router + east Cloud Run | +$10–20 and real complexity |

## 7. Migration sequence
| # | Step | Prod impact | Rollback |
|---|---|---|---|
| 0 | Fallback point | ✅ done | — |
| 1 | Repo hygiene (§5), `infra/` Terraform skeleton, GCS state bucket, rotate superuser password | none | git revert |
| 2 | Stand up **stage** in hl-main-stage with Terraform (new SQL, stopped by default). Cloud Build trigger on `develop`. Prove the full deploy → migrate → smoke-test loop | none | `terraform destroy` stage |
| 3 | Attach hl-main-prod to vpc-host-prod and stand up **prod** with Terraform: SQL, services, LB on a new IP, cert pre-provisioned through DNS auth. Restore last night's dump and test on the run.app URL | none | destroy |
| 4 | Lower the DNS TTL to 300 s (1 day ahead) | none | — |
| 5 | **Cut-over, ~15–30 min:** pause old task queue → maintenance page / scale old web → final `hired-labs-dev` export → import into `hl-prod-sql` as `hiredlabs` → migrate job → smoke test → switch DNS to the new LB IP | **downtime** | Point DNS back to the old LB (old stack untouched) |
| 6 | Watch for 7–14 days. Old stack scaled to minimum but intact | none | DNS back + re-sync data |
| 7 | Decommission: Asia (service, NEG, repo, connector, subnet), the hl-main-dev stacks, both VPC connectors, the old LB, and finally `sql-dev-001` (take a final export first) | none | restore from dumps |
| 8 | East-coast option from §6 | none | — |

## 8. Before committing to the numbers
There is no billing export, so every figure above is a list-price estimate. To check them, open **Billing → Reports**, group by **SKU** for the last 3 months, and share the top items. Or enable the BigQuery billing export, which costs pennies at this scale, so we can see trends.

## Decisions (2026-10-13)
1. **East coast: option A.** Cloud CDN plus a tested us-east1 DR path.
2. **DNS: Namecheap.** It stays there. Cut-over means changing the A record for `@` and `www` to the new LB IP. The cert is pre-provisioned with a Certificate Manager DNS-authorization CNAME added in Namecheap. Lower the TTL in Namecheap a day ahead.
3. **CI/CD: Cloud Build GitHub triggers on `HiredLabs-inc/hl_main`.** `develop` → build + deploy to **stage**. `main` → deploy the **same image digest** to **prod**.
4. **Fallback window: 14 days** after cut-over. Then the Development project `hl-main-dev` is deleted (step 7). It is no longer a target environment, but it hosts prod until cut-over.
5. **Superuser:** the leaked password belongs to `superadmin_1`, which exists only in the stage DB. Prod uses a different account, `superadmin`. No prod rotation needed. Remove the plaintext from the repo; stage gets a fresh DB.

## Implementation status
Step 1 is on branch `infra/gcp-restructure`: keyless image (`Dockerfile`, `hl_main/gcs.py`), unified `hl_main/settings/cloud.py`, Terraform in `infra/terraform`, pipeline in `infra/cloudbuild/deploy.yaml`, and the runbook in `infra/README.md`. Nothing has been applied to GCP yet.
