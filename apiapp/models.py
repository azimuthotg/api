from django.db import models
# Unable to inspect table 'table'
# The error was: (1146, "Table 'api.table' doesn't exist")

class UserProfile(models.Model):
    userId = models.CharField(max_length=100,unique=True)
    userLdap = models.CharField(max_length=100)
    # userLdap = models.CharField(max_length=100,unique=True)
    # เพิ่มคอลัมน์ user_type สำหรับเก็บประเภทผู้ใช้
    user_type = models.CharField(max_length=100)  # หรือใช้ choices เพื่อกำหนดค่าที่อนุญาต

    def __str__(self):
        return f"UserProfile: {self.userId} - Ldap: {self.userLdap} - Type: {self.user_type}"

class BindingLog(models.Model):
    """บันทึกกิจกรรมการผูกบัญชี (LINE UID + LDAP) สำหรับหน้า Monitor

    เก็บทุกครั้งที่มีการเรียก auth_ldap ไม่ว่าจะสำเร็จหรือไม่ พร้อมสาเหตุ
    (reason_code) เพื่อให้เจ้าหน้าที่หน้างานเห็นว่าเกิดอะไรขึ้น
    """
    STATUS_SUCCESS = 'success'
    STATUS_FAIL = 'fail'
    STATUS_CHOICES = [
        (STATUS_SUCCESS, 'สำเร็จ'),
        (STATUS_FAIL, 'ไม่สำเร็จ'),
    ]

    # reason_code: ok | invalid_credentials | not_in_ad | ad_error | db_not_found | missing_input
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    event = models.CharField(max_length=30, default='ldap_auth')  # ldap_auth / auth_student / auth_personnel
    line_uid = models.CharField(max_length=100, blank=True, null=True)
    display_name = models.CharField(max_length=150, blank=True, null=True)
    user_ldap = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    user_type = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, db_index=True)
    reason_code = models.CharField(max_length=50, blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    ip_address = models.CharField(max_length=45, blank=True, null=True)
    api_version = models.CharField(max_length=5, blank=True, null=True)

    class Meta:
        db_table = 'binding_log'
        ordering = ['-created_at']
        verbose_name = 'Binding Log'
        verbose_name_plural = 'Binding Logs'

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.user_ldap} - {self.status} ({self.reason_code})"


class TokenIssueLog(models.Model):
    """บันทึกทุกครั้งที่ API ออก JWT (obtain / refresh) สำหรับหน้า Monitor

    JWT เป็น stateless — ปกติไม่มี record ว่าใครได้ token ไปเมื่อไหร่/หมดเมื่อไหร่
    โมเดลนี้เก็บไว้เพื่อให้เห็นล่วงหน้าว่า token ของระบบไหนใกล้หมดอายุ
    (เคยเกิดเหตุระบบล่มเพราะ token หมดโดยไม่มีใครรู้)
    """
    EVENT_OBTAIN = 'obtain'
    EVENT_REFRESH = 'refresh'
    EVENT_CHOICES = [
        (EVENT_OBTAIN, 'ขอใหม่ (login)'),
        (EVENT_REFRESH, 'ต่ออายุ (refresh)'),
    ]

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    event = models.CharField(max_length=10, choices=EVENT_CHOICES, default=EVENT_OBTAIN)
    username = models.CharField(max_length=150, blank=True, null=True, db_index=True)
    user_id = models.CharField(max_length=50, blank=True, null=True)
    jti = models.CharField(max_length=64, blank=True, null=True)
    issued_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True, db_index=True)
    ip_address = models.CharField(max_length=45, blank=True, null=True)
    user_agent = models.CharField(max_length=300, blank=True, null=True)

    class Meta:
        db_table = 'token_issue_log'
        ordering = ['-created_at']
        verbose_name = 'Token Issue Log'
        verbose_name_plural = 'Token Issue Logs'

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.username} - {self.event} (exp {self.expires_at:%Y-%m-%d})"


