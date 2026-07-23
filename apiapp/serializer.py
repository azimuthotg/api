# apiproject/apiapp/serializers.py
from rest_framework import serializers
from apiapp.models import UserProfile,StudentsInfo,StaffInfo

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = "__all__"

class StudentsInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentsInfo
        # ระบุฟิลด์ตรง ๆ แทน '__all__' เพื่อไม่ให้ apassword (รหัสผ่าน plaintext) หลุดออก API
        fields = ['student_code', 'prefix_name', 'student_name', 'student_surname',
                  'level_id', 'level_name', 'program_name', 'degree_name', 'faculty_name']
        
class StaffInfoSerializer(serializers.ModelSerializer):
    """ข้อมูลบุคลากรสำหรับการถามตรงด้วยเลขบัตร (/staff-info/{id}/)

    ทางนี้แค่รู้เลขบัตรก็ขอได้ จึงส่งเฉพาะข้อมูลสังกัด/ตำแหน่งที่ผู้เรียกต้องใช้
    ไม่ส่ง staffbirthdate (วันเกิด) และ gendernameth (เพศ) ออกไป
    """
    class Meta:
        model = StaffInfo
        # ระบุฟิลด์ตรง ๆ แทน '__all__' เพื่อไม่ให้คอลัมน์ที่เพิ่มเข้ามาทีหลังหลุดออก API เอง
        fields = ['staffid', 'staffcitizenid', 'prefixfullname', 'staffname',
                  'staffsurname', 'posnameth', 'stftypename', 'substftypename',
                  'stfstaname', 'departmentname']