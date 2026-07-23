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

# Remember the currently-running commit as the rollback target. Written only
# AFTER the pull and only when HEAD actually moved — a repeated no-op deploy
# would otherwise overwrite it with the current commit and silently destroy
# the way back.
$before = (git rev-parse HEAD).Trim()
Write-Host "==> commit ที่รันอยู่ก่อน deploy: $before" -ForegroundColor Cyan

Write-Host "==> Pulling latest code from origin/main..." -ForegroundColor Cyan
git pull origin main

$after = (git rev-parse HEAD).Trim()
if ($after -eq $before) {
    Write-Host "==> ไม่มี commit ใหม่ — คง .deploy-last-good เดิมไว้ (ไม่เขียนทับ)" -ForegroundColor Yellow
} else {
    $before | Out-File -FilePath ".deploy-last-good" -Encoding ascii -NoNewline
    Write-Host "==> บันทึกจุดย้อนกลับไว้แล้ว: $before" -ForegroundColor Cyan
}

Write-Host "==> Applying database migrations..." -ForegroundColor Cyan
& $Python manage.py migrate --noinput

Write-Host "==> Collecting static files..." -ForegroundColor Cyan
& $Python manage.py collectstatic --noinput

Write-Host "==> Recycling IIS app pool '$AppPool'..." -ForegroundColor Cyan
Import-Module WebAdministration
Restart-WebAppPool -Name $AppPool

# Smoke check — non-fatal: บอกให้รู้เร็วที่สุดว่าควรย้อนกลับไหม
Write-Host "==> Smoke check /health/ ..." -ForegroundColor Cyan
try {
    $r = Invoke-WebRequest -Uri "https://api.npu.ac.th/health/" -UseBasicParsing -TimeoutSec 20
    Write-Host "    HTTP $($r.StatusCode) — $($r.Content)" -ForegroundColor Green
} catch {
    Write-Host "    เรียก /health/ ไม่สำเร็จ: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "    ตรวจด้วยมืออีกครั้ง ถ้าระบบใช้งานไม่ได้ให้รัน .\rollback.ps1 ทันที" -ForegroundColor Yellow
}

Write-Host "==> Deploy complete." -ForegroundColor Green
git log -1 --oneline

# บอกให้ชัดว่าถ้าย้อนกลับตอนนี้จะไปโผล่ที่ commit ไหน
Write-Host ""
if (Test-Path ".deploy-last-good") {
    $lastGood = (Get-Content ".deploy-last-good" -Raw).Trim()
    Write-Host "==> ถ้าต้องย้อนกลับ ใช้ .\rollback.ps1 — จะย้อนไปที่:" -ForegroundColor Cyan
    git log -1 --oneline $lastGood
} else {
    Write-Host "==> ยังไม่มี .deploy-last-good — ถ้าต้องย้อนกลับต้องระบุเอง: .\rollback.ps1 -To <sha>" -ForegroundColor Yellow
}
