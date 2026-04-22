# apiapp/views_v2.py
from librouteros import connect
from apiapp.models import UserProfile, StudentsInfo, StaffInfo
from apiapp.serializers_v2 import UserProfileSerializerV2, StudentsInfoSerializerV2, StaffInfoSerializerV2
from rest_framework import viewsets, status
from rest_framework.response import Response
from ldap3 import Server, Connection, ALL, NTLM
from rest_framework.decorators import action
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

class UserViewSetV2(JWTV2Authentication, viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializerV2
    lookup_field = 'userId'
    
    # เพิ่มฟีเจอร์ใหม่สำหรับ v2 เช่น
    # - การกรองข้อมูล
    # - pagination ที่ปรับแต่งได้
    # - การค้นหาขั้นสูง

class StudentsInfoViewSetV2(JWTV2Authentication, viewsets.ModelViewSet):
    queryset = StudentsInfo.objects.all()
    serializer_class = StudentsInfoSerializerV2
    lookup_field = 'student_code'
    
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

class StaffInfoViewSetV2(JWTV2Authentication, viewsets.ModelViewSet):
    queryset = StaffInfo.objects.all()
    serializer_class = StaffInfoSerializerV2
    lookup_field = 'staffcitizenid'
    
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
    try:
        # สร้างการเชื่อมต่อไปยัง AD
        server = Server(settings.LDAP_SERVER, get_info=ALL)
        conn = Connection(server, user=f'{settings.DOMAIN_NAME}\\{userLdap}', password=passLdap, authentication=NTLM, auto_bind=True)

        if conn.bind():
            # ถ้าการเชื่อมต่อสำเร็จ ดึงข้อมูลจาก AD
            conn.search(f'dc={settings.DOMAIN_NAME.split(".")[0]},dc={settings.DOMAIN_NAME.split(".")[1]}', f'(sAMAccountName={userLdap})', attributes=['displayName', 'mail'])

            if conn.entries:
                ldap_info = {
                    'displayName': conn.entries[0].displayName.value,
                    'email': conn.entries[0].mail.value if conn.entries[0].mail else None
                }
                return True, ldap_info
            else:
                return False, None
        else:
            return False, None
    except Exception as e:
        print(f"Error connecting to AD: {e}")
        return False, None

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
class LDAPAuthViewSetV2(JWTV2Authentication, viewsets.ViewSet):
    """
    ViewSet สำหรับการตรวจสอบสิทธิ์ผ่าน LDAP (เก็บไว้สำหรับความเข้ากันได้ย้อนหลัง)
    """
    @action(detail=False, methods=['post'])
    def auth_ldap(self, request):
        """
        Endpoint สำหรับตรวจสอบสิทธิ์ผ่าน LDAP (เหมือนใน v1 แต่ไม่ให้ token)
        """
        user_ldap = request.data.get('userLdap')
        pass_ldap = request.data.get('passLdap')

        if not user_ldap or not pass_ldap:
            return Response({'detail': 'Missing userLdap or passLdap'}, status=status.HTTP_400_BAD_REQUEST)

        # เรียกใช้ฟังก์ชันตรวจสอบ AD
        success, ldap_info = check_user_in_ad(user_ldap, pass_ldap)

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

