# rotate_access_log.ps1
# รัน management command rotate_access_log เพื่อ:
#   1) ย้าย API access log ของวันก่อนหน้า จากตารางสด -> คลัง (api_access_archive)
#   2) ลบคลังที่เกิน 90 วัน
# ตั้งให้ Windows Task Scheduler เรียกไฟล์นี้ทุกเที่ยงคืนบนเครื่อง prod
#
# รันเอง (ทดสอบ):
#   powershell -ExecutionPolicy Bypass -File .\rotate_access_log.ps1
#   powershell -ExecutionPolicy Bypass -File .\rotate_access_log.ps1 -DryRun

param(
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

# โฟลเดอร์โปรเจกต์ = ที่อยู่ของสคริปต์นี้
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# Python ของระบบ (เดียวกับที่ wfastcgi/IIS ใช้ ดู deploy.ps1 / CLAUDE.md)
$Python = 'C:\Python312\python.exe'

$logDir = Join-Path $ProjectDir 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir 'rotate_access_log.log'

$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Add-Content -Path $logFile -Value "[$stamp] เริ่ม rotate_access_log (DryRun=$DryRun)"

Set-Location $ProjectDir
$args = @('manage.py', 'rotate_access_log')
if ($DryRun) { $args += '--dry-run' }

$output = & $Python @args 2>&1
$output | ForEach-Object { Add-Content -Path $logFile -Value "    $_" }

$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
if ($LASTEXITCODE -eq 0) {
    Add-Content -Path $logFile -Value "[$stamp] เสร็จเรียบร้อย (exit 0)"
} else {
    Add-Content -Path $logFile -Value "[$stamp] ล้มเหลว (exit $LASTEXITCODE)"
    exit $LASTEXITCODE
}
