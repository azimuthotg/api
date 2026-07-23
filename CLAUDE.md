<!-- PROJECT-STATUS
name: apiproject (NPU API Backend)
status: active
deployment: production
deploy_url: https://api.npu.ac.th
deploy_server: 202.29.55.217
deploy_os: Windows Server
deploy_method: IIS + wfastcgi — deploy ผ่าน deploy.ps1 (git pull→migrate→collectstatic→recycle app pool)
deploy_path: C:\inetpub\wwwroot\NPUAPI\apiproject
deploy_db: MySQL (โฮสต์ reserv_db ของโปรเจกต์ reserv ด้วย)
progress: 92
phase: API หลักใช้งาน production จริง · external access ปิดครบวงจร · secret ย้ายเข้า .env แล้ว · **ปิดช่องโหว่ endpoint นักศึกษา/บุคลากรครบ (apassword + สิทธิ์เขียน + list + browsable) deploy+prod verified + มี test กันถอยหลังแล้ว 2026-07-23** — เหลือเฝ้าผลผู้เรียกที่เรียกไม่บ่อย + ตัดต้นทาง apassword + รอคำตอบทีมประตูเรื่องฟิลด์บุคลากร
done_2026-07-23 (รอบบ่าย):
  - ✅ **เพิ่ม test กันถอยหลัง 7 เคส** — v1 list ต้อง 403 / DELETE-PUT-POST ต้อง 405 (ทั้ง นศ.+บุคลากร) / v2 ต้อง 401 เมื่อไม่มี token / BrowsableAPIRenderer ต้องปิด / serializer นักศึกษาต้องไม่มี apassword · พิสูจน์แล้วว่าเคสจับผิดได้จริงด้วยการลองถอด NoListMixin แล้วดูว่าแดง · push `65ea0f1` · รวม 29/29 ผ่าน
  - ❌ **ถอด `staffbirthdate`+`gendernameth` ออกจากเส้นถามตรง → ประตูเปิดไม่ได้ ต้องถอยทั้งชุด** — deploy แล้วทีมประตูแจ้งภายในไม่กี่นาที · rollback.ps1 (ใช้งานจริงครั้งที่ 2) + `git revert` `7cd9b74` เพราะ rollback ย้อนแค่เครื่อง prod · บทเรียนอยู่ใน MEM.md
  - ✅ **ระบุตัวผู้เรียก v1 แบบไม่มี auth ได้แล้ว = reserv (LINE OA) เอง** — เทียบ log 2 หน้า + โค้ด `reserv/booking/views.py` · เปลี่ยนความเสี่ยงค้างที่ "ปิดไม่ได้เพราะไม่รู้ว่าใครใช้" ให้เป็น task ที่ทำได้เอง
done_2026-07-23 (รอบเช้า):
  - ✅ **ถอด `apassword` (รหัสผ่าน plaintext) ออกจาก response ทุก endpoint** — เปลี่ยน `fields='__all__'` เป็น explicit list ทั้ง v1/v2 ปิดครบ 5 ทางที่รั่ว (`/std-info/` list+detail, `/v2/student/`, `auth_and_get_student` ทั้ง 2 เวอร์ชัน) · push `af74e23` · deploy+เทส prod ผ่าน
  - ✅ **ปิดสิทธิ์เขียน student/staff** — `ModelViewSet`→`ReadOnlyModelViewSet` 4 ViewSet (เดิม `DELETE /std-info/{id}/` เปิดสาธารณะและลบข้อมูลจริงได้ เพราะ `managed=False` ไม่กันการเขียนของ ORM) · verified 405 บน prod
  - ✅ **ปิด `list` ดึงทั้งตาราง** — เพิ่ม `NoListMixin` ใน authentication.py → 403 ทั้ง 4 ViewSet · push `112736d` · verified 403 บน prod (retrieve ยังปกติ)
  - ✅ **ปิด BrowsableAPIRenderer จริง** (เดิมคอมเมนต์บอกว่าปิดแต่บรรทัดยังทำงาน → เปิด endpoint ในเบราว์เซอร์ได้ฟอร์มพร้อมปุ่มยิง request)
  - ✅ **เพิ่ม `rollback.ps1` + จุดย้อนกลับใน deploy.ps1** — ย้อนโค้ดแบบ local ~5-10 วิ ไม่ต้องรอ GitHub · ซ้อมและใช้งานจริงบน prod ผ่านแล้ว · push `975a499`, แก้บั๊กเขียนทับจุดย้อนกลับ `4b1eda2`
  - ✅ verify ผู้เรียกจริงไม่กระทบ — traceon (ระบบประตู, ~18,000 ครั้ง/เดือน) สแกนทั้ง นศ./บุคลากร ได้ 200 ครบ, reserv + LDAP auth ปกติ, fail = 0
