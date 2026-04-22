# API Endpoints

## API v1 (ไม่ต้องใช้ JWT)

### User Profile — `/api/`

| Method | URL | คำอธิบาย |
|--------|-----|-----------|
| GET | `/api/` | ดูรายการ UserProfile ทั้งหมด |
| POST | `/api/` | สร้าง UserProfile ใหม่ |
| GET | `/api/{userId}/` | ดู UserProfile ตาม userId |
| PUT/PATCH | `/api/{userId}/` | แก้ไข UserProfile |
| DELETE | `/api/{userId}/` | ลบ UserProfile |

### ข้อมูลนักศึกษา — `/std-info/`

| Method | URL | คำอธิบาย |
|--------|-----|-----------|
| GET | `/std-info/` | รายการนักศึกษาทั้งหมด |
| GET | `/std-info/{student_code}/` | ข้อมูลนักศึกษาตามรหัส |

### ข้อมูลบุคลากร — `/staff-info/`

| Method | URL | คำอธิบาย |
|--------|-----|-----------|
| GET | `/staff-info/` | รายการบุคลากรทั้งหมด |
| GET | `/staff-info/{staffcitizenid}/` | ข้อมูลบุคลากรตามเลขบัตรประชาชน |

### LDAP Authentication — `/auth-ldap/`

| Method | URL | Body | คำอธิบาย |
|--------|-----|------|-----------|
| POST | `/auth-ldap/auth_ldap/` | `userLdap`, `passLdap` | ตรวจสอบ AD แล้วคืน displayName, email |
| POST | `/auth-ldap/auth_and_get_student/` | `userLdap`, `passLdap` | ตรวจสอบ AD แล้วคืนข้อมูลนักศึกษา |

### ห้องสมุด Walai — `/walai/`

| Method | URL | คำอธิบาย |
|--------|-----|-----------|
| GET | `/walai/check_user_walai/{user_ldap}/` | ตรวจสอบสมาชิกห้องสมุด |

### MikroTik Hotspot — `/mt/`

| Method | URL | คำอธิบาย |
|--------|-----|-----------|
| GET | `/mt/list-users/` | รายชื่อ Hotspot users ทั้งหมด |
| GET | `/mt/enable/{username}/` | เปิดใช้งาน user |
| GET | `/mt/disable/{username}/` | ปิดใช้งาน user |

### IoT (Sonoff/HA) — `/sonoff/`

| Method | URL | Body/Params | คำอธิบาย |
|--------|-----|-------------|-----------|
| GET | `/sonoff/status/` | `?entity_id=...` | ดูสถานะอุปกรณ์ |
| POST | `/sonoff/toggle/` | `{"entity_id": "..."}` | Toggle เปิด/ปิด |

---

## API v2 (ต้องใช้ JWT Header: `Authorization: Bearer <token>`)

### Token — สาธารณะ (ไม่ต้อง auth)

| Method | URL | Body | คำอธิบาย |
|--------|-----|------|-----------|
| POST | `/v2/token/` | `username`, `password` | รับ JWT access + refresh token |
| POST | `/v2/token/refresh/` | `refresh` | รีเฟรช access token |
| POST | `/v2/auth/login/` | `username`, `password` | Login ผ่าน Django User → JWT |
| POST | `/v2/auth/verify_token/` | — | ตรวจสอบความถูกต้องของ token |

### User Profile — `/v2/data/`

| Method | URL | คำอธิบาย |
|--------|-----|-----------|
| GET | `/v2/data/` | รายการ UserProfile ทั้งหมด |
| POST | `/v2/data/` | สร้าง UserProfile ใหม่ |
| GET | `/v2/data/{userId}/` | ดู UserProfile ตาม userId |
| PUT/PATCH | `/v2/data/{userId}/` | แก้ไข UserProfile |
| DELETE | `/v2/data/{userId}/` | ลบ UserProfile |

### ข้อมูลนักศึกษา — `/v2/student/`

| Method | URL | Query Params | คำอธิบาย |
|--------|-----|--------------|-----------|
| GET | `/v2/student/` | `?name=` `?surname=` | รายการ / ค้นหาด้วยชื่อหรือนามสกุล |
| GET | `/v2/student/{student_code}/` | — | ข้อมูลนักศึกษาตามรหัส |

### ข้อมูลบุคลากร — `/v2/personnel/`

| Method | URL | Query Params | คำอธิบาย |
|--------|-----|--------------|-----------|
| GET | `/v2/personnel/` | `?name=` `?department=` | รายการ / ค้นหาด้วยชื่อหรือแผนก |
| GET | `/v2/personnel/{staffcitizenid}/` | — | ข้อมูลบุคลากรตามเลขบัตรประชาชน |

### LDAP — `/v2/ldap/`

| Method | URL | Body | คำอธิบาย |
|--------|-----|------|-----------|
| POST | `/v2/ldap/auth_ldap/` | `userLdap`, `passLdap` | ตรวจสอบ AD (JWT protected) |
| POST | `/v2/ldap/auth_and_get_student/` | `userLdap`, `passLdap` | Auth + ข้อมูลนักศึกษา + faculty/program |
| POST | `/v2/ldap/auth_and_get_personnel/` | `userLdap`, `passLdap` | Auth + ข้อมูลบุคลากร + department/position |

### ห้องสมุด — `/v2/library/`

| Method | URL | คำอธิบาย |
|--------|-----|-----------|
| GET | `/v2/library/check_user_walai/{user_ldap}/` | ตรวจสอบสมาชิกห้องสมุด (format ใหม่) |

### MikroTik Hotspot — `/v2/mt/`

| Method | URL | Query Params | คำอธิบาย |
|--------|-----|--------------|-----------|
| GET | `/v2/mt/list-users/` | `?page=` `?page_size=` `?disabled=` | รายชื่อพร้อม pagination และ filter |
| GET | `/v2/mt/enable/{username}/` | — | เปิดใช้งาน user |
| GET | `/v2/mt/disable/{username}/` | — | ปิดใช้งาน user |
| POST | `/v2/mt/reset/{username}/` | — | Reset และ disconnect user |

### IoT — `/v2/iot/`

| Method | URL | Body/Params | คำอธิบาย |
|--------|-----|-------------|-----------|
| GET | `/v2/iot/status/` | `?entity_id=...` | ดูสถานะอุปกรณ์ (คืน attributes ครบ) |
| POST | `/v2/iot/toggle/` | `{"entity_id": "..."}` | Toggle เปิด/ปิด |
| POST | `/v2/iot/schedule/` | `entity_id`, `operation`, `scheduled_time` | ตั้งเวลาเปิด/ปิด |

---

## ReservApp — `/reserv/` (Web, Session-based)

| Method | URL | คำอธิบาย |
|--------|-----|-----------|
| GET/POST | `/reserv/` | หน้าแรก |
| GET/POST | `/reserv/login/` | Login ผ่าน AD + สร้าง session |
| GET | `/reserv/welcome/` | หน้าหลังล็อกอิน |
| GET | `/reserv/rooms/` | รายการห้อง |
| GET | `/reserv/rooms/{room_id}/` | หน้าควบคุมห้อง |
| GET | `/reserv/logout/` | ลบ session |
| GET/POST | `/reserv/lineoa/` | LINE OA integration |

---

## หมายเหตุ

- หน้าแรก `/` คืน HTTP 403 เสมอ (จงใจปิดไว้)
- `/admin/` → Django Admin Panel
- V2 ทุก endpoint ยกเว้น `auth/login/`, `auth/verify_token/`, `token/`, `token/refresh/` ต้องส่ง header `Authorization: Bearer <access_token>`
