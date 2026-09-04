#!/usr/bin/env bash
# Deploy the training dashboard to Cloud Run.
#
#   ./deploy.sh                  # deploy with demo data
#   ./deploy.sh --no-sample      # deploy empty, ready for real staff
#   ./deploy.sh --password '...' # choose the manager password
#
# Written for Google Cloud Shell (https://shell.cloud.google.com), where gcloud
# is installed and you are already signed in. Works on any machine with gcloud.

set -euo pipefail

SERVICE="sales-training"
REGION="europe-west1"          # same region as the 17 decks (-ew)
PASSWORD=""
SAMPLE=1

while [ $# -gt 0 ]; do
  case "$1" in
    --no-sample) SAMPLE=0; shift ;;
    --password)  PASSWORD="${2:-}"; shift 2 ;;
    --service)   SERVICE="${2:-}"; shift 2 ;;
    --region)    REGION="${2:-}"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

c_cyan=$'\033[36m'; c_green=$'\033[32m'; c_yellow=$'\033[33m'; c_red=$'\033[31m'; c_off=$'\033[0m'
step() { printf '\n%s[%s] %s%s\n' "$c_cyan" "$1" "$2" "$c_off"; }
ok()   { printf '    %s%s%s\n' "$c_green" "$1" "$c_off"; }
die()  { printf '\n%sSTOPPED: %s%s\n\n' "$c_red" "$1" "$c_off"; exit 1; }

step 1 "Checking the folder"
if [ ! -f Dockerfile ] || [ ! -f training/main.py ]; then
  die "This is not the project folder.

  cd into the repository first:
    cd ~/AI-Research-Assistant

  If you have not downloaded it yet:
    git clone -b claude/training-staff-links-b7u1xx \\
      https://github.com/elshaghnouby/AI-Research-Assistant.git"
fi
ok "found Dockerfile and training/"

step 2 "Checking gcloud"
command -v gcloud >/dev/null 2>&1 || \
  die "gcloud is not installed. Use Cloud Shell at https://shell.cloud.google.com — it is already there."
ok "gcloud found"

step 3 "Checking your Google sign-in"
ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | head -1 || true)"
if [ -z "$ACCOUNT" ]; then
  printf '    %sNot signed in — starting sign-in.%s\n' "$c_yellow" "$c_off"
  gcloud auth login
  ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | head -1 || true)"
  [ -n "$ACCOUNT" ] || die "Sign-in did not complete. Run 'gcloud auth login' on its own and try again."
fi
ok "signed in as $ACCOUNT"

step 4 "Checking the project"
PROJECT="$(gcloud config get-value project 2>/dev/null || true)"
if [ -z "$PROJECT" ] || [ "$PROJECT" = "(unset)" ]; then
  printf '    %sNo project selected. Yours:%s\n' "$c_yellow" "$c_off"
  gcloud projects list --format='table(projectId, name)'
  printf '\n    Type the PROJECT_ID that hosts the 17 training decks: '
  read -r PROJECT
  [ -n "$PROJECT" ] || die "No project given."
  gcloud config set project "$PROJECT" >/dev/null
fi
ok "project: $PROJECT"

step 5 "Enabling the APIs Cloud Run needs (skipped if already on)"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com --quiet
ok "run, cloudbuild, artifactregistry ready"

step 6 "Manager password"
if [ -z "$PASSWORD" ]; then
  PASSWORD="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 16)"
  ok "generated one for you (shown at the end)"
else
  ok "using the password you passed in"
fi

step 7 "Building and deploying — this takes 3-5 minutes the first time"
ENV_VARS="SEED_ON_START=1,MANAGER_PASSWORD=$PASSWORD"
[ "$SAMPLE" = "1" ] && ENV_VARS="SEED_SAMPLE=1,$ENV_VARS"

gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "$ENV_VARS" \
  --quiet || die "The deploy failed. The error above is from Google Cloud — send it over."

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"

printf '\n%s%s%s\n' "$c_green" "==============================================================" "$c_off"
printf '%s LIVE:  %s%s\n' "$c_green" "$URL" "$c_off"
printf '%s\n' "=============================================================="
printf ' Sign in as manager@baroncabot.example\n'
printf ' Password:  %s\n\n' "$PASSWORD"
printf '%s Write that password down — it is not stored anywhere.%s\n' "$c_yellow" "$c_off"
if [ "$SAMPLE" = "1" ]; then
  printf " Demo data is loaded, so the dashboard carries a 'Sample data' badge.\n"
  printf ' Redeploy with  ./deploy.sh --no-sample  when real staff start using it.\n'
fi
printf '\n%s Note: Cloud Run'"'"'s disk is temporary, so this database resets when the\n' "$c_yellow"
printf ' service restarts. Fine for trying it out. Before the team relies on it,\n'
printf ' set DATABASE_URL to a managed Postgres instance.%s\n\n' "$c_off"
