<img width="1903" height="528" alt="Job-Tracker-Screenshot" src="https://github.com/user-attachments/assets/bd694eba-0d7b-469a-9b0c-dd3e80793ee0" />
# Job Tracker

A local-first job application tracker designed to run inside a Kubernetes cluster on WSL2.

The first version includes:

- FastAPI web app
- Server-rendered HTML with Jinja templates
- PostgreSQL database
- SQLAlchemy models
- Alembic migrations
- Dockerfile
- Helm chart
- Kubernetes Deployment, Service, Ingress, Secret, ConfigMap, StatefulSet, PVC, and backup CronJob

## Architecture

```text
Windows browser
    |
    v
http://jobtracker.local
    |
    v
Kubernetes Ingress / Traefik
    |
    v
FastAPI Deployment + Service
    |
    v
PostgreSQL Service
    |
    v
PostgreSQL StatefulSet + PersistentVolumeClaim
```

## Data model

Initial tables:

- `companies` — reusable company records, including website, LinkedIn page, address, city, and logo filename
- `contacts` — reusable people/contact records linked to companies
- `job_applications` — current state of each job opportunity, linked to one company and optionally one position category
- `position_categories` — managed category values such as Devops and IT
- `application_contacts` — links contacts to specific job applications
- `application_events` — timeline/history events for each opportunity

## Database choice

This project uses PostgreSQL by default.

- In Kubernetes, the app connects to the PostgreSQL Service created by the Helm chart.
- For direct development from WSL2, `.env.example` points to PostgreSQL on `localhost:5432`, which is useful when you port-forward the Kubernetes PostgreSQL Service.
- SQLite is intentionally not the default because the goal is to keep the app inside a Kubernetes-style ecosystem with a real database component.

## Run on k3s inside WSL2

### 1. Build and import the image into k3s

```bash
cd job-tracker
./scripts/build-and-import-k3s.sh
```

This builds:

```text
job-tracker-app:local
```

and imports it into k3s containerd.

### 2. Install with Helm

```bash
helm upgrade --install job-tracker ./helm/job-tracker \
  --namespace job-tracker \
  --create-namespace
```

### 3. Check pods

```bash
kubectl get all -n job-tracker
kubectl get pvc -n job-tracker
kubectl get ingress -n job-tracker
```

### 4. Access the app

For a quick test:

```bash
kubectl port-forward -n job-tracker svc/job-tracker-app 8000:80
```

Then open this from Windows:

```text
http://localhost:8000
```

## Optional: run the FastAPI process directly while still using Kubernetes PostgreSQL

This is useful for quicker code changes while keeping PostgreSQL as the database.

In one terminal:

```bash
kubectl port-forward -n job-tracker svc/job-tracker-postgres 5432:5432
```

In another terminal:

```bash
cd job-tracker
cp .env.example .env
./scripts/dev-local.sh
```

Open:

```text
http://localhost:8000
```

For the nicer local domain approach, add this to your Windows hosts file:

```text
127.0.0.1 jobtracker.local
```

Then open:

```text
http://jobtracker.local
```

Depending on how your k3s/Traefik is exposed from WSL2, you may still prefer `kubectl port-forward` initially.

## Useful Kubernetes commands

```bash
kubectl logs -n job-tracker deploy/job-tracker-app
kubectl describe pod -n job-tracker -l app.kubernetes.io/component=app
kubectl exec -it -n job-tracker statefulset/job-tracker-postgres -- psql -U jobtracker -d jobtracker
```

## Database migrations

In this initial local setup, the app container runs:

```bash
alembic upgrade head
```

before starting the web server. This is acceptable while the app has one replica.

A disabled Kubernetes migration Job template is also included. To enable it:

```bash
helm upgrade --install job-tracker ./helm/job-tracker \
  --namespace job-tracker \
  --create-namespace \
  --set migrationJob.enabled=true
```

