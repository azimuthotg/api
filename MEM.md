# MEM — apiproject (NPU API Backend)

คลังความรู้เฉพาะโปรเจกต์นี้ (ปัญหา/หมายเหตุ/การตัดสินใจ + changelog)
ทะเบียน "งานที่ต้องทำ" อยู่ในบล็อก `<!-- PROJECT-STATUS -->` ด้านบนของ CLAUDE.md — ไฟล์นี้ไว้เก็บ "ความรู้" เท่านั้น

## ปัญหา & วิธีแก้

### 2026-07-23 — ถอดฟิลด์ออกจาก endpoint ที่ traceon ใช้ → ประตูเปิดไม่ได้ ทั้งที่ log เขียว 100%
ถอด `staffbirthdate` + `gendernameth` ออกจาก serializer เส้นถามตรง (`/staff-info/`, `/v2/staff/`) deploy prod แล้ว
**ทีมประตูแจ้งภายในไม่กี่นาทีว่าเปิดไม่ได้** — rollback แล้วกลับมาปกติทันที = traceon ใช้ 1 ใน 2 ฟิลด์นี้จริง
**สิ่งที่ทำให้วินิจฉัยผิดตอนแรก:** ไล่ log หลัง deploy แล้วเห็น `StaffInfoViewSetV2.retrieve` ตอบ **200 ทุกครั้ง** จึงสรุปว่าไม่พัง
แล้วไปโทษ 404 ของฝั่งนักศึกษาที่บังเอิญพุ่งขึ้นพร้อมกัน (ซึ่งเป็นคนละเรื่อง — 404 เกิดก่อนขั้นตอน serialize)
**กฎที่ได้ (สำคัญกว่าตัวเคส):**
1. **HTTP 200 ไม่ใช่หลักฐานว่าผู้เรียกยังทำงานได้** — การถอดฟิลด์ทำให้ผู้เรียกพัง *ฝั่งเขา* API ยังตอบ 200 เสมอ
   `api_access_log` มองไม่เห็นความพังประเภทนี้เลย ต้องมีคนทดสอบหน้างานจริงตอน deploy เท่านั้น
2. **rollback.ps1 ย้อนแค่เครื่อง prod — commit ยังอยู่บน origin/main** ถ้าไม่ `git revert` + push ด้วย
   `deploy.ps1` ครั้งถัดไป (แม้จะ deploy งานอื่นที่ไม่เกี่ยวกัน) จะดึงของพังกลับขึ้นไปเอง · รอบนี้ revert `edf1b06` → `7cd9b74`
3. ก่อนถอดฟิลด์จาก endpoint ที่มีผู้เรียกที่ไม่มี source ให้ตรวจ → **ถามเจ้าของระบบก่อนเสมอ** การใช้ log ยืนยัน
   ได้แค่ "ใครเรียก" ไม่ได้บอก "เขาอ่านฟิลด์ไหน"

### 2026-07-23 — `managed=False` **ไม่ได้** กันการเขียน: `/std-info/` เปิดให้ลบข้อมูลจริงได้
เข้าใจกันมาตลอดว่า `StudentsInfo`/`StaffInfo` เป็น read-only เพราะ `Meta.managed = False`
**ผิด** — `managed=False` บอกแค่ว่า Django จะไม่สร้าง/แก้ตารางตอน migrate เท่านั้น **ORM ยัง INSERT/UPDATE/DELETE ได้ตามปกติ**
ประกอบกับ ViewSet เป็น `viewsets.ModelViewSet` (ไม่ใช่ ReadOnly) และ v1 ไม่มี auth เลย → `DELETE https://api.npu.ac.th/std-info/{รหัส}/` จากใครก็ได้ = ลบแถวจริงในฐานข้อมูลมหาวิทยาลัย
ซ้ำร้าย DB user `admin_e` มีสิทธิ์ `INSERT, UPDATE, DELETE, DROP, SUPER ... WITH GRANT OPTION` บน `*.*` และ `BrowsableAPIRenderer` เปิดอยู่ (คอมเมนต์ในโค้ดเขียนว่า "ปิดบรรทัดนี้" แต่ไม่ได้คอมเมนต์ออกจริง) → เปิด URL ในเบราว์เซอร์ได้ฟอร์ม HTML พร้อมปุ่ม DELETE ให้กด
**แก้:** ทั้ง 4 ViewSet (student/staff × v1/v2) เป็น `viewsets.ReadOnlyModelViewSet` + ปิด BrowsableAPIRenderer จริง
**กฎที่ได้:** อย่าใช้ `managed=False` เป็นเหตุผลว่า endpoint ปลอดภัย — ต้องปิดที่ชั้น ViewSet เสมอ

