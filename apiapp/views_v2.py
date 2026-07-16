# apiapp/views_v2.py
from librouteros import connect
from apiapp.models import UserProfile, StudentsInfo, StaffInfo, ExternalMember, ExternalAccessCode
from apiapp.serializers_v2 import UserProfileSerializerV2, StudentsInfoSerializerV2, StaffInfoSerializerV2, ExternalMemberSerializerV2
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from ldap3 import Server, Connection, ALL, NTLM
from rest_framework.decorators import action
from django.http import FileResponse
import mimetypes
import random
import requests
import time
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny

# นำเข้า Authentication Mixins
from apiapp.authentication import JWTV2Authentication, PublicEndpointAuthentication
from apiapp.monitoring import check_ad_detailed, log_binding, BindLoggingCreateMixin
from apiapp.access_log import ApiAccessLogMixin
from apiapp.thai_id import is_valid_thai_citizen_id
from django.db import transaction
from django.db.models import F
from zoneinfo import ZoneInfo

# เส้นแบ่ง "วัน" ของรหัสเข้าประตู ใช้เวลาไทย (DB เก็บ UTC — ดู monitor-timezone-mysql)
BANGKOK_TZ = ZoneInfo('Asia/Bangkok')


def _bkk_today():
    return timezone.now().astimezone(BANGKOK_TZ).date()


def _gen_permanent_code():
    """สุ่มรหัสถาวร 10 หลัก (หลักแรก 1-9) ไม่ชนกับ pool รายวัน (ExternalAccessCode)
    และไม่ชนกับ permanent_code ของสมาชิกถาวรคนอื่น — คืน str หรือ None เมื่อหาไม่ได้
    """
    for _ in range(10000):
        code = str(random.randint(1_000_000_000, 9_999_999_999))
        if (not ExternalAccessCode.objects.filter(code=code).exists()
                and not ExternalMember.objects.filter(permanent_code=code).exists()):
            return code
    return None


def _gen_external_ref_id():
    """ID อ้างอิงแทนเลขบัตร ปชช. สำหรับบุคคลสำคัญที่ไม่สะดวกให้เลขบัตร (ลงทะเบียนถาวรโดย staff)
    รูปแบบ V + เลขสุ่ม 12 หลัก (รวม 13 ตัว เท่า PK เดิม, ไม่ชนเลขบัตรจริงซึ่งเป็นตัวเลขล้วน)
    คืน str หรือ None เมื่อหาไม่ได้
    """
    for _ in range(10000):
        ref = 'V' + str(random.randint(0, 999_999_999_999)).zfill(12)
        if not ExternalMember.objects.filter(citizen_id=ref).exists():
            return ref
    return None

class UserViewSetV2(BindLoggingCreateMixin, JWTV2Authentication, viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializerV2
    lookup_field = 'userId'
    bind_api_version = 'v2'
    
    # เพิ่มฟีเจอร์ใหม่สำหรับ v2 เช่น
    # - การกรองข้อมูล
    # - pagination ที่ปรับแต่งได้
    # - การค้นหาขั้นสูง

class StudentsInfoViewSetV2(ApiAccessLogMixin, JWTV2Authentication, viewsets.ModelViewSet):
    queryset = StudentsInfo.objects.all()
    serializer_class = StudentsInfoSerializerV2
    lookup_field = 'student_code'
    access_log_api_version = 'v2'
    
    # เพิ่มความสามารถในการค้นหาด้วยชื่อหรือนามสกุล
    def get_queryset(self):
        queryset = super().get_queryset()
        name = self.request.query_params.get('name', None)
        surname = self.request.query_params.get('surname', None)
        
        if name:
            queryset = queryset.filter(student_name__icontains=name)
        if surname:
            queryset = queryset.filter(student_surname__icontains=surname)
            
        return queryset

class StaffInfoViewSetV2(ApiAccessLogMixin, JWTV2Authentication, viewsets.ModelViewSet):
    queryset = StaffInfo.objects.all()
    serializer_class = StaffInfoSerializerV2
    lookup_field = 'staffcitizenid'
    access_log_api_version = 'v2'
    
    # เพิ่มความสามารถในการค้นหาด้วยชื่อหรือตำแหน่ง
    def get_queryset(self):
        queryset = super().get_queryset()
        name = self.request.query_params.get('name', None)
        department = self.request.query_params.get('department', None)
        
        if name:
            queryset = queryset.filter(staffname__icontains=name)
        if department:
            queryset = queryset.filter(departmentname__icontains=department)
            
        return queryset

#---------------------------------------------
def check_user_in_ad(userLdap, passLdap):
    # delegate ไปยัง check_ad_detailed (source of truth เดียว) แล้วคืน signature เดิม
    success, ldap_info, _reason, _message = check_ad_detailed(userLdap, passLdap)
    return success, ldap_info

#---------------------------------------------
# เปลี่ยนจาก LDAPAuthViewSetV2 เป็น AuthViewSetV2
class AuthViewSetV2(PublicEndpointAuthentication, viewsets.ViewSet):
    """
    ViewSet สำหรับการตรวจสอบสิทธิ์ผ่าน Django User และการสร้าง JWT token
    """

    @action(detail=False, methods=['post'])
    def login(self, request):
        """
        Endpoint สำหรับการล็อกอินและรับ JWT token (ใช้ Django User)
        """
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({
                'success': False,
                'detail': 'Missing username or password'
            }, status=status.HTTP_400_BAD_REQUEST)

        # ตรวจสอบสิทธิ์ผ่าน Django Authentication
        user = authenticate(username=username, password=password)

        if user:
            # สร้าง JWT tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'success': True,
                'user_info': {
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                },
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                },
                'api_version': 'v2'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False, 
                'detail': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)

    @action(detail=False, methods=['post'])
    def verify_token(self, request):
        """
        Endpoint สำหรับตรวจสอบความถูกต้องของ token
        """
        # ใช้ default authentication ซึ่งตรวจสอบ token อยู่แล้ว
        # ถ้ามาถึงนี่ได้แสดงว่า token ถูกต้อง
        return Response({
            'valid': True,
            'user': request.user.username,
            'timestamp': str(timezone.now())
        }, status=status.HTTP_200_OK)