done_2026-07-20:
  - ✅ `/v2/external/permanent/{citizen_id}/update/` แก้ไขชื่อ-สกุล (+รูป) สมาชิกถาวร — ไม่แตะ status/permanent_code/approved_* · push `e14897d` · deploy prod + เทสร่วมกับ reserv ผ่าน (แก้ชื่อได้จริง รหัสถาวรไม่เปลี่ยน)
done_2026-07-16:
  - ✅ deploy prod (`deploy.ps1`) + เทส prod ผ่าน — issue ไม่บังคับ citizen_id ทำงานถูกต้องบน production
  - ✅ **ทีมประตูเทส QR จริงผ่านแล้วทั้ง 2 แบบ (รายวัน + ถาวร)** ผ่าน `/v2/external/check/` — ปิดงาน external access ครบวงจร (task ค้างตั้งแต่ 2026-07-12)
  - ✅ `/v2/external/issue/` ทำ `citizen_id` เป็น optional (บังคับแค่ first_name+last_name) — ไม่ส่งเลขบัตร → `_gen_external_ref_id()` gen `V`+12 หลัก (mirror permanent_register), เทสเพิ่ม 2 เคส รวม 22/22 ผ่าน, อัปเดต API_ENDPOINTS.md — push แล้ว (`2ad5701`) จับคู่งานฝั่ง reserv (`336d4e2`)
done_2026-07-13:
  - ✅ ทำความสะอาดไฟล์ untracked สำเนา/backup 7 ไฟล์ (ไฟล์เก่าปี 2024/ต้นปี 2025 ไม่ตรงโค้ดปัจจุบัน)
  - ✅ ส่งมอบเอกสาร Word คู่มือ API ให้ทีมประตู (doc/คู่มือทีมประตู-external-check-api.docx — untracked) + ทดสอบยิง /v2/external/check/ บน prod ผ่าน (permanent VVIP รหัส V… allow:true)
  - ✅ เพิ่ม test เส้นรหัสรายวัน external (DailyPoolAccessCodeTests 10 เคส: issue + check_external รายวัน) — รวม apiapp/tests.py 20/20 ผ่าน
  - ✅ ย้าย WALAI_API_TOKEN ออกจาก hardcode default (settings.py → '') + test_walai_search.py อ่านจาก .env — deploy prod + เทสเช็คสมาชิก Walai ผ่าน
  - ✅ ย้าย HA_TOKEN ออกจาก hardcode default (settings.py → '') + ลบ comment token ตกค้างใน views.py — deploy prod + เทสเปิด/ปิด IoT (Sonoff) ผ่าน
done_2026-07-10:
  - ✅ push ค้าง 2 commits ขึ้น GitHub สำเร็จ (แก้จากฝั่ง Windows แทน WSL token ที่หมดอายุ)
  - ✅ deploy prod (git pull + restart) เรียบร้อย, เทส prod ผ่าน — permanent_register ไม่บังคับ citizen_id (VVIP) ทำงานถูกต้อง
  - ✅ permanent_register ไม่บังคับ citizen_id (รองรับ VVIP เช่น นายกสภาฯ) — เว้นว่างแล้ว gen รหัสอ้างอิง `V`+12 หลัก, ขยาย url regex รับ `V…`, ไม่มี migration, test 10/10
done_2026-07-09:
  - ✅ external member integration กับ reserv ครบ (prod verified) — approve เก็บ approved_by จริง + endpoint ลบสมาชิกถาวร (hard delete)
  - ✅ เริ่มมี automated tests แล้ว (`apiapp/tests.py` 6 เคส + `apiproject/test_settings.py` sqlite) — เดิมไม่มีเลย