class ApiAccessLog(models.Model):
    """บันทึกการเรียกใช้ endpoint ตรวจสอบ/ดึงข้อมูล นศ.-บุคลากร สำหรับหน้า Monitor

    หลายระบบภายนอกเรียก endpoint เหล่านี้ (login ตรวจ AD / ดึงข้อมูล) แต่ผู้ดูแล
    มองไม่เห็นเลยว่า "ระบบไหน" เรียกเข้ามา ผลเป็นอย่างไร เวลาผู้ใช้มาถามว่า
    "login จากระบบ X เข้าไม่ได้เพราะอะไร" จะได้สืบจาก log นี้ได้
    ระบุระบบจาก client_user (บัญชี JWT ของระบบ) + ip + user_agent. ไม่เก็บรหัสผ่าน.
    """
    RESULT_SUCCESS = 'success'
    RESULT_FAIL = 'fail'

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    client_user = models.CharField(max_length=150, blank=True, null=True, db_index=True)  # username ของ JWT (= ระบบที่เรียก)
    client_ip = models.CharField(max_length=45, blank=True, null=True)
    user_agent = models.CharField(max_length=300, blank=True, null=True)
    api_version = models.CharField(max_length=5, blank=True, null=True)
    endpoint = models.CharField(max_length=100, db_index=True)  # เช่น LDAPAuthViewSetV2.auth_ldap
    method = models.CharField(max_length=8, blank=True, null=True)
    target_user = models.CharField(max_length=100, blank=True, null=True, db_index=True)  # รหัส นศ./บุคลากร ที่ถูกตรวจ/ดึง
    http_status = models.IntegerField(blank=True, null=True, db_index=True)
    result = models.CharField(max_length=10, blank=True, null=True, db_index=True)  # success / fail
    reason_code = models.CharField(max_length=50, blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    duration_ms = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'api_access_log'
        ordering = ['-created_at']
        verbose_name = 'API Access Log'
        verbose_name_plural = 'API Access Logs'

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.client_user or self.client_ip} -> {self.endpoint} ({self.http_status})"


class ApiAccessArchive(models.Model):
    """คลังเก็บ API access log ย้อนหลัง (พ้นวันนี้) ไว้วิเคราะห์/ตรวจสอบระบบที่เข้ามา

    ตารางสด ApiAccessLog เก็บเฉพาะ "วันนี้" เพื่อให้หน้า Monitor real-time เบาตลอด
    ทุกเที่ยงคืน management command `rotate_access_log` ย้ายแถวของเมื่อวานมาที่นี่
    แล้วลบออกจากตารางสด — คงค่า created_at เดิมไว้ จึง "ไม่" ใช้ auto_now_add
    เก็บที่นี่ 90 วันเพื่อการวิเคราะห์ หน้า real-time ไม่แตะตารางนี้เลย โครงสร้างเหมือน
    ApiAccessLog ทุกคอลัมน์ (ดิบครบ) เพื่อให้ย้อนดูรายละเอียดได้เหมือนกัน
    """
    RESULT_SUCCESS = 'success'
    RESULT_FAIL = 'fail'

    created_at = models.DateTimeField(db_index=True)  # คงเวลาจริงจากตารางสด (ไม่ auto_now_add)
    client_user = models.CharField(max_length=150, blank=True, null=True, db_index=True)
    client_ip = models.CharField(max_length=45, blank=True, null=True)
    user_agent = models.CharField(max_length=300, blank=True, null=True)
    api_version = models.CharField(max_length=5, blank=True, null=True)
    endpoint = models.CharField(max_length=100, db_index=True)
    method = models.CharField(max_length=8, blank=True, null=True)
    target_user = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    http_status = models.IntegerField(blank=True, null=True, db_index=True)
    result = models.CharField(max_length=10, blank=True, null=True, db_index=True)
    reason_code = models.CharField(max_length=50, blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    duration_ms = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'api_access_archive'
        ordering = ['-created_at']
        verbose_name = 'API Access Archive'
        verbose_name_plural = 'API Access Archives'

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.client_user or self.client_ip} -> {self.endpoint} ({self.http_status})"


class ExternalMember(models.Model):
    """บุคคลภายนอกที่ลงทะเบียนขอเข้าใช้ห้องสมุด — ประชากร "ขาที่ 3"

    ไม่มีใน AD (และเราแตะ AD ไม่ได้) ไม่มีใน StudentsInfo/StaffInfo → เก็บตัวตนเองในตารางนี้
    (Django-managed เขียนได้). กุญแจ = เลขบัตร ปชช. 13 หลัก (ตรวจ checksum ตอนลงทะเบียน).

    มี 2 ประเภท (member_type):
    - daily     : ลงทะเบียนเองอนุมัติทันที (status=active) ใช้รหัส 10 หลักจาก ExternalAccessCode (pool รายวัน)
    - permanent : เช่น พนักงานส่งเอกสาร — admin อนุมัติก่อน (เริ่ม pending → active) ได้ permanent_code
                  คงที่ใช้ได้ทุกวันจนกว่าจะ revoked, มี photo สำหรับทำบัตร (reserv จัดการที่ /manage/)
    """
    STATUS_PENDING = 'pending'
    STATUS_ACTIVE = 'active'
    STATUS_REVOKED = 'revoked'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'pending'),
        (STATUS_ACTIVE, 'active'),
        (STATUS_REVOKED, 'revoked'),
    ]

    TYPE_DAILY = 'daily'
    TYPE_PERMANENT = 'permanent'
    TYPE_CHOICES = [(TYPE_DAILY, 'daily'), (TYPE_PERMANENT, 'permanent')]

    citizen_id = models.CharField(max_length=13, primary_key=True)  # เลขบัตร ปชช. (ผ่าน checksum)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    member_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_DAILY, db_index=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True)
    permanent_code = models.CharField(max_length=10, unique=True, blank=True, null=True, db_index=True)  # รหัสถาวร (สมาชิกถาวรเท่านั้น) ออกตอน approve
    photo = models.ImageField(upload_to='external_member_photos/', blank=True, null=True)  # รูปสำหรับทำบัตร
    approved_at = models.DateTimeField(blank=True, null=True)
    approved_by = models.CharField(max_length=150, blank=True, null=True)  # username ของ JWT ที่อนุมัติ
    registered_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'external_member'
        ordering = ['-registered_at']
        verbose_name = 'External Member'
        verbose_name_plural = 'External Members'

    def __str__(self):
        return f"{self.citizen_id} {self.first_name} {self.last_name} ({self.status})"


