# deploy.ps1 — Git-based deployment for the NPU API (IIS + wfastcgi)
#
# Run this ON THE PRODUCTION SERVER from the project root:
#   cd C:\inetpub\wwwroot\NPUAPI\apiproject
#   .\deploy.ps1
#
# It replaces the old copy-paste deploy: pull latest code from GitHub,
# apply migrations, refresh static files, then recycle the IIS app pool
# so wfastcgi reloads the new code.

$ErrorActionPreference = "Stop"

# --- Production server settings -------------------------------------------
$ProjectDir = "C:\inetpub\wwwroot\NPUAPI\apiproject"
$Python     = "C:\Python312\python.exe"
$AppPool    = "apiproject"
# --------------------------------------------------------------------------

Set-Location $ProjectDir

# Safety: refuse to deploy if there are uncommitted changes to tracked files.
$dirty = git status --porcelain --untracked-files=no
if ($dirty) {
    Write-Host "==> Aborting: tracked files have local changes on the server." -ForegroundColor Red
    Write-Host $dirty
    Write-Host "    Commit or discard them before deploying." -ForegroundColor Red
    exit 1
}

Write-Host "==> Pulling latest code from origin/main..." -ForegroundColor Cyan
git pull origin main

Write-Host "==> Applying database migrations..." -ForegroundColor Cyan
& $Python manage.py migrate --noinput

Write-Host "==> Collecting static files..." -ForegroundColor Cyan
& $Python manage.py collectstatic --noinput

Write-Host "==> Recycling IIS app pool '$AppPool'..." -ForegroundColor Cyan
Import-Module WebAdministration
Restart-WebAppPool -Name $AppPool

Write-Host "==> Deploy complete." -ForegroundColor Green
git log -1 --oneline
