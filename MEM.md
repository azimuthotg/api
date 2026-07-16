# MEM — apiproject (NPU API Backend)

คลังความรู้เฉพาะโปรเจกต์นี้ (ปัญหา/หมายเหตุ/การตัดสินใจ + changelog)
ทะเบียน "งานที่ต้องทำ" อยู่ในบล็อก `<!-- PROJECT-STATUS -->` ด้านบนของ CLAUDE.md — ไฟล์นี้ไว้เก็บ "ความรู้" เท่านั้น

## ปัญหา & วิธีแก้

### 2026-07-10 — push GitHub จาก WSL ไม่ได้
token ใน `/root/.git-credentials` (WSL) หมดอายุ/ถูก revoke — GitHub ตอบ "Invalid username or token"
ทางแก้: push จากฝั่ง Windows (`C:\projects\apiproject`) ที่ใช้ Git Credential Manager แยกกัน แทนการสร้าง PAT ใหม่

## การตัดสินใจ

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
