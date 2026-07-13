<!-- PROJECT-STATUS
name: apiproject (NPU API Backend)
status: active
deployment: production
progress: 87
phase: API หลักใช้งาน production จริง · external library member (permanent, รองรับ VVIP ไม่บังคับเลขบัตร) integration กับ reserv เสร็จ+prod verified+e2e ผ่าน — เหลือรอทีมประตูเทส QR code
done_2026-07-10:
  - ✅ push ค้าง 2 commits ขึ้น GitHub สำเร็จ (แก้จากฝั่ง Windows แทน WSL token ที่หมดอายุ)
  - ✅ deploy prod (git pull + restart) เรียบร้อย, เทส prod ผ่าน — permanent_register ไม่บังคับ citizen_id (VVIP) ทำงานถูกต้อง
  - ✅ permanent_register ไม่บังคับ citizen_id (รองรับ VVIP เช่น นายกสภาฯ) — เว้นว่างแล้ว gen รหัสอ้างอิง `V`+12 หลัก, ขยาย url regex รับ `V…`, ไม่มี migration, test 10/10
done_2026-07-09:
  - ✅ external member integration กับ reserv ครบ (prod verified) — approve เก็บ approved_by จริง + endpoint ลบสมาชิกถาวร (hard delete)
  - ✅ เริ่มมี automated tests แล้ว (`apiapp/tests.py` 6 เคส + `apiproject/test_settings.py` sqlite) — เดิมไม่มีเลย
done_2026-07-13:
  - ✅ ทำความสะอาดไฟล์ untracked ที่เป็นสำเนา/backup 7 ไฟล์ (views copy.py, settings 21032568.py, home 25092567.html, home_url copy.html, room_control copy.html, views lineliff.py ฯลฯ) — ลบแล้วยืนยันเป็นไฟล์เก่าปี 2024/ต้นปี 2025 ไม่ตรงกับโค้ดปัจจุบัน
next:
  - แจ้งทีมประตูให้เอา QR code ไปทดสอบว่าเข้าได้จริงหรือไม่ (route `/v2/external/check/` พร้อมแล้วฝั่ง API, รอทีมประตูเพิ่ม route 10 หลักและทดสอบ)
  - ขยาย test coverage ให้ครอบคลุม endpoint อื่น (ปัจจุบันมีแค่ external member permanent, มี tests/test_walai_search.py ใหม่ยังไม่ commit)
  - ศึกษา security ที่ต้องทำสำหรับ API นี้ (เช่น auth/rate-limit/input validation/HTTPS — ยังไม่ได้กำหนดขอบเขต) — รับแจ้ง 2026-07-12
  - ศึกษาการบริหารจัดการ API ในภาพรวม (API management/versioning/monitoring/gateway ฯลฯ) — รับแจ้ง 2026-07-12
updated: 2026-07-13
-->

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Django 5.0.7 REST API backend for NPU (Nakhon Pathom University). Serves as a multi-functional platform integrating authentication, user management, library systems, IoT controls, and room reservations. Deployed on IIS (Windows) via FastCGI with Python 3.12.

## Common Commands

```bash
# Development server
python manage.py runserver

# Database migrations
python manage.py makemigrations
python manage.py migrate

# Collect static files (required before deployment)
python manage.py collectstatic

# Admin user creation
python manage.py createsuperuser
```

There are no automated tests in this project.

## Deployment

Production is git-based via `deploy.ps1` (not copy-paste). Dev pushes to `origin/main`; on the prod server (`202.29.55.217`, RDP) run from the project root `C:\inetpub\wwwroot\NPUAPI\apiproject`:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy.ps1
```

The script pulls `origin/main`, runs `migrate` + `collectstatic`, then recycles the IIS app pool `apiproject` (system Python `C:\Python312\python.exe`, wfastcgi). The site is bound to host `api.npu.ac.th` only — `localhost` requests return IIS 404. See README.md → "การ Deploy บน IIS" for first-time setup and details.

## Architecture

### Dual API Versioning

The project maintains two parallel API versions in `apiapp/`:

- **V1 (Legacy):** Session-based auth. ViewSets in `views.py`, serializers in `serializer.py`. Routes registered under `/api/`, `/std-info/`, `/auth-ldap/`, `/staff-info/`, `/walai/`, `/mt/`, `/sonoff/`.
- **V2 (Modern):** JWT Bearer token auth. ViewSets in `views_v2.py`, serializers in `serializers_v2.py`. All routes prefixed with `/v2/`. Token endpoints at `/v2/token/` and `/v2/token/refresh/`.

Both versions are registered in `apiproject/urls.py` using DRF `DefaultRouter`.

### Authentication Pattern

`apiapp/authentication.py` defines two mixins used on V2 ViewSets:
- `JWTRequiredAuthentication` — protects endpoints, validates Bearer tokens
- `PublicEndpointAuthentication` — skips auth for login/token endpoints

JWT tokens have a 365-day access lifetime (configured in `settings.py`).

### Database Models

`StudentsInfo` and `StaffInfo` are **read-only** (`managed=False`) models that map to existing university database tables. `UserProfile` is the only writable Django-managed model.

### ReservApp

`reservapp/` handles room reservations and LINE OA integration. It uses **Google Sheets as a backend** (via `gspread`) instead of Django models — no database tables. Room-to-spreadsheet mappings are hardcoded in `reservapp/views.py`. Templates are in `reservapp/templates/reservapp/`.

### External Integrations

| Service | Purpose | Location |
|---|---|---|
| Active Directory (LDAP3) | User authentication, `NPU.local` domain | `views.py` / `views_v2.py` `auth_ldap` actions |
| MikroTik RouterOS API | Hotspot user management | `views.py` / `views_v2.py` MikroTik ViewSets |
| Home Assistant REST API | IoT device control (lights, AC, projectors) | `views_v2.py` `SonoffControlViewSetV2` |
| Walai Library API | Library membership check | `views.py` / `views_v2.py` Walai ViewSets |
| Google Sheets (gspread) | Room reservation storage | `reservapp/views.py` |

### Settings & Configuration

- Main settings: `apiproject/settings.py`
- Credentials are loaded from `.env` (database, MikroTik, Home Assistant token, Walai token)
- `apiproject/settings27062025.py` and `apiproject/settings 21032568.py` are backup files — do not use
- CORS allowed origins are explicitly listed in `settings.py` (includes production domains `api.npu.ac.th`, `rdb.npu.ac.th`, `arc.npu.ac.th`)
- Static files served via WhiteNoise middleware; collected to `/static/`
- Response timing logged via custom middleware in `apiproject/middleware.py`

## กติกาการปิด session
ก่อนจบงานทุกครั้ง ให้อัปเดตบล็อก <!-- PROJECT-STATUS --> ด้านบนของไฟล์นี้:
ปรับ progress, phase, รายการ next ให้ตรงกับงานจริง และแก้ updated เป็นวันที่ปัจจุบัน
จากนั้นรัน `python C:\projects\project_status.py` เพื่ออัปเดต dashboard รวม