### 2026-07-23 — `fields = '__all__'` ทำรหัสผ่านนักศึกษารั่วออก API
`students_info.apassword` เก็บ**รหัสผ่าน plaintext** (10,789 แถวมีค่าครบ, distinct 5,032, 7,484 แถวยาว 4 ตัวอักษร = ไม่ใช่ hash แน่นอน) sync มาจาก Oracle `AVSREG.VIEWSYSSTUDENTPASSWORD` โดย aims_project
serializer ทั้ง v1/v2 ใช้ `fields = '__all__'` → รั่วออก **5 ทาง**: `/std-info/` (list+detail), `/v2/student/`, `/auth-ldap/auth_and_get_student/`, `/v2/ldap/auth_and_get_student/` โดยฝั่ง v1 ไม่ต้อง auth เลย
**แก้:** ระบุฟิลด์ตรง ๆ 9 ตัว (v2 เติม `fullname`) — จุดเดียวปิดครบทั้ง 5 ทางเพราะทุกทางใช้ serializer เดียวกัน
**กฎที่ได้:** ห้ามใช้ `'__all__'` กับ model ที่ map ตารางของระบบอื่น — คอลัมน์ที่โผล่มาทีหลังจะหลุดออก API เองโดยไม่มีใครรู้

### 2026-07-10 — push GitHub จาก WSL ไม่ได้
token ใน `/root/.git-credentials` (WSL) หมดอายุ/ถูก revoke — GitHub ตอบ "Invalid username or token"
ทางแก้: push จากฝั่ง Windows (`C:\projects\apiproject`) ที่ใช้ Git Credential Manager แยกกัน แทนการสร้าง PAT ใหม่

### 2026-07-23 — ผู้เรียก v1 แบบไม่มี auth คือ reserv เอง (ไม่ใช่ระบบภายนอกที่คุมไม่ได้)
ความเสี่ยง "`/std-info/`,`/staff-info/` v1 ไม่ต้อง auth" ค้างมานานเพราะไม่รู้ว่าใครใช้ เลยไม่กล้าปิด
วิธีที่ระบุตัวได้ (ทำซ้ำได้): เทียบ log 2 หน้าที่มีอยู่แล้ว — `/monitor/api-usage/` เห็น `LDAPAuthViewSet.auth_ldap` (110.78.83.102) แล้ว `StudentsInfoViewset.retrieve` (10.0.6.253) ยิงติดกันใน 3 วินาที **ด้วยรหัส นศ. เดียวกัน** แล้วเอารหัสนั้นไปเทียบหน้า `/monitor/` เห็นเป็นขั้นตอนผูกบัญชี LINE พอดี → ยืนยันด้วยโค้ด `reserv/booking/views.py` `_fetch_npu_profile()` ที่ `requests.get()` เปล่า ๆ ไม่แนบ header
**ทางแก้ที่เปิดอยู่:** reserv มี `NPU_API_USERNAME/PASSWORD` + cache token อยู่แล้ว (settings.py, ใช้ยิง `/v2/external/*` ทุกวัน) แค่ย้าย `_fetch_npu_profile()` ไป `/v2/student/`,`/v2/staff/` พร้อม Bearer แล้วค่อยปิด v1
**บทเรียน:** IP + ลำดับเวลา + target_user ใน access log ระบุตัวระบบผู้เรียกได้แม้ไม่มี JWT — ไม่ต้องเดาว่า "อาจมีใครใช้อยู่"

