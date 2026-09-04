# Deploy the training dashboard to Cloud Run.
#
#   .\deploy.ps1                      # deploy with demo data
#   .\deploy.ps1 -NoSample            # deploy empty, ready for real staff
#   .\deploy.ps1 -Password "..."      # choose the manager password
#
# Run it from inside the repository folder. It checks everything first and
# stops with a plain explanation rather than half-deploying.

[CmdletBinding()]
param(
  [string]$Service  = "sales-training",
  [string]$Region   = "europe-west1",     # same region as the 17 decks (-ew)
  [string]$Password = "",
  [switch]$NoSample
)

$ErrorActionPreference = "Stop"

function Step($n, $msg) { Write-Host "`n[$n] $msg" -ForegroundColor Cyan }
function Ok($msg)       { Write-Host "    $msg" -ForegroundColor Green }
function Die($msg)      { Write-Host "`nSTOPPED: $msg`n" -ForegroundColor Red; exit 1 }

# --- 1. right folder -------------------------------------------------------
Step 1 "Checking the folder"
if (-not (Test-Path "./Dockerfile") -or -not (Test-Path "./training/main.py")) {
  Die @"
This is not the project folder.

  cd into the repository first, for example:
    cd `$HOME\AI-Research-Assistant

  If you have not downloaded it yet:
    git clone -b claude/training-staff-links-b7u1xx ``
      https://github.com/elshaghnouby/AI-Research-Assistant.git
"@
}
Ok "found Dockerfile and training/ — deploying $(Split-Path -Leaf (Get-Location))"

# --- 2. gcloud present -----------------------------------------------------
Step 2 "Checking gcloud"
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
  Die "gcloud is not installed. Install the Google Cloud CLI, or use Cloud Shell at https://shell.cloud.google.com (gcloud is already there)."
}
Ok "gcloud found"

# --- 3. signed in ----------------------------------------------------------
Step 3 "Checking your Google sign-in"
$account = (gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>$null | Select-Object -First 1)
if (-not $account) {
  Write-Host "    Not signed in — opening a browser." -ForegroundColor Yellow
  gcloud auth login
  $account = (gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>$null | Select-Object -First 1)
  if (-not $account) { Die "Sign-in did not complete. Run 'gcloud auth login' on its own and try again." }
}
Ok "signed in as $account"

# --- 4. project ------------------------------------------------------------
Step 4 "Checking the project"
$project = (gcloud config get-value project 2>$null)
if (-not $project -or $project -eq "(unset)") {
  Write-Host "    No project selected. Yours:" -ForegroundColor Yellow
  gcloud projects list --format="table(projectId, name)"
  $project = Read-Host "`n    Type the PROJECT_ID that hosts the 17 training decks"
  if (-not $project) { Die "No project given." }
  gcloud config set project $project | Out-Null
}
Ok "project: $project"

# --- 5. APIs ---------------------------------------------------------------
Step 5 "Enabling the APIs Cloud Run needs (skipped if already on)"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --quiet
Ok "run, cloudbuild, artifactregistry ready"

# --- 6. password -----------------------------------------------------------
Step 6 "Manager password"
if (-not $Password) {
  $chars = (48..57) + (65..90) + (97..122)      # 0-9 A-Z a-z, nothing to escape
  $Password = -join ($chars | Get-Random -Count 16 | ForEach-Object { [char]$_ })
  Ok "generated one for you (shown at the end)"
} else {
  Ok "using the password you passed in"
}

# --- 7. deploy -------------------------------------------------------------
Step 7 "Building and deploying — this takes 3-5 minutes the first time"
$envVars = "SEED_ON_START=1,MANAGER_PASSWORD=$Password"
if (-not $NoSample) { $envVars = "SEED_SAMPLE=1,$envVars" }

gcloud run deploy $Service `
  --source . `
  --region $Region `
  --allow-unauthenticated `
  --set-env-vars $envVars `
  --quiet
if ($LASTEXITCODE -ne 0) { Die "The deploy failed. The error above is from Google Cloud — send it over." }

$url = (gcloud run services describe $Service --region $Region --format="value(status.url)")

Write-Host "`n$('=' * 62)" -ForegroundColor Green
Write-Host " LIVE:  $url" -ForegroundColor Green
Write-Host "$('=' * 62)"
Write-Host " Sign in as manager@baroncabot.example"
Write-Host " Password:  $Password"
Write-Host ""
Write-Host " Write that password down — it is not stored anywhere." -ForegroundColor Yellow
if (-not $NoSample) {
  Write-Host " Demo data is loaded, so the dashboard carries a 'Sample data' badge."
  Write-Host " Redeploy with  .\deploy.ps1 -NoSample  when real staff start using it."
}
Write-Host ""
Write-Host " Note: Cloud Run's disk is temporary, so this database resets when the"
Write-Host " service restarts. Fine for trying it out. Before the team relies on it,"
Write-Host " set DATABASE_URL to a managed Postgres instance." -ForegroundColor Yellow
Write-Host ""