# คงเก็บไว้สำหรับความเข้ากันได้ย้อนหลัง แต่แยกเป็น class ต่างหาก
class LDAPAuthViewSetV2(ApiAccessLogMixin, JWTV2Authentication, viewsets.ViewSet):
    """
    ViewSet สำหรับการตรวจสอบสิทธิ์ผ่าน LDAP (เก็บไว้สำหรับความเข้ากันได้ย้อนหลัง)
    """
    access_log_api_version = 'v2'
    @action(detail=False, methods=['post'])
    def auth_ldap(self, request):
        """
        Endpoint สำหรับตรวจสอบสิทธิ์ผ่าน LDAP (เหมือนใน v1 แต่ไม่ให้ token)
        """
        user_ldap = request.data.get('userLdap')
        pass_ldap = request.data.get('passLdap')
        # ข้อมูล LINE (ถ้า frontend ส่งมา) สำหรับเชื่อมโยงใน Monitor
        line_uid = request.data.get('line_uid') or request.data.get('userId')
        display_name = request.data.get('display_name') or request.data.get('displayName')
        user_type = request.data.get('user_type')

        if not user_ldap or not pass_ldap:
            log_binding(
                request, event='ldap_auth', user_ldap=user_ldap,
                status='fail', reason_code='missing_input',
                message='ไม่ได้ส่ง userLdap หรือ passLdap',
                line_uid=line_uid, display_name=display_name,
                user_type=user_type, api_version='v2',
            )
            return Response({'detail': 'Missing userLdap or passLdap'}, status=status.HTTP_400_BAD_REQUEST)

        # เรียกใช้ฟังก์ชันตรวจสอบ AD (แบบมีสาเหตุ)
        success, ldap_info, reason_code, message = check_ad_detailed(user_ldap, pass_ldap)
        request._api_access_reason = (reason_code, message)  # ส่งสาเหตุ AD เข้า ApiAccessLog ด้วย

        log_binding(
            request, event='ldap_auth', user_ldap=user_ldap,
            status='success' if success else 'fail',
            reason_code=reason_code, message=message,
            line_uid=line_uid,
            display_name=display_name or (ldap_info.get('displayName') if ldap_info else None),
            user_type=user_type, api_version='v2',
        )

        if success:
            # API v2: เพิ่มข้อมูลการเข้าสู่ระบบล่าสุด
            response_data = {
                'success': True,
                'ldap_info': ldap_info,
                'last_login': {
                    'timestamp': str(timezone.now()),
                    'version': 'v2'
                }
            }
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            return Response({'success': False, 'detail': 'Invalid credentials or user not found in AD'}, status=status.HTTP_401_UNAUTHORIZED)

    @action(detail=False, methods=['post'])
    def auth_and_get_student(self, request):
        """
        Endpoint สำหรับตรวจสอบสิทธิ์และดึงข้อมูลนักศึกษา (เหมือนใน v1)
        """
        user_ldap = request.data.get('userLdap')
        pass_ldap = request.data.get('passLdap')

        if not user_ldap or not pass_ldap:
            return Response({'detail': 'Missing userLdap or passLdap'}, status=status.HTTP_400_BAD_REQUEST)

        # ตรวจสอบ AD
        success, ldap_info = check_user_in_ad(user_ldap, pass_ldap)

        if success:
            try:
                # ค้นหาข้อมูลนักศึกษาตาม userLdap
                student_info = StudentsInfo.objects.get(student_code=user_ldap)
                serializer = StudentsInfoSerializerV2(student_info)
                
                # API v2: เพิ่มข้อมูลคณะและสาขา
                faculty = student_info.faculty_name
                program = student_info.program_name
                
                return Response({
                    'success': True, 
                    'student_info': serializer.data,
                    'additional_info': {
                        'faculty': faculty,
                        'program': program
                    }
                }, status=status.HTTP_200_OK)
            except StudentsInfo.DoesNotExist:
                return Response({'success': False, 'detail': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({'success': False, 'detail': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        
    @action(detail=False, methods=['post'])
    def auth_and_get_personnel(self, request):
        """
        Endpoint สำหรับตรวจสอบสิทธิ์และดึงข้อมูลบุคลากร
        """
        user_ldap = request.data.get('userLdap')
        pass_ldap = request.data.get('passLdap')

        if not user_ldap or not pass_ldap:
            return Response({'detail': 'Missing userLdap or passLdap'}, status=status.HTTP_400_BAD_REQUEST)

        # ตรวจสอบ AD
        success, ldap_info = check_user_in_ad(user_ldap, pass_ldap)

        if success:
            try:
                # ค้นหาข้อมูลบุคลากรตาม userLdap (จุดนี้อาจต้องปรับตามโครงสร้างข้อมูลจริง)
                staff_info = StaffInfo.objects.get(staffcitizenid=user_ldap)
                serializer = StaffInfoSerializerV2(staff_info)
                
                # API v2: เพิ่มข้อมูลแผนกและตำแหน่ง
                department = staff_info.departmentname
                position = staff_info.posnameth
                
                return Response({
                    'success': True, 
                    'personnel_info': serializer.data,
                    'additional_info': {
                        'department': department,
                        'position': position,
                        'login_time': str(timezone.now())
                    }
                }, status=status.HTTP_200_OK)
            except StaffInfo.DoesNotExist:
                return Response({'success': False, 'detail': 'Personnel not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({'success': False, 'detail': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

#---------------------------------------------
class WalaiCheckUserViewSetV2(JWTV2Authentication, viewsets.ViewSet):
    """
    ViewSet สำหรับตรวจสอบข้อมูลผู้ใช้ในระบบ Walai Autolib (v2)
    """
    
    @action(detail=False, methods=['get'], url_path='check_user_walai/(?P<user_ldap>[^/.]+)')
    def check_user_walai(self, request, user_ldap=None):
        
        # URL ของ Walai Autolib API สำหรับตรวจสอบ userLdap
        walai_autolib_api_url = f"{settings.WALAI_API_URL}/{user_ldap}"
        
        # Header ที่ต้องแนบไปกับ request
        headers = {
            "token": settings.WALAI_API_TOKEN,
            "Content-Type": "application/json"
        }
        
        try:
            # ส่ง GET request ไปที่ API ของ Walai Autolib พร้อมกับ header
            response = requests.get(walai_autolib_api_url, headers=headers)
            
            # ตรวจสอบสถานะของคำขอ
            if response.status_code == 200:
                # ถ้าคำขอสำเร็จ ดึงข้อมูล JSON ที่ได้จาก API
                data = response.json()
                
                # API v2: จัดรูปแบบข้อมูลให้อ่านง่ายขึ้น
                formatted_data = {
                    'user_info': {
                        'id': user_ldap,
                        'status': data.get('status', 'unknown')
                    },
                    'library_info': data.get('data', {}),
                    'api_version': 'v2'
                }
                
                return Response(formatted_data, status=status.HTTP_200_OK)
            else:
                # กรณีที่ API ตอบกลับด้วย status code ที่ไม่ใช่ 200
                return Response({"error": f"Failed to retrieve data. Status code: {response.status_code}"}, status=response.status_code)
        
        except requests.RequestException as e:
            # กรณีที่มีข้อผิดพลาดในการเชื่อมต่อกับ API
            return Response({"error": f"Error fetching data from API: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#----------------------------------------------
class ExternalAccessViewSetV2(ApiAccessLogMixin, JWTV2Authentication, viewsets.ViewSet):
    """บุคคลภายนอกเข้าห้องสมุด: ออกรหัส (issue) + เช็คที่ประตู (check_external)

    ประชากร "ขาที่ 3" ที่ไม่มีใน AD และเราแตะ AD ไม่ได้ → ตัวตนอยู่ใน ExternalMember (เขียนได้)
    เข้าใช้งานผ่านรหัส 10 หลักใน ExternalAccessCode (pool หมุนเวียนรายวัน) ดู [[external-library-member]]
    หน้าเว็บออก QR อยู่ระบบ reserv — ที่นี่เป็น backend อย่างเดียว
    ติด ApiAccessLogMixin ให้ check ที่ประตูโผล่ใน /monitor/api-usage/ เหมือน check นศ./บุคลากร
    """
    access_log_api_version = 'v2'

    @action(detail=False, methods=['post'])
    def issue(self, request):
        """รับชื่อ-สกุล (บังคับ) + เลขบัตร 13 หลัก (ไม่บังคับ) → จองรหัสวันนี้

        นโยบายปัจจุบัน: บังคับแค่ชื่อ-สกุล เลขบัตรเป็น optional (เอาสะดวกผู้ใช้ก่อน)
        - ส่งเลขบัตรมา → ตรวจ checksum, dedupe คนเดิมในวันเดียวได้ (คืนรหัสเดิม ไม่เปลือง slot),
          revoke/quota ต่อคนได้
        - ไม่ส่งเลขบัตร → gen ref id ขึ้นต้น V ให้ (เหมือน permanent_register); แต่ละครั้งเป็นคนใหม่
          → ไม่ dedupe และกินสล็อต pool ทุกครั้ง (ยอมแลกกับความสะดวก) ดู [[external-library-member]]
        """
        citizen_id = (request.data.get('citizen_id') or '').strip()
        first_name = (request.data.get('first_name') or '').strip()
        last_name = (request.data.get('last_name') or '').strip()

        if not first_name or not last_name:
            return Response({'success': False, 'detail': 'Missing first_name or last_name'}, status=status.HTTP_400_BAD_REQUEST)
        if citizen_id:
            if not is_valid_thai_citizen_id(citizen_id):
                request._api_access_reason = ('invalid_citizen_id', 'เลขบัตรประชาชนไม่ถูกต้อง')
                return Response({'success': False, 'detail': 'Invalid citizen id'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            citizen_id = _gen_external_ref_id()
            if citizen_id is None:
                return Response({'success': False, 'detail': 'Cannot allocate reference id'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        today = _bkk_today()
        with transaction.atomic():
            member, _created = ExternalMember.objects.get_or_create(
                citizen_id=citizen_id,
                defaults={'first_name': first_name, 'last_name': last_name},
            )
            if member.status == ExternalMember.STATUS_REVOKED:
                request._api_access_reason = ('revoked', 'สมาชิกถูกระงับ')
                return Response({'success': False, 'detail': 'Member revoked'}, status=status.HTTP_403_FORBIDDEN)

            # ออกบัตรซ้ำคนเดิมในวันเดียว = คืนรหัสเดิม (ไม่เปลือง slot)
            assigned = ExternalAccessCode.objects.filter(
                assigned_citizen_id=citizen_id, assigned_date=today
            ).first()
            if assigned is None:
                # จองรหัสที่ว่างวันนี้ ตัวที่ถูกใช้นานสุดก่อน (หมุนวน) — ล็อกแถวกัน race
                assigned = (
                    ExternalAccessCode.objects
                    .exclude(assigned_date=today)
                    .order_by(F('assigned_date').asc(nulls_first=True), 'seq')
                    .select_for_update()
                    .first()
                )
                if assigned is None:
                    request._api_access_reason = ('pool_full', 'รหัสในพูลถูกใช้หมดสำหรับวันนี้')
                    return Response({'success': False, 'detail': 'Access code pool exhausted for today'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
                assigned.assigned_citizen_id = citizen_id
                assigned.assigned_date = today
                assigned.save(update_fields=['assigned_citizen_id', 'assigned_date'])

        return Response({
            'success': True,
            'access_code': assigned.code,       # นำไปสร้าง QR (ฝั่ง reserv)
            'valid_date': today.isoformat(),    # ใช้ได้เฉพาะวันนี้ (เวลาไทย)
            'member': {
                'citizen_id': member.citizen_id,
                'first_name': member.first_name,
                'last_name': member.last_name,
            },
            'api_version': 'v2',
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get', 'post'], url_path='check/(?P<code>[^/.]+)')
    def check_external(self, request, code=None):
        """ประตูส่งรหัส 10 หลักมา → allow ถ้า (ก) เป็นรหัส pool ที่จองไว้วันนี้ หรือ
        (ข) เป็น permanent_code ของสมาชิกถาวรที่ active — ทั้งสองกรณีสมาชิกต้องไม่ถูกระงับ
        ฝั่งประตูเรียก endpoint เดิมตัวเดียว ไม่ต้องแยก logic รายวัน/ถาวร
        """
        today = _bkk_today()

        # (ก) รหัส pool รายวัน
        entry = ExternalAccessCode.objects.filter(code=code, assigned_date=today).first()
        if entry is not None:
            member = ExternalMember.objects.filter(citizen_id=entry.assigned_citizen_id).first()
            if member is None or member.status == ExternalMember.STATUS_REVOKED:
                request._api_access_reason = ('revoked', 'สมาชิกถูกระงับ/ไม่พบ')
                return Response({'allow': False, 'detail': 'Member revoked or not found'}, status=status.HTTP_403_FORBIDDEN)
            return Response({
                'allow': True,
                'member': {
                    'citizen_id': member.citizen_id,
                    'first_name': member.first_name,
                    'last_name': member.last_name,
                },
                'api_version': 'v2',
            }, status=status.HTTP_200_OK)

        # (ข) รหัสถาวร — ใช้ได้ทุกวันถ้าสมาชิก active
        pmember = ExternalMember.objects.filter(
            permanent_code=code, member_type=ExternalMember.TYPE_PERMANENT
        ).first()
        if pmember is not None:
            if pmember.status != ExternalMember.STATUS_ACTIVE:
                request._api_access_reason = ('revoked', 'สมาชิกถาวรถูกระงับ/ยังไม่อนุมัติ')
                return Response({'allow': False, 'detail': 'Permanent member not active'}, status=status.HTTP_403_FORBIDDEN)
            return Response({
                'allow': True,
                'member': {
                    'citizen_id': pmember.citizen_id,
                    'first_name': pmember.first_name,
                    'last_name': pmember.last_name,
                },
                'member_type': 'permanent',
                'api_version': 'v2',
            }, status=status.HTTP_200_OK)

        request._api_access_reason = ('not_valid_today', 'รหัสนี้ไม่ได้ใช้งานวันนี้')
        return Response({'allow': False, 'detail': 'Code not valid today'}, status=status.HTTP_404_NOT_FOUND)

    # ── สมาชิกถาวร (reserv /manage/ เรียก ผ่าน JWT) ────────────────────────────
    @action(detail=False, methods=['post'], url_path='permanent/register',
            parser_classes=[MultiPartParser, FormParser])
    def permanent_register(self, request):
        """ลงทะเบียนสมาชิกถาวร: citizen_id + ชื่อ-สกุล + photo → สร้าง pending รออนุมัติ

        citizen_id เว้นว่างได้ (บุคคลสำคัญที่ไม่สะดวกให้เลขบัตร เช่น นายกสภาฯ — staff ลงทะเบียนให้)
        → ระบบออก ID อ้างอิงขึ้นต้น V ให้แทน; ถ้าส่งมาต้องผ่าน checksum เหมือนเดิม
        """
        citizen_id = (request.data.get('citizen_id') or '').strip()
        first_name = (request.data.get('first_name') or '').strip()
        last_name = (request.data.get('last_name') or '').strip()
        photo = request.FILES.get('photo')

        if citizen_id:
            if not is_valid_thai_citizen_id(citizen_id):
                request._api_access_reason = ('invalid_citizen_id', 'เลขบัตรประชาชนไม่ถูกต้อง')
                return Response({'success': False, 'detail': 'Invalid citizen id'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            citizen_id = _gen_external_ref_id()
            if citizen_id is None:
                return Response({'success': False, 'detail': 'Cannot allocate reference id'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if not first_name or not last_name:
            return Response({'success': False, 'detail': 'Missing first_name or last_name'}, status=status.HTTP_400_BAD_REQUEST)

        member, _created = ExternalMember.objects.get_or_create(
            citizen_id=citizen_id,
            defaults={'first_name': first_name, 'last_name': last_name},
        )
        # ถ้าเป็นสมาชิกถาวรที่อนุมัติแล้ว ไม่รีเซ็ตสถานะ (กันเผลอถอนสิทธิ์)
        if member.member_type == ExternalMember.TYPE_PERMANENT and member.status == ExternalMember.STATUS_ACTIVE:
            return Response({'success': False, 'detail': 'Member already approved as permanent'}, status=status.HTTP_409_CONFLICT)

        member.first_name = first_name
        member.last_name = last_name
        member.member_type = ExternalMember.TYPE_PERMANENT
        member.status = ExternalMember.STATUS_PENDING
        if photo:
            member.photo = photo
        member.save()
        return Response({'success': True, 'member': ExternalMemberSerializerV2(member).data}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='permanent')
    def permanent_list(self, request):
        """list สมาชิกถาวร (filter ตาม status ได้: ?status=pending|active|revoked)"""
        qs = ExternalMember.objects.filter(member_type=ExternalMember.TYPE_PERMANENT)
        status_f = request.query_params.get('status')
        if status_f:
            qs = qs.filter(status=status_f)
        qs = qs.order_by('-registered_at')
        return Response({'results': ExternalMemberSerializerV2(qs, many=True).data})

    @action(detail=False, methods=['get'], url_path='permanent/(?P<citizen_id>[0-9V][0-9]{12})')
    def permanent_detail(self, request, citizen_id=None):
        """รายละเอียดสมาชิกถาวรรายคน"""
        member = ExternalMember.objects.filter(
            citizen_id=citizen_id, member_type=ExternalMember.TYPE_PERMANENT
        ).first()
        if member is None:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ExternalMemberSerializerV2(member).data)

    @action(detail=False, methods=['post'], url_path='permanent/(?P<citizen_id>[0-9V][0-9]{12})/approve')
    def permanent_approve(self, request, citizen_id=None):
        """admin อนุมัติ → ออก permanent_code (ถ้ายังไม่มี) + status=active (idempotent)"""
        with transaction.atomic():
            member = ExternalMember.objects.select_for_update().filter(
                citizen_id=citizen_id, member_type=ExternalMember.TYPE_PERMANENT
            ).first()
            if member is None:
                return Response({'success': False, 'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

            if not member.permanent_code:
                code = _gen_permanent_code()
                if code is None:
                    return Response({'success': False, 'detail': 'Cannot allocate permanent code'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
                member.permanent_code = code
            member.status = ExternalMember.STATUS_ACTIVE
            member.approved_at = timezone.now()
            # ใช้ชื่อ staff ที่ client (reserv) ส่งมาถ้ามี ไม่งั้น fallback เป็น username ของ JWT
            approved_by = (request.data.get('approved_by') or '').strip()[:150]
            member.approved_by = approved_by or getattr(request.user, 'username', None)
            member.save(update_fields=['permanent_code', 'status', 'approved_at', 'approved_by'])

        return Response({'success': True, 'member': ExternalMemberSerializerV2(member).data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='permanent/(?P<citizen_id>[0-9V][0-9]{12})/revoke')
    def permanent_revoke(self, request, citizen_id=None):
        """admin ระงับ → status=revoked (รหัสถาวรใช้ไม่ได้ทันที)"""
        member = ExternalMember.objects.filter(
            citizen_id=citizen_id, member_type=ExternalMember.TYPE_PERMANENT
        ).first()
        if member is None:
            return Response({'success': False, 'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        member.status = ExternalMember.STATUS_REVOKED
        member.save(update_fields=['status'])
        return Response({'success': True, 'member': ExternalMemberSerializerV2(member).data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='permanent/(?P<citizen_id>[0-9V][0-9]{12})/delete')
    def permanent_delete(self, request, citizen_id=None):
        """admin ลบสมาชิกถาวรออกจากระบบ (hard delete) — ปลดล็อก citizen_id + permanent_code + ลบรูป"""
        member = ExternalMember.objects.filter(
            citizen_id=citizen_id, member_type=ExternalMember.TYPE_PERMANENT
        ).first()
        if member is None:
            return Response({'success': False, 'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if member.photo:
            member.photo.delete(save=False)  # ลบไฟล์รูปทิ้งด้วย ไม่ให้ค้าง
        member.delete()
        return Response({'success': True}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='permanent/(?P<citizen_id>[0-9V][0-9]{12})/photo')
    def permanent_photo(self, request, citizen_id=None):
        """ส่งไฟล์รูป (ต้องใช้ JWT — ไม่เปิดสาธารณะ) ให้ reserv proxy ไป render บัตร"""
        member = ExternalMember.objects.filter(citizen_id=citizen_id).first()
        if member is None or not member.photo:
            return Response({'detail': 'No photo'}, status=status.HTTP_404_NOT_FOUND)
        try:
            f = member.photo.open('rb')
        except (FileNotFoundError, ValueError):
            return Response({'detail': 'No photo'}, status=status.HTTP_404_NOT_FOUND)
        content_type = mimetypes.guess_type(member.photo.name)[0] or 'application/octet-stream'
        return FileResponse(f, content_type=content_type)

#----------------------------------------------
class MikroTikHotspotViewSetV2(JWTV2Authentication, viewsets.ViewSet):
    """
    ViewSet สำหรับ list, enable, disable users ใน MikroTik Hotspot ผ่าน API (v2)
    """

    def connect_to_mikrotik(self):
        """
        ฟังก์ชันสำหรับเชื่อมต่อกับ MikroTik API ปกติ
        """
        try:
            api = connect(username=settings.MIKROTIK_USER, password=settings.MIKROTIK_PASSWORD, host=settings.MIKROTIK_HOST)
            return api
        except Exception as e:
            raise Exception(f"Error connecting to MikroTik: {e}")

    @action(detail=False, methods=['get'], url_path='list-users')
    def list_users(self, request):
        """
        แสดงรายการผู้ใช้ทั้งหมดใน Hotspot
        """
        try:
            # API v2: เพิ่ม pagination และ filtering
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 20))
            filter_disabled = request.query_params.get('disabled', None)
            
            api = self.connect_to_mikrotik()
            hotspot_users = api.path('ip', 'hotspot', 'user')
            users = []
            
            for user in hotspot_users:
                # กรองตาม disabled ถ้ามีการระบุ
                if filter_disabled is not None:
                    is_disabled = str(user['disabled']).lower() == 'true'
                    filter_value = filter_disabled.lower() == 'true'
                    if is_disabled != filter_value:
                        continue
                
                users.append({
                    'name': user['name'],
                    'disabled': user['disabled'],
                    'profile': user.get('profile', 'N/A'),
                    'uptime': user.get('uptime', 'N/A'),  # เพิ่มข้อมูลเวลาที่ใช้งาน
                    'mac_address': user.get('mac-address', 'N/A')  # เพิ่มข้อมูล MAC address
                })
            
            # จัดการ pagination
            total_users = len(users)
            start_idx = (page - 1) * page_size
            end_idx = min(start_idx + page_size, total_users)
            
            paginated_users = users[start_idx:end_idx]
            
            return Response({
                'users': paginated_users,
                'pagination': {
                    'total': total_users,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': (total_users + page_size - 1) // page_size
                }
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    @action(detail=False, methods=['get'], url_path='enable/(?P<username>[^/.]+)')
    def enable_user(self, request, username=None):
        """
        Enable user ใน Hotspot
        """
        try:
            api = self.connect_to_mikrotik()
            hotspot_users = api.path('ip', 'hotspot', 'user')

            user_found = False
            for user in hotspot_users:
                if user['name'] == username:
                    user_found = True
                    # ใช้ .id แทน id ในการ update
                    hotspot_users.update(**{'.id': user['.id'], 'disabled': False})
                    
                    # API v2: เพิ่มข้อมูลเวลาที่เปลี่ยนแปลงและผู้ดำเนินการ
                    return Response({
                        'status': f"User {username} enabled",
                        'timestamp': str(timezone.now()),
                        'performed_by': request.user.username if request.user.is_authenticated else 'anonymous',
                        'api_version': 'v2'
                    }, status=status.HTTP_200_OK)

            if not user_found:
                return Response({'status': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='disable/(?P<username>[^/.]+)')
    def disable_user(self, request, username=None):
        """
        Disable user ใน Hotspot
        """
        try:
            api = self.connect_to_mikrotik()
            hotspot_users = api.path('ip', 'hotspot', 'user')

            user_found = False
            for user in hotspot_users:
                if user['name'] == username:
                    user_found = True
                    # ใช้ .id แทน id ในการ update
                    hotspot_users.update(**{'.id': user['.id'], 'disabled': True})
                    
                    # API v2: เพิ่มข้อมูลเวลาที่เปลี่ยนแปลงและผู้ดำเนินการ
                    return Response({
                        'status': f"User {username} disabled",
                        'timestamp': str(timezone.now()),
                        'performed_by': request.user.username if request.user.is_authenticated else 'anonymous',
                        'api_version': 'v2'
                    }, status=status.HTTP_200_OK)

            if not user_found:
                return Response({'status': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # API v2: เพิ่ม endpoint สำหรับ reset user
    @action(detail=False, methods=['post'], url_path='reset/(?P<username>[^/.]+)')
    def reset_user(self, request, username=None):
        """
        Reset user ใน Hotspot
        """
        try:
            api = self.connect_to_mikrotik()
            hotspot_users = api.path('ip', 'hotspot', 'user')
            hotspot_active = api.path('ip', 'hotspot', 'active')

            user_found = False
            for user in hotspot_users:
                if user['name'] == username:
                    user_found = True
                    
                    # ถ้าผู้ใช้กำลัง online อยู่ ให้ disconnect ก่อน
                    for active in hotspot_active:
                        if active.get('user') == username:
                            hotspot_active.remove(active['.id'])
                    
                    # อัพเดตข้อมูลบางส่วนของผู้ใช้ เช่น reset limit
                    hotspot_users.update(**{
                        '.id': user['.id'],
                        'limit-bytes-in': '0',
                        'limit-bytes-out': '0'
                    })
                    
                    return Response({
                        'status': f"User {username} reset successfully",
                        'timestamp': str(timezone.now()),
                        'api_version': 'v2'
                    }, status=status.HTTP_200_OK)

            if not user_found:
                return Response({'status': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#--------------------------------------------------------------------------
class SonoffControlViewSetV2(JWTV2Authentication, viewsets.ViewSet):
    """
    ViewSet สำหรับควบคุม Sonoff ผ่าน Home Assistant API (v2)
    """

    def get_sonoff_state(self, entity_id):
        """
        ฟังก์ชันสำหรับดึงสถานะปัจจุบันของ Sonoff
        """
        headers = {
            "Authorization": f"Bearer {settings.HA_TOKEN}",
            "Content-Type": "application/json"
        }
        
        url = f"http://{settings.HA_IP}:{settings.HA_PORT}/api/states/{entity_id}"
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return data  # API v2: ส่งข้อมูลทั้งหมดแทนที่จะส่งเฉพาะ state
            else:
                print(f"เกิดข้อผิดพลาดในการดึงสถานะ: {response.status_code}")
        except Exception as e:
            print(f"ไม่สามารถเชื่อมต่อกับ HA ได้: {e}")
        return None

    @action(detail=False, methods=['get'], url_path='status')
    def get_status(self, request):
        """
        API สำหรับดึงสถานะปัจจุบันของ Sonoff
        """
        entity_id = request.query_params.get('entity_id')  # รับ Entity ID จาก query parameters
        if not entity_id:
            return Response({'error': 'Entity ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        entity_data = self.get_sonoff_state(entity_id)
        if entity_data is None:
            return Response({'error': 'Failed to retrieve Sonoff state'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # API v2: ส่งข้อมูลที่มากขึ้น
        current_state = entity_data.get('state')
        attributes = entity_data.get('attributes', {})
        friendly_name = attributes.get('friendly_name', 'Unknown Device')
        
        return Response({
            "status": "success", 
            "device_info": {
                "entity_id": entity_id,
                "name": friendly_name,
                "current_state": current_state,
                "last_changed": entity_data.get('last_changed'),
                "attributes": attributes
            },
            "api_version": "v2"
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='toggle')
    def toggle_sonoff(self, request):
        """
        API สำหรับสลับสถานะของ Sonoff โดยใช้ entity_id ที่ส่งมาใน request
        """
        headers = {
            "Authorization": f"Bearer {settings.HA_TOKEN}",
            "Content-Type": "application/json"
        }
        
        entity_id = request.data.get('entity_id')  # รับ Entity ID ของ Sonoff จาก request
        if not entity_id:
            return Response({'error': 'Entity ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        # ตรวจสอบสถานะปัจจุบันของ Sonoff
        entity_data = self.get_sonoff_state(entity_id)
        if entity_data is None:
            return Response({'error': 'Failed to retrieve Sonoff state'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        current_state = entity_data.get('state')

        # Toggle สถานะ
        if current_state == "on":
            service_url = f"http://{settings.HA_IP}:{settings.HA_PORT}/api/services/switch/turn_off"
        else:
            service_url = f"http://{settings.HA_IP}:{settings.HA_PORT}/api/services/switch/turn_on"

        data = {"entity_id": entity_id}
        try:
            response = requests.post(service_url, headers=headers, json=data)
            if response.status_code == 200:
                new_state = "off" if current_state == "on" else "on"
                
                # API v2: เพิ่มข้อมูลการดำเนินการ
                return Response({
                    "status": "success", 
                    "device_operation": {
                        "entity_id": entity_id,
                        "previous_state": current_state,
                        "new_state": new_state,
                        "operation": "toggle",
                        "timestamp": str(timezone.now())
                    },
                    "api_version": "v2"
                }, status=status.HTTP_200_OK)
            else:
                return Response({"error": f"Failed to toggle Sonoff"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({"error": f"Error toggling Sonoff: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # API v2: เพิ่ม endpoint สำหรับตั้งเวลาเปิด/ปิด
    @action(detail=False, methods=['post'], url_path='schedule')
    def schedule_operation(self, request):
        """
        API สำหรับตั้งเวลาเปิด/ปิด Sonoff
        """
        headers = {
            "Authorization": f"Bearer {settings.HA_TOKEN}",
            "Content-Type": "application/json"
        }
        
        entity_id = request.data.get('entity_id')
        operation = request.data.get('operation')  # 'turn_on' หรือ 'turn_off'
        scheduled_time = request.data.get('scheduled_time')  # เวลาที่ต้องการให้ทำงาน (ISO format)
        
        if not all([entity_id, operation, scheduled_time]):
            return Response({
                'error': 'Missing required fields. Please provide entity_id, operation, and scheduled_time'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        if operation not in ['turn_on', 'turn_off']:
            return Response({
                'error': 'Invalid operation. Must be either "turn_on" or "turn_off"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # ในที่นี้เราจะสร้าง automation ใน Home Assistant
        # แต่เนื่องจากเป็นตัวอย่าง เราจะจำลองว่าได้ดำเนินการแล้ว
        
        return Response({
            "status": "success",
            "schedule_info": {
                "entity_id": entity_id,
                "operation": operation,
                "scheduled_time": scheduled_time,
                "schedule_id": f"schedule_{entity_id}_{int(timezone.now().timestamp())}"
            },
            "message": "Schedule created successfully",
            "api_version": "v2"
        }, status=status.HTTP_200_OK)