## การตัดสินใจ

### 2026-07-23 — ยืนยันว่าถอด `apassword` ได้ปลอดภัย ด้วยข้อมูลจาก api_access_log ไม่ใช่การเดา
endpoint กลุ่มนี้มีระบบอื่นใช้อยู่จริง การถอด field = breaking change ที่อาจพังเงียบ ๆ
วิธีที่ใช้ตัดสินใจ (ทำซ้ำได้ครั้งหน้า):
1. `grep` หา `apassword` ทั่ว `C:\projects` → เจอเฉพาะ aims_project (ตัว**เขียน**ค่าลง DB) กับสคริปต์ทดสอบ — ไม่มีใคร**อ่าน**จาก API
2. อ่านโค้ดผู้บริโภคที่มี source: `reserv/booking/views.py`, `vm/accounts/backends.py` → แกะแค่ชื่อ/คณะ/สาขา
3. query `api_access_log` + `api_access_archive` หาผู้เรียกจริงย้อนหลัง ~5 สัปดาห์ → traceon 18,180 / emoney ~550 / courses 112 / pfss 4 · **ทุก request เป็น GET 100% (22,549 ครั้ง)** จึงยืนยันได้ว่าปิดสิทธิ์เขียนไม่กระทบใคร
4. หลัง deploy query log ซ้ำเฉพาะช่วงหลังโค้ดใหม่ขึ้น → traceon 200 success, fail = 0
**บทเรียน:** `api_access_log` ที่ทำไว้ตั้งแต่ มิ.ย. คือสิ่งที่ทำให้กล้าแก้ endpoint ที่มีคนใช้จริง — ถ้าไม่มี log นี้จะเหลือแค่การเดา

### 2026-07-23 — ปิด `list` แยก commit จากงานอื่น เพื่อให้ถอยเฉพาะส่วนได้
`GET /std-info/` ดึง นศ. ทั้ง 10,789 คนได้ (v1 ไม่ต้อง auth) แต่ log ทั้งหมดมี list แค่ 15 ครั้ง กระจุกใน 4 วัน (19,20,22 มิ.ย. / 4 ก.ค.) ยิงเป็นชุดในนาทีเดียวกัน = รูปแบบการนั่งทดสอบ ไม่ใช่ระบบที่รันตามรอบ และไม่มีการเรียกเลยตั้งแต่ 4 ก.ค.
ตัดสินใจปิดเป็น **commit แยก** (`112736d`) จากชุดถอด apassword (`af74e23`) → ถ้ามีระบบแอบใช้ list โผล่มาทีหลัง revert เฉพาะตัวนี้ได้โดยไม่ต้องเอารหัสผ่านกลับมารั่ว
เลือกตอบ **403 (ไม่ใช่ 404)** เพื่อให้ `ApiAccessLogMixin` บันทึกไว้ → ถ้ามีคนใช้จะเห็นในหน้า monitor ทันที

