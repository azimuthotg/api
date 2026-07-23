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
        # ระบุฟิลด์ตรง ๆ แทน '__all__' เพื่อไม่ให้ apassword (รหัสผ่าน plaintext) หลุดออก API
        fields = ['student_code', 'prefix_name', 'student_name', 'student_surname',
                  'level_id', 'level_name', 'program_name', 'degree_name', 'faculty_name',
                  'fullname']

    # เพิ่มเมธอดสำหรับคำนวณชื่อเต็ม
    def get_fullname(self, obj):
        return f"{obj.prefix_name or ''} {obj.student_name or ''} {obj.student_surname or ''}".strip()
        
class StaffInfoSerializerV2(serializers.ModelSerializer):
    """ข้อมูลบุคลากรสำหรับการถามตรงด้วยเลขบัตร (/v2/staff/{id}/)

    ทางนี้แค่รู้เลขบัตร (+ token ของระบบผู้เรียก) ก็ขอข้อมูลของใครก็ได้ จึงส่งเฉพาะ
    ข้อมูลสังกัด/ตำแหน่ง ไม่ส่ง staffbirthdate (วันเกิด) และ gendernameth (เพศ)
    ถ้าเป็นทางที่เจ้าตัวล็อกอินด้วยรหัสผ่านตัวเอง ให้ใช้ StaffInfoFullSerializerV2 แทน
    """
    # เพิ่ม field เพื่อแสดงข้อมูลเต็ม
    fullname = serializers.SerializerMethodField()

    class Meta:
        model = StaffInfo
        # ระบุฟิลด์ตรง ๆ แทน '__all__' เพื่อไม่ให้คอลัมน์ที่เพิ่มเข้ามาทีหลังหลุดออก API เอง
        fields = ['staffid', 'staffcitizenid', 'prefixfullname', 'staffname',
                  'staffsurname', 'posnameth', 'stftypename', 'substftypename',
                  'stfstaname', 'departmentname', 'fullname']

    # เพิ่มเมธอดสำหรับคำนวณชื่อเต็ม
    def get_fullname(self, obj):
        return f"{obj.prefixfullname or ''} {obj.staffname or ''} {obj.staffsurname or ''}".strip()


class StaffInfoFullSerializerV2(StaffInfoSerializerV2):
    """ข้อมูลบุคลากรฉบับเต็ม — ใช้เฉพาะหลังเจ้าตัวยืนยันตัวตนกับ AD ด้วยรหัสผ่านของตัวเอง
    (auth_and_get_personnel) จึงเป็นข้อมูลของตัวเอง ส่ง staffbirthdate + gendernameth ได้

    emoney ใช้ staffbirthdate จากทางนี้ไปเก็บวันเกิดผู้ใช้ — ห้ามถอดออกโดยไม่แจ้งล่วงหน้า
    """
    class Meta(StaffInfoSerializerV2.Meta):
        fields = StaffInfoSerializerV2.Meta.fields + ['staffbirthdate', 'gendernameth']


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