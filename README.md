# NPU API Project

REST API Backend สำหรับมหาวิทยาลัยนครปฐม (Nakhon Pathom University)

## สารบัญ

- [ภาพรวมโปรเจกต์](#ภาพรวมโปรเจกต์)
- [เทคโนโลยีที่ใช้](#เทคโนโลยีที่ใช้)
- [โครงสร้างโปรเจกต์](#โครงสร้างโปรเจกต์)
- [การติดตั้งและตั้งค่า](#การติดตั้งและตั้งค่า)
- [สถาปัตยกรรม API](#สถาปัตยกรรม-api)
- [การยืนยันตัวตน (Authentication)](#การยืนยันตัวตน-authentication)
- [โมเดลฐานข้อมูล](#โมเดลฐานข้อมูล)
- [API Endpoints](#api-endpoints)
- [ReservApp — ระบบจองห้อง](#reservapp--ระบบจองห้อง)
- [การเชื่อมต่อบริการภายนอก](#การเชื่อมต่อบริการภายนอก)
- [การ Deploy บน IIS](#การ-deploy-บน-iis)

---

## ภาพรวมโปรเจกต์

แพลตฟอร์ม API หลายฟังก์ชันสำหรับ NPU ประกอบด้วย:

- **การยืนยันตัวตน:** LDAP (Active Directory) + JWT Token
- **ข้อมูลบุคลากรและนักศึกษา:** Query จากฐานข้อมูลมหาวิทยาลัย (read-only)
- **ห้องสมุด Walai:** ตรวจสอบสมาชิกผ่าน API
- **MikroTik Hotspot:** จัดการ user บน RouterOS
- **IoT (Home Assistant/Sonoff):** ควบคุมอุปกรณ์ไฟฟ้าในห้อง
- **ระบบจองห้อง (ReservApp):** Web app พร้อม LINE OA Integration และ Google Sheets backend

---

## เทคโนโลยีที่ใช้

| ส่วน | เทคโนโลยี |
|------|-----------|
| Framework | Django 5.0.7 + Django REST Framework |
| Language | Python 3.12 |
| Database | MySQL (production), SQLite (dev fallback) |
| Authentication | JWT (SimpleJWT) + LDAP3 (NTLM) |
| IoT | Home Assistant REST API |
| Network | librouteros (MikroTik RouterOS API) |
| Storage (Reserv) | Google Sheets via gspread |
| Static Files | WhiteNoise |
| Deployment | IIS + FastCGI (Windows) |

---

## โครงสร้างโปรเจกต์

```
apiproject/
├── apiapp/                        # Django app หลัก — REST API
│   ├── models.py                  # 3 models: UserProfile, StudentsInfo, StaffInfo
│   ├── views.py                   # V1 ViewSets (session-based)
│   ├── views_v2.py                # V2 ViewSets (JWT-based)
│   ├── serializer.py              # V1 Serializers
│   ├── serializers_v2.py          # V2 Serializers (มี computed field: fullname)
│   ├── authentication.py          # JWT mixins: JWTRequiredAuthentication, PublicEndpointAuthentication
│   ├── admin.py                   # Django Admin registrations
│   └── migrations/
├── reservapp/                     # ระบบจองห้อง + LINE OA
│   ├── models.py                  # ว่างเปล่า (ใช้ Google Sheets แทน)
│   ├── views.py                   # View functions + Google Sheets + LDAP integration
│   ├── urls.py                    # URL patterns
│   └── templates/reservapp/       # HTML templates
├── apiproject/
│   ├── settings.py                # Settings หลัก
│   ├── urls.py                    # URL Router รวม
│   ├── middleware.py              # ResponseTimeMiddleware
│   ├── wsgi.py
│   └── asgi.py
├── static/                        # Static files (collectstatic)
├── .env                           # Environment variables (ไม่ commit)
├── web.config                     # IIS FastCGI configuration
├── manage.py
├── CLAUDE.md                      # คำแนะนำสำหรับ Claude Code
└── API_ENDPOINTS.md               # ตารางสรุป endpoints ทั้งหมด
```

---

## การติดตั้งและตั้งค่า

### 1. ติดตั้ง Dependencies

```bash
pip install -r requirements.txt
```

### 2. ตั้งค่า Environment Variables

สร้างไฟล์ `.env` ที่ root ของโปรเจกต์:

```env
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=127.0.0.1,localhost,your-domain.com

DB_ENGINE=django.db.backends.mysql
DB_NAME=api
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=your_db_host
DB_PORT=3306

MIKROTIK_HOST=your_mikrotik_ip
MIKROTIK_USER=your_mikrotik_user
MIKROTIK_PASSWORD=your_mikrotik_password

HA_TOKEN=your_home_assistant_token

WALAI_API_TOKEN=your_walai_token
```

### 3. Migrate และเริ่มระบบ

```bash
# สร้างและ migrate ฐานข้อมูล
python manage.py makemigrations
python manage.py migrate

# สร้าง superuser
python manage.py createsuperuser

# Collect static files (จำเป็นก่อน deploy)
python manage.py collectstatic

# รัน development server
python manage.py runserver
```

---

## สถาปัตยกรรม API

โปรเจกต์นี้มี **2 เวอร์ชัน API คู่ขนาน** ใน `apiapp/`:

### V1 (Legacy)
- Authentication: Session-based (ไม่ต้องใช้ token)
- ViewSets: `views.py`
- Serializers: `serializer.py`
- Routes: `/api/`, `/std-info/`, `/auth-ldap/`, `/staff-info/`, `/walai/`, `/mt/`, `/sonoff/`

### V2 (Modern)
- Authentication: JWT Bearer Token (`Authorization: Bearer <token>`)
- ViewSets: `views_v2.py`
- Serializers: `serializers_v2.py`
- Routes: ทุก endpoint อยู่ภายใต้ prefix `/v2/`
- Token endpoints: `POST /v2/token/` และ `POST /v2/token/refresh/`

---

## การยืนยันตัวตน (Authentication)

### JWT Configuration (`settings.py`)

| ค่า | การตั้งค่า |
|-----|-----------|
| Access Token Lifetime | 365 วัน |
| Refresh Token Lifetime | 395 วัน |
| Algorithm | HS256 |
| Header Type | `Bearer` |
| Rotate Refresh Tokens | เปิดใช้งาน |
| Blacklist After Rotation | เปิดใช้งาน |

### Authentication Mixins (`apiapp/authentication.py`)

| Mixin | ใช้กับ | การทำงาน |
|-------|--------|----------|
| `JWTV2Authentication` | V2 ViewSets ที่ต้องการ auth | ตรวจสอบ Bearer token, บังคับ IsAuthenticated |
| `PublicEndpointAuthentication` | Login/Token endpoints | ข้ามการตรวจสอบ, AllowAny |

### การขอ Token

```http
POST /v2/token/
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

Response:
```json
{
  "refresh": "eyJ...",
  "access": "eyJ..."
}
```

### การใช้ Token

```http
GET /v2/student/
Authorization: Bearer eyJ...
```

---

## โมเดลฐานข้อมูล

### UserProfile — Django-managed (เขียนได้)

```python
- userId       CharField(100, unique=True)   # เช่น LINE userId หรือ student code
- userLdap     CharField(100)                # LDAP username
- user_type    CharField(100)                # เช่น "นักศึกษา", "บุคลากรภายในมหาวิทยาลัย"
```

Bridge ระหว่าง external auth (LDAP, LINE) กับ Django User system

---

### StudentsInfo — read-only (`managed=False`)

Maps to existing DB table: `students_info`

```python
- student_code      CharField(50, PK)
- prefix_name       CharField
- student_name      CharField
- student_surname   CharField
- level_id          IntegerField
- level_name        CharField
- program_name      CharField
- degree_name       CharField
- faculty_name      CharField
- apassword         CharField
```

> **หมายเหตุ:** โมเดลนี้ sync มาจากฐานข้อมูลมหาวิทยาลัย ไม่รองรับการเขียน

---

### StaffInfo — read-only (`managed=False`)

Maps to existing DB table: `staff_info`

```python
- staffid           CharField(50, PK)        # DB column: STAFFID
- staffcitizenid    CharField(13)            # DB column: STAFFCITIZENID
- prefixfullname    CharField                # DB column: PREFIXFULLNAME
- staffname         CharField                # DB column: STAFFNAME
- staffsurname      CharField                # DB column: STAFFSURNAME
- staffbirthdate    DateField                # DB column: STAFFBIRTHDATE
- gendernameth      CharField
- posnameth         CharField
- stftypename       CharField
- substftypename    CharField
- stfstaname        CharField
- departmentname    CharField
```

> **หมายเหตุ:** โมเดลนี้ sync มาจากฐานข้อมูลมหาวิทยาลัย ไม่รองรับการเขียน

---

## API Endpoints

ดูตารางสรุปทั้งหมดได้ที่ [API_ENDPOINTS.md](./API_ENDPOINTS.md)

### V1 API — Session-based (ไม่ต้อง token)

#### User Profile — `/api/`
| Method | URL | คำอธิบาย |
|--------|-----|----------|
| GET | `/api/` | รายการ UserProfile ทั้งหมด |
| POST | `/api/` | สร้าง UserProfile |
| GET | `/api/{userId}/` | ดูตาม userId |
| PUT/PATCH | `/api/{userId}/` | แก้ไข |
| DELETE | `/api/{userId}/` | ลบ |

#### ข้อมูลนักศึกษา — `/std-info/`
| Method | URL | คำอธิบาย |
|--------|-----|----------|
| GET | `/std-info/` | รายการนักศึกษาทั้งหมด |
| GET | `/std-info/{student_code}/` | ข้อมูลตามรหัสนักศึกษา |

#### ข้อมูลบุคลากร — `/staff-info/`
| Method | URL | คำอธิบาย |
|--------|-----|----------|
| GET | `/staff-info/` | รายการบุคลากรทั้งหมด |
| GET | `/staff-info/{staffcitizenid}/` | ข้อมูลตามเลขบัตรประชาชน |

#### LDAP Authentication — `/auth-ldap/`
| Method | URL | Body | คำอธิบาย |
|--------|-----|------|----------|
| POST | `/auth-ldap/auth_ldap/` | `userLdap`, `passLdap` | ตรวจสอบกับ Active Directory |
| POST | `/auth-ldap/auth_and_get_student/` | `userLdap`, `passLdap` | Auth + คืนข้อมูลนักศึกษา |

#### ห้องสมุด Walai — `/walai/`
| Method | URL | คำอธิบาย |
|--------|-----|----------|
| GET | `/walai/check_user_walai/{user_ldap}/` | ตรวจสอบสมาชิกห้องสมุด |

#### MikroTik Hotspot — `/mt/`
| Method | URL | คำอธิบาย |
|--------|-----|----------|
| GET | `/mt/list-users/` | รายชื่อ Hotspot users |
| GET | `/mt/enable/{username}/` | เปิดใช้งาน user |
| GET | `/mt/disable/{username}/` | ปิดใช้งาน user |

#### IoT/Sonoff — `/sonoff/`
| Method | URL | คำอธิบาย |
|--------|-----|----------|
| GET | `/sonoff/status/` | ดูสถานะอุปกรณ์ (`?entity_id=...`) |
| POST | `/sonoff/toggle/` | Toggle เปิด/ปิดอุปกรณ์ |

---

### V2 API — JWT Bearer Token Required

> **Header ทุก request (ยกเว้น token/login):** `Authorization: Bearer <access_token>`

#### Token — สาธารณะ
| Method | URL | คำอธิบาย |
|--------|-----|----------|
| POST | `/v2/token/` | ขอ JWT token (username + password) |
| POST | `/v2/token/refresh/` | รีเฟรช token |
| POST | `/v2/auth/login/` | Login ผ่าน Django User → JWT |
| POST | `/v2/auth/verify_token/` | ตรวจสอบ token (ต้องใช้ header) |

#### User Profile — `/v2/data/` (JWT Required)
| Method | URL | คำอธิบาย |
|--------|-----|----------|
| GET | `/v2/data/` | รายการ UserProfile ทั้งหมด |
| POST | `/v2/data/` | สร้าง UserProfile |
| GET | `/v2/data/{userId}/` | ดูตาม userId |
| PUT/PATCH | `/v2/data/{userId}/` | แก้ไข |
| DELETE | `/v2/data/{userId}/` | ลบ |

#### ข้อมูลนักศึกษา — `/v2/student/` (JWT Required)
| Method | URL | Query Params | คำอธิบาย |
|--------|-----|-------------|----------|
| GET | `/v2/student/` | `?name=` `?surname=` | รายการ / ค้นหา |
| GET | `/v2/student/{student_code}/` | — | ข้อมูลตามรหัส (มี `fullname`) |

#### ข้อมูลบุคลากร — `/v2/personnel/` (JWT Required)
| Method | URL | Query Params | คำอธิบาย |
|--------|-----|-------------|----------|
| GET | `/v2/personnel/` | `?name=` `?department=` | รายการ / ค้นหา |
| GET | `/v2/personnel/{staffcitizenid}/` | — | ข้อมูลตามเลขบัตร (มี `fullname`) |

#### LDAP — `/v2/ldap/` (JWT Required)
| Method | URL | Body | คำอธิบาย |
|--------|-----|------|----------|
| POST | `/v2/ldap/auth_ldap/` | `userLdap`, `passLdap` | ตรวจสอบ AD |
| POST | `/v2/ldap/auth_and_get_student/` | `userLdap`, `passLdap` | Auth + ข้อมูลนักศึกษา + faculty/program |
| POST | `/v2/ldap/auth_and_get_personnel/` | `userLdap`, `passLdap` | Auth + ข้อมูลบุคลากร + department/position |

#### ห้องสมุด — `/v2/library/` (JWT Required)
| Method | URL | คำอธิบาย |
|--------|-----|----------|
| GET | `/v2/library/check_user_walai/{user_ldap}/` | ตรวจสอบสมาชิก (response format V2) |

#### MikroTik Hotspot — `/v2/mt/` (JWT Required)
| Method | URL | Query Params | คำอธิบาย |
|--------|-----|-------------|----------|
| GET | `/v2/mt/list-users/` | `?page=` `?page_size=` `?disabled=` | รายชื่อพร้อม pagination |
| GET | `/v2/mt/enable/{username}/` | — | เปิดใช้งาน user |
| GET | `/v2/mt/disable/{username}/` | — | ปิดใช้งาน user |
| POST | `/v2/mt/reset/{username}/` | — | Reset quota + disconnect (V2 only) |

#### IoT — `/v2/iot/` (JWT Required)
| Method | URL | คำอธิบาย |
|--------|-----|----------|
| GET | `/v2/iot/status/` | ดูสถานะอุปกรณ์ (`?entity_id=...`) คืน attributes ครบ |
| POST | `/v2/iot/toggle/` | Toggle เปิด/ปิด |
| POST | `/v2/iot/schedule/` | ตั้งเวลาเปิด/ปิด (V2 only) |

---

### URL พิเศษ

| URL | คำอธิบาย |
|-----|----------|
| `/` | คืน HTTP 403 เสมอ (ปิดจงใจ) |
| `/admin/` | Django Admin Panel |

---

## ReservApp — ระบบจองห้อง

Web application สำหรับจองและควบคุมห้องในห้องสมุด รองรับทั้ง Web browser และ LINE OA

### คุณสมบัติ
- Login ผ่าน LDAP (Active Directory) หรือ LINE
- แสดงข้อมูลผู้ใช้จาก API (นักศึกษา/บุคลากร)
- ตรวจสอบสมาชิกห้องสมุด Walai
- ควบคุมอุปกรณ์ในห้อง (ไฟ, แอร์, โปรเจกเตอร์, ทีวี) ผ่าน Home Assistant
- **ข้อมูลการจองเก็บใน Google Sheets** (ไม่ใช้ Django models)
- ตรวจสอบสิทธิ์เข้าห้องตามช่วงเวลาที่จอง

### Routes — `/reserv/`
| Method | URL | คำอธิบาย |
|--------|-----|----------|
| GET/POST | `/reserv/` | หน้าแรก |
| GET | `/reserv/lineoa/` | LINE OA entry point |
| GET/POST | `/reserv/login/` | Login ผ่าน LDAP |
| GET | `/reserv/welcome/` | หน้าหลังล็อกอิน + ข้อมูลผู้ใช้ |
| GET | `/reserv/rooms/` | รายการห้องทั้งหมด |
| GET | `/reserv/rooms/{room_id}/` | ควบคุมอุปกรณ์ในห้อง |
| GET | `/reserv/logout/` | ลบ session + logout |

### ห้องที่รองรับ

| room_id | ชื่อห้อง | อุปกรณ์ |
|---------|---------|--------|
| 1 | ห้อง Mini Theater | ประตู, ระบบแสงสว่าง, ระบบเสียง, โปรเจ็คเตอร์, เครื่องปรับอากาศ |
| 2 | โซน Netflix | ทีวีและปลั๊ก |
| 3 | ห้อง Journal | ทีวีและปลั๊ก |

### Google Sheets Backend
- แต่ละห้องมี Spreadsheet แยก (URL hardcoded ใน `reservapp/views.py`)
- ระบบอ่าน worksheet แรก (`get_worksheet(0)`) เพื่อตรวจสอบข้อมูลการจอง
- ตรวจสอบ: `userId` + วันที่ปัจจุบัน + ช่วงเวลา `เวลาเข้า`/`เวลาออก`
- Service account: `control-room-440116-eda428ec17d3.json`

---

## การเชื่อมต่อบริการภายนอก

| บริการ | Protocol | วัตถุประสงค์ | Host |
|--------|----------|------------|------|
| Active Directory | LDAP3 NTLM | ยืนยันตัวตน NPU.local | `10.0.3.12` |
| MikroTik RouterOS | API (librouteros) | จัดการ Hotspot users | `202.29.55.180` |
| Home Assistant | REST API | ควบคุม Sonoff/IoT | `202.29.55.30:8123` |
| Walai Library | REST API | ตรวจสอบสมาชิกห้องสมุด | `opacapi.npu.ac.th` |
| Google Sheets | gspread | เก็บข้อมูลการจองห้อง | Google Cloud |

---

## Middleware

### ResponseTimeMiddleware (`apiproject/middleware.py`)
วัดเวลาประมวลผลของแต่ละ request และ:
- เพิ่ม response header: `X-Process-Time`
- Log ไปที่ Django logger
> **หมายเหตุ:** ปัจจุบัน comment ออกใน settings.py

---

## การ Deploy บน IIS

ใช้ FastCGI ผ่าน `web.config` ที่ root ของโปรเจกต์

### ขั้นตอนหลัก
1. ติดตั้ง Python 3.12 และ packages
2. Copy โปรเจกต์ไปยัง server
3. ตั้งค่า `.env` สำหรับ production
4. รัน `python manage.py collectstatic`
5. ตั้งค่า IIS Application Pool และ FastCGI handler
6. ชี้ `web.config` ไปยัง `wfastcgi.py`

### CORS Allowed Origins (production)
```
https://rdb.npu.ac.th
https://arc.npu.ac.th
https://a.npu.world
https://202.29.55.213
https://edoc-npu.pages.dev
http://localhost:3000
http://202.29.55.98
```
(รวมถึง regex pattern สำหรับ `script.google.com`)

---

## หมายเหตุ

- **V1** เหมาะสำหรับ integration เดิมที่ไม่ต้องการ JWT
- **V2** แนะนำสำหรับ integration ใหม่ทุกรายการ
- `StudentsInfo` และ `StaffInfo` เป็น read-only models ที่ map ตรงไปยังตารางฐานข้อมูลมหาวิทยาลัย
- Browsable API ของ DRF เปิดใช้งานอยู่ — สามารถทดสอบ V1 endpoints ได้ผ่าน browser
- Token V2 มีอายุ 365 วัน เหมาะสำหรับ mobile/app integrations ที่ไม่บ่อยต้อง re-auth
