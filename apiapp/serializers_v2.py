# apiapp/serializers_v2.py
from rest_framework import serializers
from apiapp.models import UserProfile, StudentsInfo, StaffInfo

class UserProfileSerializerV2(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = "__all__"
        # เพิ่มเติม: ถ้าต้องการแสดงข้อมูลเพิ่มเติมหรือปรับแต่งข้อมูลใน v2

class StudentsInfoSerializerV2(serializers.ModelSerializer):
    # เพิ่ม field เพื่อแสดงข้อมูลเต็ม
    fullname = serializers.SerializerMethodField()
    
    class Meta:
        model = StudentsInfo
        fields = '__all__'
    
    # เพิ่มเมธอดสำหรับคำนวณชื่อเต็ม
    def get_fullname(self, obj):
        return f"{obj.prefix_name or ''} {obj.student_name or ''} {obj.student_surname or ''}".strip()
        
class StaffInfoSerializerV2(serializers.ModelSerializer):
    # เพิ่ม field เพื่อแสดงข้อมูลเต็ม
    fullname = serializers.SerializerMethodField()
    
    class Meta:
        model = StaffInfo
        fields = '__all__'
    
    # เพิ่มเมธอดสำหรับคำนวณชื่อเต็ม
    def get_fullname(self, obj):
        return f"{obj.prefixfullname or ''} {obj.staffname or ''} {obj.staffsurname or ''}".strip()