class ExternalAccessCode(models.Model):
    """Pool รหัส 10 หลักสำหรับเปิดประตู (หมุนเวียนรายวัน)

    รหัสถูก seed ไว้ล่วงหน้า (command seed_access_codes) เป็นเลขสุ่ม 10 หลัก (ไม่เรียงลำดับ
    เดายาก). เมื่อบุคคลภายนอกขอเข้า ระบบจองรหัสที่ "ว่างวันนี้" ตัวที่ถูกใช้นานสุดก่อน (หมุนวน)
    ผูกกับ assigned_citizen_id + assigned_date = วันนี้ (เวลาไทย). ประตูส่งรหัส 10 หลักมาเช็ค:
    ถ้า assigned_date == วันนี้ = ผ่าน. รหัสใช้ได้วันเดียว ของเมื่อวานจึงใช้ไม่ได้.
    """
    code = models.CharField(max_length=10, unique=True)  # รหัสที่ฝังใน QR (ประตูอ่าน) เลขสุ่ม 10 หลัก
    seq = models.IntegerField(unique=True)               # ลำดับใน pool (1..N)
    assigned_citizen_id = models.CharField(max_length=13, blank=True, null=True, db_index=True)
    assigned_date = models.DateField(blank=True, null=True, db_index=True)  # วันไทยที่รหัสนี้ใช้ได้

    class Meta:
        db_table = 'external_access_code'
        ordering = ['seq']
        verbose_name = 'External Access Code'
        verbose_name_plural = 'External Access Codes'

    def __str__(self):
        return f"#{self.seq} {self.code} -> {self.assigned_citizen_id or '-'} ({self.assigned_date or '-'})"


class StudentsInfo(models.Model):
    student_code = models.CharField(max_length=50, blank=True, null=False,primary_key=True)  # กำหนดให้ student_code เป็น primary key
    prefix_name = models.CharField(max_length=50, blank=True, null=True)
    student_name = models.CharField(max_length=100, blank=True, null=True)
    student_surname = models.CharField(max_length=100, blank=True, null=True)
    level_id = models.IntegerField(blank=True, null=True)
    level_name = models.CharField(max_length=50, blank=True, null=True)
    program_name = models.CharField(max_length=100, blank=True, null=True)
    degree_name = models.CharField(max_length=100, blank=True, null=True)
    faculty_name = models.CharField(max_length=100, blank=True, null=True)
    apassword = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'students_info'


class StaffInfo(models.Model):
    staffid = models.CharField(db_column='STAFFID', primary_key=True, max_length=50)  # Field name made lowercase.
    staffcitizenid = models.CharField(db_column='STAFFCITIZENID', max_length=13, blank=True, null=True)  # Field name made lowercase.
    prefixfullname = models.CharField(db_column='PREFIXFULLNAME', max_length=50, blank=True, null=True)  # Field name made lowercase.
    staffname = models.CharField(db_column='STAFFNAME', max_length=100, blank=True, null=True)  # Field name made lowercase.
    staffsurname = models.CharField(db_column='STAFFSURNAME', max_length=100, blank=True, null=True)  # Field name made lowercase.
    staffbirthdate = models.DateField(db_column='STAFFBIRTHDATE', blank=True, null=True)  # Field name made lowercase.
    gendernameth = models.CharField(db_column='GENDERNAMETH', max_length=50, blank=True, null=True)  # Field name made lowercase.
    posnameth = models.CharField(db_column='POSNAMETH', max_length=100, blank=True, null=True)  # Field name made lowercase.
    stftypename = models.CharField(db_column='STFTYPENAME', max_length=100, blank=True, null=True)  # Field name made lowercase.
    substftypename = models.CharField(db_column='SUBSTFTYPENAME', max_length=100, blank=True, null=True)  # Field name made lowercase.
    stfstaname = models.CharField(db_column='STFSTANAME', max_length=100, blank=True, null=True)  # Field name made lowercase.
    departmentname = models.CharField(db_column='DEPARTMENTNAME', max_length=100, blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'staff_info'
