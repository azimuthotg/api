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