### 2026-07-20 — แก้ไขชื่อสมาชิกถาวร ต้องมี endpoint `update/` แยก ใช้ `register/` ซ้ำไม่ได้
ตอนแรกดูเหมือนใช้ `permanent/register/` ยิงทับด้วย citizen_id เดิมก็พอ แต่ `register/` ตั้งใจออกแบบให้เป็น "ลงทะเบียนใหม่" คือ **บังคับ `status = pending` เสมอ** และถ้าคนนั้นเป็น permanent ที่ `active` อยู่แล้วจะตอบ **409 ปฏิเสธไปเลย** (กันเผลอถอนสิทธิ์คนที่อนุมัติแล้ว)
→ ถ้าดันใช้ทางนั้นแก้ชื่อ จะกลายเป็นว่าคนที่อนุมัติแล้ว **แก้ชื่อไม่ได้เลย** (ติด 409) ส่วนคนที่ยัง pending ก็เสี่ยงโดนรีเซ็ตสถานะ
ตัดสินใจ: เพิ่ม `POST /v2/external/permanent/{citizen_id}/update/` แยก — แตะเฉพาะ `first_name`/`last_name` (+`photo` ถ้าแนบมา, ลบไฟล์รูปเดิมทิ้ง) และ **ไม่แตะ `status`/`permanent_code`/`approved_at`/`approved_by`** → แก้ชื่อคนที่ถือบัตรอยู่ได้โดยรหัสถาวรเดิมยังสแกนผ่าน ไม่ต้องอนุมัติใหม่/ออกบัตรใหม่
ฝั่ง reserv เป็นหน้า `/manage/external/<id>/edit/` proxy มาที่ endpoint นี้ (reserv ไม่เก็บข้อมูลสมาชิกเอง — api เป็น source of truth)
deploy prod ทั้ง 2 repo + เทสจริงผ่านแล้ว

### 2026-07-13 — ย้าย secret ที่ hardcode เป็น default ใน settings.py ไป .env
เดิม `settings.py` มี pattern `X = env('X', default='<ค่าจริง>')` ซึ่งทำให้ **token production หลุดอยู่ในโค้ดที่ commit** (Walai token บรรทัด 212, HA_TOKEN บรรทัด 209 — long-lived อายุถึง ~2034)
ตัดสินใจ: เปลี่ยน default เป็น `''` แล้วให้ค่าจริงมาจาก `.env` เท่านั้น (`.env` gitignore อยู่แล้ว)
**กฎที่ได้:** เมื่อลบ hardcode default แบบนี้ = สร้าง breaking change ซ่อน — **ต้องเพิ่ม key นั้นใน `.env` ของ prod (เครื่อง 202.29.55.217 คนละไฟล์กับ dev) ก่อน `git pull` เสมอ** ไม่งั้นหลัง restart ค่าจะว่าง ระบบที่พึ่ง token นั้นพัง (Walai=เช็คสมาชิกห้องสมุด, HA=คุม IoT ทั้ง V1+V2)
ทำ+verify prod แล้วทั้งคู่: Walai เช็คสมาชิกผ่าน, HA เปิด/ปิด IoT ผ่าน

## หมายเหตุ

### 2026-07-13 — token เก่ายังตกค้างในไฟล์ backup local (ไม่ใช่ repo)
`grep` token literal ยังเจอใน `code_deploy/` (archive หลาย snapshot) และ `apiproject/settings27062025.py` — แต่ทั้งหมด **gitignore + ไม่ track** จึงไม่หลุดขึ้น GitHub ยืนยันด้วย `git grep` ว่าไฟล์ที่ track จริงสะอาดหมด ถ้าจะล้างเครื่องให้หมดจริงค่อยลบไฟล์ backup local ทีหลัง (task ใน next)

### 2026-07-13 — Postman เว็บ (Cloud Agent) ยิง api.npu.ac.th ไม่ถึง
ยิง `api.npu.ac.th` ผ่าน Postman **เว็บ** (postman.co) ด้วย Cloud Agent → ได้ HTTP 200 แต่ body เป็นหน้า HTML ของ Postman เอง (มี USER_ID/TEAM_ID, bifrost gw) ไม่ใช่ JSON ของ API — เพราะ Cloud Agent อยู่นอกเครือข่ายมหาลัย เข้า host ไม่ถึง
**ทางแก้:** ใช้ Postman **Desktop app** (หรือ Desktop Agent) บนเครื่องที่เข้าเน็ต npu ได้ → ยิงถึงจริง ได้ JSON ถูกต้อง

