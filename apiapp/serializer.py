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
    class Meta:
        model = StaffInfo
        fields = '__all__'  # หรือระบุเฉพาะฟิลด์ที่คุณต้องการ