next:
  - ย้าย reserv `_fetch_npu_profile()` จาก v1 (`/std-info/`,`/staff-info/` ไม่ต้อง auth) ไปเรียก v2 + Bearer token แล้วปิด v1 retrieve ให้ต้อง auth — reserv มีบัญชี JWT + cache token พร้อมใช้อยู่แล้ว (แตะ 2 repo, deploy พร้อมกัน · ดู MEM.md)
  - เฝ้าดู `/monitor/api-usage/` ถึงราว 2026-07-26 ว่า emoney / courses / pfss (เรียกไม่บ่อย ยังไม่ได้ผ่านโค้ดใหม่) ทำงานปกติหลังถอด apassword
  - ตัดต้นทาง apassword — แก้ `aims_project/dashboard/management/commands/sync_students.py` เลิกดึงคอลัมน์ APASSWORD จาก Oracle แล้ว `ALTER TABLE students_info DROP COLUMN apassword` (ทำหลัง 2026-07-30 ให้ของใหม่นิ่งก่อน · สำรองตารางก่อนเสมอ)
  - **ถามทีมประตู (traceon) ว่าใช้ `staffbirthdate` / `gendernameth` ตัวไหนบ้าง** — ลองถอดออกจากเส้นถามตรงแล้ว 2026-07-23 ประตูเปิดไม่ได้ทันที ต้อง rollback + revert (`7cd9b74`) · ห้ามลองใหม่จนกว่าจะได้คำตอบ (ดู MEM.md) · ถ้าเขาใช้ทั้งคู่ = ปิด task นี้ว่าถอดไม่ได้
  - ทำ fixture/mock ให้ `StudentsInfo`/`StaffInfo` (managed=False → ตารางไม่ถูกสร้างตอนเทส) เพื่อคุม `retrieve` ที่ต้องได้ 200 พร้อมฟิลด์ถูกต้อง — ตอนนี้เทสคุมได้แค่เส้นทางที่ต้องถูกปฏิเสธ ซึ่งเป็นช่องว่างเดียวกับที่ทำให้เหตุประตูเปิดไม่ได้หลุดไปถึง prod
  - เพิ่ม test ให้ `permanent/{id}/update/` (deploy+เทสมือผ่านแล้ว แต่ยังไม่มีเคสใน apiapp/tests.py — เคสสำคัญ: แก้ชื่อคน active แล้ว status/permanent_code ต้องไม่เปลี่ยน)
  - ขยาย test coverage endpoint กลุ่มที่ต่อระบบภายนอก (LDAP/Walai/MikroTik/Sonoff) — ต้อง mock (ปัจจุบันคุมแค่ external member ทั้ง permanent + daily)
  - ทำความสะอาดไฟล์ backup local ที่มี secret ตกค้าง (code_deploy/, settings27062025.py — gitignore อยู่ ไม่หลุด repo แต่ยังมี token เก่าในเครื่อง)
  - ศึกษา security ที่ต้องทำสำหรับ API นี้ (เช่น auth/rate-limit/input validation/HTTPS — ยังไม่ได้กำหนดขอบเขต) — รับแจ้ง 2026-07-12
  - ศึกษาการบริหารจัดการ API ในภาพรวม (API management/versioning/monitoring/gateway ฯลฯ) — รับแจ้ง 2026-07-12
risks:
  - `students_info.apassword` ยังเก็บรหัสผ่าน plaintext ไว้ใน DB (10,789 แถว) — ปิดทาง API แล้ว แต่ยังไม่ตัดต้นทาง/drop คอลัมน์ (ดู MEM.md)
  - `/std-info/`,`/staff-info/` (v1) ยังไม่ต้อง auth — ใครรู้รหัส นศ./เลขบัตร ยิงดูชื่อ-คณะ-สาขาได้ (ปิด list + สิทธิ์เขียนแล้ว เหลือ retrieve) · **ระบุตัวผู้เรียกได้แล้ว 2026-07-23 = reserv เอง → ปิดได้ มี task ใน next**
  - secret เคย hardcode ใน settings.py (Walai+HA token) — ย้ายเข้า .env แล้ว 2026-07-13; เหลือสำเนา token เก่าในไฟล์ backup local (gitignore)
  - `/v2/external/issue/` ไม่บังคับ citizen_id → ระงับสิทธิ์/โควตารายคนใช้ไม่ได้ + pool 100 รหัส/วันอาจหมดเร็ว (ดู MEM.md — มีแผนถอย)
updated: 2026-07-23
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