## บันทึกงานที่ทำ (changelog)

### 2026-07-23 (รอบบ่าย)
- ❌ **ถอด `staffbirthdate`+`gendernameth` ออกจากเส้นถามตรง → ประตูเปิดไม่ได้** (`edf1b06`) · rollback + revert (`7cd9b74`) · ประตูกลับมาปกติ · รายละเอียด/บทเรียนอยู่หัวข้อ "ปัญหา & วิธีแก้"
- ✅ **test กันถอยหลัง 7 เคส** (`65ea0f1`) — `StudentStaffEndpointLockdownTests` (v1 list 403 / write 405 / v2 401) + `RendererAndFieldExposureTests` (BrowsableAPIRenderer ปิด, ไม่มี apassword) · รวม 29/29
  **วิธีพิสูจน์ว่าเทสจับผิดได้จริง (ทำซ้ำครั้งหน้า):** ลองถอด `NoListMixin` ออกจาก ViewSet แล้วรันใหม่ — เคสต้องแดง และ error ที่ได้คือ `no such table: students_info` ซึ่งยืนยันว่า request วิ่งถึง DB จริงถ้าไม่มีตัวป้องกัน ไม่ใช่ status code บังเอิญตรง
- ℹ️ route ของ staff v2 คือ **`/v2/personnel/`** ไม่ใช่ `/v2/staff/` (urls.py บรรทัด 48 — comment บอกว่าเปลี่ยนชื่อจาก 'staff-info')
- ℹ️ query `api_access_log` จากเครื่อง dev ได้ตรง ๆ ด้วย `C:\Python312\python.exe` + `MySQLdb` อ่าน `.env` (ไม่มี venv ในโปรเจกต์) — เร็วกว่าและได้ข้อมูลครบกว่าหน้า monitor ตอนต้องวิเคราะห์ย้อนหลัง

### 2026-07-23 (รอบเช้า)
- ✅ **ปิดช่องโหว่ endpoint นักศึกษา/บุคลากรครบ 4 เรื่อง** — ถอด `apassword`, `ReadOnlyModelViewSet`, ปิด `list` (403), ปิด BrowsableAPIRenderer · `af74e23` + `112736d` · deploy + verify prod ผ่านทุกข้อ (405/403/406/200) · traceon + reserv + LDAP auth ทำงานปกติ fail = 0
- ✅ **เครื่องมือย้อนกลับ** — `rollback.ps1` (git reset --hard + collectstatic + recycle app pool, ~5-10 วิ, ทำงาน local ไม่ต้องรอ GitHub) + `deploy.ps1` บันทึกจุดย้อนกลับลง `.deploy-last-good` และ smoke check `/health/` · `975a499` · **ใช้ย้อนกลับจริงบน prod แล้วสำเร็จ** แล้ว deploy กลับขึ้นมา
- ✅ แก้บั๊ก `deploy.ps1` เขียนทับจุดย้อนกลับตอน deploy ซ้ำ (เขียนไฟล์หลัง pull และเฉพาะเมื่อ HEAD ขยับ) · `4b1eda2` · ทดสอบด้วย git repo จำลอง 3 รอบ
- ✅ อัปเดตเอกสาร README.md / API_ENDPOINTS.md ให้ตรงพฤติกรรมใหม่ (403 list, 405 write, ไม่มี apassword) · test 22/22 ผ่าน

### 2026-07-20
- ✅ **`POST /v2/external/permanent/{citizen_id}/update/`** — แก้ไขชื่อ-สกุลสมาชิกถาวร ([views_v2.py](apiapp/views_v2.py) `permanent_update()`): บังคับ `first_name`+`last_name` (ว่าง → 400), แนบ `photo` ได้ (multipart → เปลี่ยนรูป + ลบไฟล์เดิม), รับทั้ง JSON และ form-data, ไม่เจอ/ไม่ใช่ permanent → 404 · ไม่มี migration (ไม่แตะ model) · อัปเดต API_ENDPOINTS.md · push `e14897d` → origin/main
- ✅ deploy prod ทั้ง 2 repo + เทสจริงผ่าน — แก้ชื่อ-นามสกุลบุคคลภายนอกถาวรได้ ระบบทำงานร่วมกับ reserv ปกติ
- ⚠️ **ยังไม่มี automated test** ของ endpoint นี้ (ผ่านแค่ `manage.py check` + เทสมือบน prod) — เป็น task ใน `next:`