For a production-style deployment, you would normally run migrations as a separate controlled Job and avoid running migrations automatically in every app pod.

## Backups

A PostgreSQL backup CronJob is enabled by default and runs daily according to the Helm value:

```yaml
backup:
  schedule: "0 7 * * *"
```

To trigger a backup manually:

```bash
kubectl create job -n job-tracker \
  --from=cronjob/job-tracker-backup \
  manual-backup-$(date +%s)
```

To inspect backup files:

```bash
kubectl get pods -n job-tracker -l app.kubernetes.io/component=backup
```

You can later add a restore script and export feature.

## Current features

- Add/edit/delete reusable companies with city/address fields
- View company, company contact, recruiter company, and recruiter contact detail pages
- Add/edit/delete reusable company contacts
- Add a job application linked to a company and category
- Link existing contacts to a job application
- View all applications in a summary table
- Filter and sort the summary tables, including by category
- Search company, role, location, source, and notes
- View application detail with company logo and linked contacts
- Edit application
- Delete application
- Add timeline/history events
- Track status changes as events
- Manage job application statuses and position categories from Maintenance

## Suggested next milestones

1. Add CSV export
2. Add dashboard statistics
3. Add Kanban board by status
4. Add file attachments for CV versions, job descriptions, or home assignments
5. Add reminder view for upcoming next-action dates
6. Add authentication only if you later expose it outside your machine

## Company and recruiter company logos

Logos are now uploaded from the Company and Recruiter Company add/edit forms.

The app stores only the generated logo filename in PostgreSQL. The uploaded image file is saved under:

```text
/app/data/logos
```

In Kubernetes, `/app/data` is backed by the `job-tracker-app-data` PVC, so uploaded logos survive pod restarts and image rebuilds.

For direct local development, `.env.example` uses:

```env
LOGO_DIR=data/logos
```

Supported file types are:

```text
.png, .jpg, .jpeg, .gif, .webp, .svg
```

Older image files in the project-level `logos/` folder can still be served as a fallback for existing records, but new logos should be uploaded through the web UI.

### Recruiter management

The app now separates company-side contacts from recruiter-side contacts:

- `/contacts` manages company contacts linked to target companies and selectable on position records.
- `/recruiter-companies` manages recruiting agencies/search firms separately from target companies.
- `/recruiter-contacts` manages recruiter contacts. `date_added` is automatic and `date_contact_made` is optional/manual.

Recruiter contacts are intentionally not linked to position detail pages yet.


### Application summary screens

The app includes Application Intake, Interview Pipeline, and Archive summary screens. Status values can be assigned to one of these screens from Maintenance → Job Application Statuses.

## LinkedIn company lookup service

The Company add/edit form can look up likely LinkedIn company pages using a separate internal FastAPI service:

```text
Job Tracker app  --->  linkedin-lookup Service  --->  Tavily API
```

The lookup service is deployed as its own Kubernetes Deployment and Service by the Helm chart. The main app calls it through the internal service URL stored in `LINKEDIN_LOOKUP_URL`.

The Tavily API key is stored in the Helm Secret as `TAVILY_API_KEY`. Do not commit a real key to Git.

Deploy with the key like this:

```bash
export TAVILY_API_KEY="your-real-key"

helm upgrade --install job-tracker ./helm/job-tracker \
  --namespace job-tracker \
  --create-namespace \
  --set-string linkedinLookup.tavilyApiKey="$TAVILY_API_KEY"
```

After deployment, verify the lookup service:

```bash
kubectl get pods,svc -n job-tracker | grep linkedin
kubectl logs -n job-tracker deploy/job-tracker-linkedin-lookup
```

For direct local development, run the lookup service separately:

```bash
export TAVILY_API_KEY="your-real-key"
uvicorn linkedin_lookup.main:app --host 0.0.0.0 --port 8001
```

Then set this in `.env` for the main app:

```env
LINKEDIN_LOOKUP_URL=http://localhost:8001
```
