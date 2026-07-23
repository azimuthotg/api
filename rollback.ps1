# rollback.ps1 — Emergency rollback for the NPU API (IIS + wfastcgi)
#
# Run this ON THE PRODUCTION SERVER from the project root:
#   cd C:\inetpub\wwwroot\NPUAPI\apiproject
#   .\rollback.ps1                 # ย้อนไป commit ที่ deploy.ps1 บันทึกไว้ก่อน pull ครั้งล่าสุด
#   .\rollback.ps1 -To <sha>       # ย้อนไป commit ที่ระบุเอง
#   .\rollback.ps1 -DryRun         # ดูว่าจะทำอะไรบ้าง โดยไม่แตะระบบจริง
#
# ทำงานแบบ local ล้วน — ไม่ต้องรอ GitHub, ไม่ต้องรอเครื่อง dev
# ใช้เวลา ~5-10 วินาที (reset code + recycle app pool)
#
# ข้อจำกัดสำคัญ: สคริปต์นี้ย้อน "โค้ด" เท่านั้น **ไม่ย้อน migration ของฐานข้อมูล**
# ถ้า commit ที่จะย้อนกลับมีการเพิ่ม migration สคริปต์จะเตือนและให้ยืนยันด้วย -Force

param(
    [string]$To = "",
    [switch]$DryRun,
    [switch]$Force,
    [string]$ProjectDir = "C:\inetpub\wwwroot\NPUAPI\apiproject"
)

$ErrorActionPreference = "Stop"

# --- Production server settings (ต้องตรงกับ deploy.ps1) --------------------
$Python       = "C:\Python312\python.exe"
$AppPool      = "apiproject"
$LastGoodFile = ".deploy-last-good"
# --------------------------------------------------------------------------

Set-Location $ProjectDir

$current = (git rev-parse HEAD).Trim()
Write-Host "==> HEAD ปัจจุบัน: $current" -ForegroundColor Cyan
git log -1 --oneline

# --- หา commit ปลายทาง -----------------------------------------------------
if (-not $To) {
    if (Test-Path $LastGoodFile) {
        $To = (Get-Content $LastGoodFile -Raw).Trim()
        Write-Host "==> ใช้ commit จาก $LastGoodFile : $To" -ForegroundColor Cyan
    } else {
        $To = (git rev-parse HEAD~1).Trim()
        Write-Host "==> ไม่พบ $LastGoodFile — ใช้ HEAD~1 แทน: $To" -ForegroundColor Yellow
    }
}

# ตรวจว่า commit ปลายทางมีอยู่จริง (--quiet: ไม่มี output = ไม่พบ, เลี่ยงการ redirect stderr)
$resolved = git rev-parse --verify --quiet "$To^{commit}"
if (-not $resolved) {
    Write-Host "==> ยกเลิก: ไม่พบ commit '$To' ใน repo นี้" -ForegroundColor Red
    exit 1
}
$To = $resolved.Trim()

if ($To -eq $current) {
    Write-Host "==> HEAD อยู่ที่ commit นั้นอยู่แล้ว ไม่มีอะไรต้องย้อน" -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "==> จะย้อนกลับไปที่:" -ForegroundColor Cyan
git log -1 --oneline $To
Write-Host ""
Write-Host "==> ไฟล์ที่จะเปลี่ยน:" -ForegroundColor Cyan
git diff --stat $current $To

# --- เตือนเรื่อง migration -------------------------------------------------
$migrations = git diff --name-only $current $To -- "*/migrations/*"
if ($migrations) {
    Write-Host ""
    Write-Host "==> !! คำเตือน: ช่วง commit นี้มีไฟล์ migration เปลี่ยน" -ForegroundColor Red
    Write-Host $migrations
    Write-Host "    สคริปต์นี้ย้อนแค่โค้ด ไม่ย้อนฐานข้อมูล — ต้อง migrate ย้อนเองด้วยมือ" -ForegroundColor Red
    if (-not $Force) {
        Write-Host "    ยกเลิกไว้ก่อน ถ้ายืนยันว่าต้องการจริงให้ใส่ -Force" -ForegroundColor Red
        exit 1
    }
    Write-Host "    -Force ถูกระบุ — ดำเนินการต่อ" -ForegroundColor Yellow
}

# --- เตือนถ้ามีไฟล์ที่แก้ค้างไว้บนเซิร์ฟเวอร์ -------------------------------
$dirty = git status --porcelain --untracked-files=no
if ($dirty) {
    Write-Host ""
    Write-Host "==> !! คำเตือน: มีไฟล์ที่ถูกแก้ค้างไว้บนเซิร์ฟเวอร์ และจะถูกทิ้งไป" -ForegroundColor Red
    Write-Host $dirty
    if (-not $Force) {
        Write-Host "    ยกเลิกไว้ก่อน ถ้ายืนยันว่าทิ้งได้ให้ใส่ -Force" -ForegroundColor Red
        exit 1
    }
    Write-Host "    -Force ถูกระบุ — ดำเนินการต่อ" -ForegroundColor Yellow
}

if ($DryRun) {
    Write-Host ""
    Write-Host "==> DryRun: ไม่ได้แก้อะไรจริง จบการทำงาน" -ForegroundColor Green
    exit 0
}

# --- ย้อนกลับ --------------------------------------------------------------
Write-Host ""
Write-Host "==> บันทึก commit ปัจจุบันไว้ที่ .rollback-from (เผื่อกลับมาใหม่)..." -ForegroundColor Cyan
$current | Out-File -FilePath ".rollback-from" -Encoding ascii -NoNewline

Write-Host "==> ย้อนโค้ดกลับไปที่ $To ..." -ForegroundColor Cyan
git reset --hard $To

Write-Host "==> Collecting static files..." -ForegroundColor Cyan
& $Python manage.py collectstatic --noinput

Write-Host "==> Recycling IIS app pool '$AppPool'..." -ForegroundColor Cyan
Import-Module WebAdministration
Restart-WebAppPool -Name $AppPool

Write-Host ""
Write-Host "==> Rollback เสร็จแล้ว — HEAD ตอนนี้:" -ForegroundColor Green
git log -1 --oneline
Write-Host ""
Write-Host "หมายเหตุ: prod ตอนนี้อยู่หลัง origin/main — deploy.ps1 ครั้งถัดไปจะ pull กลับขึ้นมาเอง" -ForegroundColor Yellow
Write-Host "          ถ้าต้องการให้ origin/main กลับไปด้วย ให้ทำ git revert บนเครื่อง dev แล้ว push" -ForegroundColor Yellow