### 2026-07-16
- ✅ **deploy prod (`deploy.ps1`) + เทส prod ผ่าน** — issue ไม่บังคับ citizen_id ทำงานถูกต้องบน production (ไม่มี migration)
- ✅ **ทีมประตูเทส QR จริงผ่านแล้วทั้ง 2 แบบ (รายวัน + ถาวร)** ผ่าน `/v2/external/check/` — QR ออกสมบูรณ์ สแกนเข้าประตูได้จริง ปิดงาน external access **ครบวงจร** (task ค้างตั้งแต่ 2026-07-12)
- ✅ `/v2/external/issue/` (เส้นรายวัน) — ทำ `citizen_id` เป็น **optional** (เดิมบังคับ ผ่าน `is_valid_thai_citizen_id`) mirror pattern เดียวกับ `permanent_register`: ไม่ส่งเลขบัตร → `_gen_external_ref_id()` gen `V`+12 หลัก แล้วออกรหัสรายวันได้ · บังคับแค่ `first_name`+`last_name` · [views_v2.py](apiapp/views_v2.py) `issue()` + เทส `DailyPoolAccessCodeTests` เพิ่ม 2 เคส (gen ref-id + gate allow, และ anonymous ไม่ dedupe/กินสล็อตทุกครั้ง) — api tests 22/22 ผ่าน · **trade-off:** ไม่มีเลขบัตร = แยกคนไม่ได้ → บล็อก/โควตา/dedupe ต่อคนใช้ไม่ได้ และกินสล็อต pool (default 100/วัน ขยายด้วย `seed_access_codes --count N`) ทุกครั้ง — จับคู่กับงานฝั่ง reserv วันเดียวกัน · ยังไม่ push/deploy

### 2026-07-13
- ✅ cleanup ไฟล์ untracked backup 7 ไฟล์ (commit `da661fc`)
- ✅ ทำเอกสาร Word คู่มือ external-check API ให้ทีมประตู (`doc/คู่มือทีมประตู-external-check-api.docx`, untracked) + เทสยิง check บน prod ผ่าน (Postman desktop)
- ✅ เพิ่ม `DailyPoolAccessCodeTests` 10 เคส เส้นรหัสรายวัน (issue+check) — apiapp/tests.py 20/20 (commit `ee75109`)
- ✅ ย้าย WALAI_API_TOKEN + test_walai_search.py อ่านจาก .env (commit `ee75109`) — deploy+verify prod
- ✅ ย้าย HA_TOKEN + ลบ comment token ตกค้าง views.py (commit `44f95da`) — deploy+verify prod
- push ครบทั้ง 3 commit ขึ้น origin/main (`da661fc..44f95da`)

### 2026-07-10
- ✅ push ค้าง 2 commits ขึ้น GitHub สำเร็จ (`54de5ee..8779351` main) — push จากฝั่ง Windows แทน WSL
- ✅ deploy prod (git pull+restart) เรียบร้อย, เทส prod ผ่าน — permanent_register ไม่บังคับ citizen_id (รองรับ VVIP) ทำงานถูกต้องบน production, e2e กับ reserv ผ่าน
- เหลืองานเดียว: แจ้งทีมประตูเอา QR code ไปทดสอบว่าเข้าได้จริงหรือไม่ (route `/v2/external/check/` พร้อมแล้ว รอทีมประตูเพิ่ม route 10 หลักฝั่งเขา)
