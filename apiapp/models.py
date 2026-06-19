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
