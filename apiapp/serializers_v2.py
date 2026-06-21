# apiapp/serializers_v2.py
from rest_framework import serializers
from apiapp.models import UserProfile, StudentsInfo, StaffInfo, ExternalMember

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


class ExternalMemberSerializerV2(serializers.ModelSerializer):
    """สมาชิกภายนอก (ใช้กับหน้า /manage/ ของ reserv) — ไม่ส่ง path รูปดิบ
    รูปดึงผ่าน endpoint แยกที่ต้องใช้ JWT; ส่งแค่ has_photo บอกว่ามีรูปไหม
    """
    fullname = serializers.SerializerMethodField()
    has_photo = serializers.SerializerMethodField()

    class Meta:
        model = ExternalMember
        fields = [
            'citizen_id', 'first_name', 'last_name', 'fullname',
            'member_type', 'status', 'permanent_code', 'has_photo',
            'approved_at', 'approved_by', 'registered_at',
        ]

    def get_fullname(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()

    def get_has_photo(self, obj):
        return bool(obj.photo)