# rotate_access_log.ps1
# รัน management command rotate_access_log เพื่อ:
#   1) ย้าย API access log ของวันก่อนหน้า จากตารางสด -> คลัง (api_access_archive)
#   2) ลบคลังที่เกิน 90 วัน
# ตั้งให้ Windows Task Scheduler เรียกไฟล์นี้ทุกเที่ยงคืนบนเครื่อง prod
#
# รันเอง (ทดสอบ):
#   powershell -ExecutionPolicy Bypass -File .\rotate_access_log.ps1
#   powershell -ExecutionPolicy Bypass -File .\rotate_access_log.ps1 -DryRun
#
# ดู log (อ่านเป็น UTF-8 เพื่อให้ภาษาไทยไม่เพี้ยน):
#   Get-Content .\logs\rotate_access_log.log -Encoding UTF8 -Tail 30

param(
    [switch]$DryRun
)

# โฟลเดอร์โปรเจกต์ = ที่อยู่ของสคริปต์นี้ / Python ของระบบ (เดียวกับ deploy.ps1)
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = 'C:\Python312\python.exe'

$logDir = Join-Path $ProjectDir 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir 'rotate_access_log.log'

function Write-Log($msg) {
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $logFile -Value "[$stamp] $msg" -Encoding UTF8
}

Write-Log "start rotate_access_log (DryRun=$DryRun)"

Set-Location $ProjectDir
$pyArgs = @('manage.py', 'rotate_access_log')
if ($DryRun) { $pyArgs += '--dry-run' }

# จับ stdout+stderr ทั้งคู่ลง log โดย "ไม่" ปล่อยให้ stderr ของ native exe
# กลายเป็น terminating error (ปัญหาคลาสสิกของ PowerShell 5.1) — ตัดสินสำเร็จ/พัง
# จาก exit code จริง ($LASTEXITCODE) แทน
$prev = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$output = & $Python @pyArgs 2>&1
$code = $LASTEXITCODE
$ErrorActionPreference = $prev

foreach ($line in $output) {
    Add-Content -Path $logFile -Value "    $line" -Encoding UTF8
}

if ($code -eq 0) {
    Write-Log "done (exit 0)"
} else {
    Write-Log "FAILED (exit $code)"
    exit $code
}
