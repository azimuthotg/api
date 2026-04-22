# ReservApp — ระบบจองห้องและควบคุมอุปกรณ์

เอกสารอธิบาย Flow, Logic และสถาปัตยกรรมของ `reservapp/` สำหรับการเรียนรู้

---

## สารบัญ

1. [ภาพรวม](#1-ภาพรวม)
2. [โครงสร้างไฟล์](#2-โครงสร้างไฟล์)
3. [Flow การทำงานหลัก](#3-flow-การทำงานหลัก)
4. [อธิบายแต่ละ View Function](#4-อธิบายแต่ละ-view-function)
5. [Logic การตรวจสอบสิทธิ์ห้อง](#5-logic-การตรวจสอบสิทธิ์ห้อง)
6. [การเชื่อมต่อบริการภายนอก](#6-การเชื่อมต่อบริการภายนอก)
7. [ข้อมูล Hardcoded](#7-ข้อมูล-hardcoded)
8. [Session Management](#8-session-management)
9. [URL Routing](#9-url-routing)
10. [Templates](#10-templates)
11. [Diagram ภาพรวมระบบ](#11-diagram-ภาพรวมระบบ)

---

## 1. ภาพรวม

ReservApp เป็น Web Application ที่ทำงานร่วมกับ **LINE OA (Official Account)** ของมหาวิทยาลัย

### หน้าที่หลัก
- รับ identity ของผู้ใช้จาก LINE (userId, displayName, pictureUrl)
- ตรวจสอบว่าผู้ใช้คนนี้เคยผูก LDAP account ไว้แล้วหรือยัง
- แสดงข้อมูลส่วนตัว (นักศึกษา หรือ บุคลากร) และสถานะสมาชิกห้องสมุด
- ให้ผู้ใช้เข้าควบคุมห้องที่จองไว้ **ตามช่วงเวลาที่จองเท่านั้น**
- ควบคุมอุปกรณ์ในห้อง (ไฟ, แอร์, โปรเจกเตอร์, ทีวี) ผ่าน Home Assistant

### สิ่งที่ระบบนี้ "ไม่ได้ทำ"
- **ไม่รับจองห้อง** — การจองทำจากระบบอื่น (เช่น Google Forms) แล้วบันทึกลง Google Sheets
- **ไม่เก็บข้อมูลใน Django database** — ใช้ Google Sheets เป็น backend แทน
- **ไม่ใช้ JWT** — ใช้ Django Session ในการจดจำผู้ใช้

---

## 2. โครงสร้างไฟล์

```
reservapp/
├── views.py                        # Logic หลักทั้งหมด
├── urls.py                         # URL mapping
├── models.py                       # ว่างเปล่า (ไม่ใช้ DB)
├── admin.py
├── apps.py
└── templates/
    └── reservapp/
        ├── base.html               # Layout หลัก
        ├── base2.html              # Layout สำรอง
        ├── home.html               # หน้าแรก (รับ POST จาก LINE)
        ├── home_oa.html            # LINE OA entry point
        ├── home_lineliff.html      # LINE LIFF integration
        ├── login.html              # หน้า Login ด้วย LDAP
        ├── welcome.html            # หน้าหลังเข้าสู่ระบบ
        ├── room_list.html          # รายการห้องทั้งหมด
        ├── room_control.html       # หน้าควบคุมอุปกรณ์ในห้อง
        ├── error_access.html       # หน้าปฏิเสธการเข้าห้อง
        └── success.html            # หน้าสำเร็จ
```

---

## 3. Flow การทำงานหลัก

### 3.1 Path A — เข้าผ่าน LINE OA (ปกติ)

```
[LINE Mini App / LIFF]
        │
        │  POST: userId, displayName, pictureUrl, page
        ▼
   /reserv/  →  home()
        │  บันทึกลง Session
        │  redirect
        ▼
   /reserv/welcome/  →  welcome()
        │
        ├── check_user_in_api(userId)
        │       └── GET /api/{userId}          ← ตรวจว่าผูก LDAP ไว้แล้วหรือยัง
        │               │
        │               ├── user_type = "นักศึกษา"
        │               │       └── GET /std-info/{userLdap}/
        │               │
        │               └── user_type = "บุคลากร"
        │                       └── GET /staff-info/{userLdap}/
        │
        ├── check_walai_membership(userLdap)
        │       └── GET /walai/check_user_walai/{userLdap}
        │
        ├── พบข้อมูล → แสดง welcome.html
        └── ไม่พบข้อมูล → redirect ไป /reserv/login/
```

### 3.2 Path B — ยังไม่เคยผูก LDAP (ครั้งแรก)

```
   /reserv/login/  →  login()
        │
        │  POST: userLdap, passLdap, user_type
        ▼
   check_user_in_ad(userLdap, passLdap)
        │  เชื่อมต่อ LDAP 10.0.3.12 ด้วย NTLM
        │
        ├── สำเร็จ → POST /api/ { userId, userLdap, user_type }
        │               └── บันทึก UserProfile ในฐานข้อมูล
        │                   (ผูก LINE userId ↔ LDAP username)
        │                   → แสดง home.html (สำเร็จ)
        │
        └── ล้มเหลว → แสดง login.html + error_message
```

### 3.3 Path C — เข้าควบคุมห้อง

```
   /reserv/rooms/  →  room_list_view()
        │  แสดงรายการ 3 ห้อง
        ▼
   /reserv/rooms/{room_id}/?userId=xxx  →  room_control_view()
        │
        ├── 1. ตรวจ room_id → หา sheet_url
        ├── 2. เชื่อม Google Sheets API (service account)
        ├── 3. ดึง records จาก Sheet
        │       กรอง: UserID == userId AND วันที่ == วันนี้
        │
        ├── 4. check_access()
        │       เวลาเข้า ≤ เวลาปัจจุบัน ≤ เวลาออก ?
        │
        ├── ✅ อนุญาต → room_control.html
        │       (แสดง devices, ชื่อ, เวลาจอง)
        │
        └── ❌ ปฏิเสธ → error_access.html (HTTP 403)
```

---

## 4. อธิบายแต่ละ View Function

### `home(request)` — `/reserv/`

**วัตถุประสงค์:** รับ identity จาก LINE และเก็บลง Session

```python
# GET  → แสดงหน้า home.html เปล่าๆ
# POST → รับค่าจาก LINE แล้ว redirect ไป welcome

request.session['userId']      = userId       # LINE User ID (เช่น Uxxxxxxxx)
request.session['displayName'] = displayName  # ชื่อใน LINE
request.session['pictureUrl']  = pictureUrl   # URL รูปโปรไฟล์ LINE
request.session['page']        = page         # หน้าที่ต้องการ (ถ้ามี)
```

**ข้อสังเกต:** ไม่มีการ validate ข้อมูลใดๆ ในขั้นตอนนี้ ตรวจสอบจริงที่ `welcome()`

---

### `login(request)` — `/reserv/login/`

**วัตถุประสงค์:** ผูก LINE userId เข้ากับ LDAP account (ทำครั้งเดียว)

```
Input:
  userLdap   = รหัสนักศึกษา หรือ username พนักงาน
  passLdap   = รหัสผ่าน AD
  user_type  = "นักศึกษา" หรือ "บุคลากรภายในมหาวิทยาลัย"

Process:
  1. check_user_in_ad()  → ตรวจสอบกับ Active Directory
  2. requests.post(api_url, json=data)  → บันทึก UserProfile

Output:
  สำเร็จ  → home.html (แจ้งลงทะเบียนแล้ว)
  ล้มเหลว → login.html + error_message
```

---

### `check_user_in_ad(userLdap, passLdap)` — Internal

**วัตถุประสงค์:** ตรวจสอบ username/password กับ Active Directory ของมหาวิทยาลัย

```python
Server: 10.0.3.12
Domain: NPU.local
Protocol: LDAP3 with NTLM authentication

# ถ้าสำเร็จ ดึงข้อมูล:
ldap_info = {
    'displayName': 'ชื่อ-นามสกุล',
    'email': 'user@npu.ac.th'
}

return (True, ldap_info)   # สำเร็จ
return (False, None)       # ล้มเหลว
```

---

### `welcome(request)` — `/reserv/welcome/`

**วัตถุประสงค์:** หน้าหลักหลัง login แสดงข้อมูลผู้ใช้ครบถ้วน

```python
# ตรวจ session ก่อน — ถ้าไม่มี userId → redirect login

userId = request.session['userId']

# เรียก 2 ฟังก์ชัน:
user_exists, user_ldap, user_info, user_type, is_walai_member = check_user_in_api(userId)

# ส่งไป template:
{
  'userId': userId,
  'displayName': displayName,     # จาก LINE
  'pictureUrl': pictureUrl,       # จาก LINE
  'userLdap': user_ldap,          # จาก DB
  'user_info': user_info,         # student_info หรือ staff_info
  'user_type': user_type,         # ประเภทผู้ใช้
  'is_walai_member': True/False   # สมาชิกห้องสมุด
}
```

---

### `check_user_in_api(userId)` — Internal

**วัตถุประสงค์:** ดึงข้อมูลผู้ใช้ทั้งหมดโดยใช้ userId เป็นจุดเริ่มต้น

```
GET https://api.npu.ac.th/api/{userId}
    └── ได้ user_type และ userLdap

    ├── user_type = "นักศึกษา"
    │       GET /std-info/{userLdap}/
    │       return (True, userLdap, student_info, user_type, is_walai_member)
    │
    └── user_type = "บุคลากรภายในมหาวิทยาลัย"
            GET /staff-info/{userLdap}/
            return (True, userLdap, staff_info, user_type, is_walai_member)

ล้มเหลว → return (False, None, None, None, None)
```

---

### `check_walai_membership(user_ldap)` — Internal

**วัตถุประสงค์:** ตรวจสอบว่าเป็นสมาชิกห้องสมุด Walai หรือไม่

```
GET https://api.npu.ac.th/walai/check_user_walai/{user_ldap}
Headers: { token: WALAI_API_TOKEN }

Response แบบ list  → len(data) > 0  = เป็นสมาชิก
Response แบบ dict  → data['is_member']

return True   # เป็นสมาชิก
return False  # ไม่ใช่สมาชิก / เรียก API ไม่สำเร็จ
```

---

### `room_control_view(request, room_id)` — `/reserv/rooms/{room_id}/`

**วัตถุประสงค์:** ตรวจสอบสิทธิ์และแสดงหน้าควบคุมอุปกรณ์

```python
# ขั้นตอนการทำงาน:

# 1. รับ userId จาก Query String
user_id = request.GET.get('userId')  # ?userId=Uxxxxxxxx

# 2. หา Google Sheet ของห้องนี้
sheet_url = sheet_urls[str(room_id)]

# 3. เชื่อม Google Sheets ด้วย Service Account
creds = Credentials.from_service_account_file('...json', scopes=scope)
worksheet = client.open_by_url(sheet_url).get_worksheet(0)

# 4. ดึง records ที่ตรงเงื่อนไข
records = worksheet.get_all_records()
user_data = [row for row in records
             if row['UserID'] == user_id
             and row['วันที่'] == datetime.now().strftime("%Y-%m-%d")]

# 5. ตรวจสอบช่วงเวลา
check_in  = datetime.strptime(record['เวลาเข้า'], "%H:%M").time()
check_out = datetime.strptime(record['เวลาออก'], "%H:%M").time()
access = check_in <= datetime.now().time() <= check_out

# 6. ตัดสินใจ
if access:
    return render('room_control.html', devices=ROOM_DEVICES[room_id])
else:
    return render('error_access.html', status=403)
```

---

## 5. Logic การตรวจสอบสิทธิ์ห้อง

ผู้ใช้จะเข้าห้องได้ก็ต่อเมื่อผ่านเงื่อนไข **ทั้ง 3 ข้อ** พร้อมกัน:

```
เงื่อนไขที่ 1: มี room_id นี้อยู่ใน sheet_urls
เงื่อนไขที่ 2: มีแถวใน Google Sheet ที่
               - UserID  ตรงกับ userId ที่ส่งมา
               - วันที่  ตรงกับวันนี้ (YYYY-MM-DD)
เงื่อนไขที่ 3: เวลาปัจจุบัน อยู่ระหว่าง เวลาเข้า ถึง เวลาออก
```

**ตัวอย่าง Google Sheet:**

| UserID | displayname | วันที่ | เวลาเข้า | เวลาออก |
|--------|------------|--------|----------|---------|
| Uabc123 | สมชาย ใจดี | 2026-04-22 | 09:00 | 11:00 |
| Uabc123 | สมชาย ใจดี | 2026-04-22 | 13:00 | 15:00 |
| Uxyz456 | สมหญิง รักดี | 2026-04-22 | 10:00 | 12:00 |

ถ้าตอนนี้คือ **10:30** และ userId = `Uabc123` → **ไม่ผ่าน** (อยู่นอกช่วง 09:00-11:00 ก็ได้ขึ้นอยู่กับเวลาจริง)
ถ้าตอนนี้คือ **09:30** → **ผ่าน**

---

## 6. การเชื่อมต่อบริการภายนอก

### 6.1 Active Directory (LDAP)

```python
Library: ldap3
Server:  10.0.3.12
Domain:  NPU.local
Auth:    NTLM (username/password)

# เรียกใช้ใน:
- check_user_in_ad()  ← ตรวจสอบตอน login
```

### 6.2 Django REST API (ตัวเอง)

```python
# reservapp เรียก API ของตัวเองใน apiapp!

GET  https://api.npu.ac.th/api/{userId}          ← ดึง UserProfile
POST https://api.npu.ac.th/api/                   ← สร้าง UserProfile
GET  https://api.npu.ac.th/std-info/{userLdap}/   ← ข้อมูลนักศึกษา
GET  https://api.npu.ac.th/staff-info/{userLdap}  ← ข้อมูลบุคลากร
GET  https://api.npu.ac.th/walai/check_user_walai/{userLdap}  ← สมาชิกห้องสมุด
```

> **สังเกต:** reservapp ไม่ได้ import models ของ apiapp โดยตรง แต่เรียกผ่าน HTTP แทน

### 6.3 Google Sheets

```python
Library: gspread + google-auth
Auth:    Service Account JSON
         (control-room-440116-eda428ec17d3.json)
Scopes:  spreadsheets + drive

# แต่ละห้องมี Spreadsheet แยก:
room 1 → sheet_urls["1"] → Google Sheets สำหรับ Mini Theater
room 2 → sheet_urls["2"] → Google Sheets สำหรับ Netflix Zone
room 3 → sheet_urls["3"] → Google Sheets สำหรับ Journal Room
```

### 6.4 Home Assistant (IoT)

```
ระบบควบคุมอุปกรณ์ไม่ได้เรียกจาก views.py โดยตรง
Frontend (room_control.html) เรียก Home Assistant API เอง
โดยใช้ entity_id ที่ส่งมาจาก views.py
```

---

## 7. ข้อมูล Hardcoded

ข้อมูลเหล่านี้ถูกกำหนดตายตัวใน `views.py`:

### ชื่อห้อง
```python
ROOM_NAMES = {
    1: "ห้อง Mini Theater",
    2: "โซน Netflix",
    3: "ห้อง Journal"
}
```

### อุปกรณ์ในแต่ละห้อง
```python
ROOM_DEVICES = {
    1: [
        {"name": "ประตู",              "entity_id": "switch.sonoff_1001f20182"},
        {"name": "ระบบแสงสว่าง",       "entity_id": "switch.sonoff_1002115f1a"},
        {"name": "ระบบเสียง",          "entity_id": "switch.sonoff_10021888d9_1"},
        {"name": "โปรเจ็คเตอร์",       "entity_id": "switch.sonoff_1000bff56b"},
        {"name": "เครื่องปรับอากาศ",   "entity_id": "switch.sonoff_100211915b"},
    ],
    2: [{"name": "ทีวีและปลั๊ก", "entity_id": "switch.sonoff_1001f579cb"}],
    3: [{"name": "ทีวีและปลั๊ก", "entity_id": "switch.sonoff_10021861bd_1"}]
}
```

### Google Sheet URLs
```python
sheet_urls = {
    "1": "https://docs.google.com/spreadsheets/d/1LnhtWElm50PdQ.../",
    "2": "https://docs.google.com/spreadsheets/d/1uluAqFI8-fR7Z.../",
    "3": "https://docs.google.com/spreadsheets/d/1clLVM7zPoqHPD.../"
}
```

> **ถ้าต้องการเพิ่มห้อง:** เพิ่ม entry ใน `ROOM_NAMES`, `ROOM_DEVICES`, และ `sheet_urls` พร้อมสร้าง Google Sheet ใหม่

---

## 8. Session Management

ReservApp ใช้ **Django Session** เพื่อจดจำผู้ใช้:

| Key | ค่า | เซ็ตที่ | ใช้ที่ |
|-----|-----|--------|-------|
| `userId` | LINE User ID (Uxxxxxxxx) | `home()` | `welcome()`, `login()` |
| `displayName` | ชื่อใน LINE | `home()` | `welcome()` |
| `pictureUrl` | URL รูป LINE | `home()` | `welcome()` |
| `page` | หน้าที่ต้องการ | `home()` | `welcome()` |

### Session หมดอายุเมื่อ:
- เรียก `logout()` → `del request.session['userId']`
- Django session หมดอายุตามค่า `SESSION_COOKIE_AGE` ใน settings.py

> **หมายเหตุ:** `room_control_view()` ไม่ใช้ session — ใช้ `?userId=` จาก Query String แทน เพราะ URL นี้ถูกส่งจาก LINE โดยตรง

---

## 9. URL Routing

กำหนดใน `reservapp/urls.py` และ include ใน `apiproject/urls.py` ด้วย prefix `/reserv/`

```python
urlpatterns = [
    path('',                home,              name='home'),
    path('lineoa/',         line_oa_home,      name='line_oa_home'),
    path('login/',          login,             name='login'),
    path('welcome/',        welcome,           name='welcome'),
    path('logout/',         logout,            name='logout'),
    path('rooms/',          room_list_view,    name='room_list'),
    path('rooms/<int:room_id>/', room_control_view, name='room_control'),
]
```

---

## 10. Templates

### `home.html`
- รับ POST จาก LINE (userId, displayName, pictureUrl)
- หรือแสดงหน้า landing page

### `login.html`
- ฟอร์ม: `userLdap`, `passLdap`, `user_type` (radio/select)
- แสดง `error_message` ถ้า LDAP ล้มเหลว

### `welcome.html`
- แสดงข้อมูลผู้ใช้: รูปโปรไฟล์, ชื่อ, ประเภท, คณะ/สาขา
- แสดง badge สมาชิกห้องสมุด Walai
- มีปุ่มไปหน้ารายการห้อง

### `room_list.html`
- แสดงการ์ด 3 ห้อง พร้อมลิงก์ไปหน้า `room_control`

### `room_control.html`
- แสดงชื่อห้อง, ชื่อผู้จอง, เวลาเข้า-ออก
- แสดง toggle button สำหรับแต่ละอุปกรณ์
- JavaScript เรียก Home Assistant API ด้วย entity_id ของแต่ละอุปกรณ์

### `error_access.html`
- แสดงข้อความ "ไม่อยู่ในช่วงเวลาที่ท่านได้ทำการจองไว้"
- HTTP Status 403

---

## 11. Diagram ภาพรวมระบบ

```
┌─────────────────────────────────────────────────────────────┐
│                        LINE OA / LIFF                       │
│          ส่ง userId, displayName, pictureUrl                │
└───────────────────────────┬─────────────────────────────────┘
                            │ POST
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    /reserv/  (home)                         │
│                   บันทึก Session                            │
└───────────────────────────┬─────────────────────────────────┘
                            │ redirect
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  /reserv/welcome/                           │
│                                                             │
│   ┌─────────────────┐     ┌──────────────────────────────┐  │
│   │ check_user_in_  │     │  check_walai_membership()    │  │
│   │    api(userId)  │     │  GET /walai/check_user_walai │  │
│   │                 │     └──────────────────────────────┘  │
│   │ GET /api/{id}   │                                       │
│   │    ├─ นักศึกษา  │→ GET /std-info/{ldap}/               │
│   │    └─ บุคลากร   │→ GET /staff-info/{ldap}/             │
│   └─────────────────┘                                       │
│                                                             │
│   [ไม่พบข้อมูล] → redirect /reserv/login/                  │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   /reserv/rooms/                            │
│              แสดงรายการ 3 ห้อง                              │
└───────────────────────────┬─────────────────────────────────┘
                            │ เลือกห้อง
                            ▼
┌─────────────────────────────────────────────────────────────┐
│         /reserv/rooms/{room_id}/?userId=Uxxxxxxxx           │
│                                                             │
│   Google Sheets API                                         │
│   ┌──────────────────────────────────────────────────────┐  │
│   │  worksheet.get_all_records()                         │  │
│   │  กรอง: UserID == userId AND วันที่ == วันนี้         │  │
│   │  check: เวลาเข้า ≤ ตอนนี้ ≤ เวลาออก                 │  │
│   └──────────────────────────────────────────────────────┘  │
│                                                             │
│   ✅ ผ่าน  →  room_control.html                             │
│              (devices list + toggle buttons)                │
│                                                             │
│   ❌ ไม่ผ่าน → error_access.html (HTTP 403)                │
└───────────────────────────┬─────────────────────────────────┘
                            │ Toggle อุปกรณ์
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Home Assistant (202.29.55.30:8123)             │
│         POST /api/services/switch/turn_on|turn_off          │
│              entity_id: switch.sonoff_xxxxxxxx              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  /reserv/login/  (LDAP Path)                │
│                                                             │
│   POST userLdap + passLdap + user_type                      │
│        │                                                    │
│        ▼                                                    │
│   LDAP 10.0.3.12 (NPU.local) NTLM Auth                     │
│        │                                                    │
│        ├── สำเร็จ → POST /api/ { userId, userLdap, type }  │
│        │           บันทึก UserProfile → home.html          │
│        │                                                    │
│        └── ล้มเหลว → login.html + error                    │
└─────────────────────────────────────────────────────────────┘
```

---

## สรุปสิ่งสำคัญที่ควรจำ

| ประเด็น | รายละเอียด |
|---------|-----------|
| **userId คือ LINE User ID** | เป็น key หลักทั้งระบบ (เช่น `Uabc123456`) |
| **UserProfile = สะพานเชื่อม** | ผูก LINE userId ↔ LDAP username ไว้ใน DB |
| **Google Sheets = Database** | ข้อมูลการจองห้องไม่ได้อยู่ใน Django |
| **reservapp เรียก apiapp** | ผ่าน HTTP request ไม่ใช่ import โดยตรง |
| **Session ≠ JWT** | ระบบนี้ใช้ Django Session ไม่ใช่ Bearer Token |
| **การควบคุมอุปกรณ์** | ทำจาก Frontend JS ไปยัง Home Assistant โดยตรง |
| **เพิ่มห้องใหม่** | ต้องแก้ `ROOM_NAMES`, `ROOM_DEVICES`, `sheet_urls` |
