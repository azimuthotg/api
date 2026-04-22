# apiproject/apiapp/views.py
from librouteros import connect
from apiapp.models import UserProfile,StudentsInfo,StaffInfo
from apiapp.serializer import UserProfileSerializer,StudentsInfoSerializer,StaffInfoSerializer
from rest_framework import viewsets , status
#-------------------------------------------
from rest_framework.response import Response
from ldap3 import Server, Connection, ALL,NTLM
from rest_framework.decorators import action,api_view
import requests
from django.conf import settings  # เพิ่มบรรทัดนี้
from django.http import HttpResponse



# ลบการประกาศตัวแปรเหล่านี้
# ข้อมูลการเชื่อมต่อกับ AD
# LDAP_SERVER = '10.0.3.12'  # แทนที่ด้วย IP ของ AD server
# DOMAIN_NAME = 'NPU.local'  # แทนที่ด้วย Domain ของคุณ
#----------------------------------------------
# ข้อมูลการเชื่อมต่อกับ MikroTik
# MIKROTIK_HOST = '202.29.55.180'  # แทนที่ด้วย IP ของ MikroTik
# MIKROTIK_USER = 'admin_e'  # แทนที่ด้วยชื่อผู้ใช้ MikroTik
# MIKROTIK_PASSWORD = '41132834@ake@1'  # แทนที่ด้วยรหัสผ่านของ MikroTik
#----------------------------------------------

class userViewset(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    lookup_field = 'userId'

class StudentsInfoViewset(viewsets.ModelViewSet):
    queryset = StudentsInfo.objects.all()
    serializer_class = StudentsInfoSerializer
    lookup_field = 'student_code'

class StaffInfoViewSet(viewsets.ModelViewSet):
    queryset = StaffInfo.objects.all()
    serializer_class = StaffInfoSerializer
    lookup_field = 'staffcitizenid'


@api_view(['GET'])
def restricted_api_root(request, format=None):
    return Response(status=403)

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
class LDAPAuthViewSet(viewsets.ViewSet):

    @action(detail=False, methods=['post'])
    def auth_ldap(self, request):
        user_ldap = request.data.get('userLdap')
        pass_ldap = request.data.get('passLdap')

        if not user_ldap or not pass_ldap:
            return Response({'detail': 'Missing userLdap or passLdap'}, status=status.HTTP_400_BAD_REQUEST)

        # เรียกใช้ฟังก์ชันตรวจสอบ AD
        success, ldap_info = check_user_in_ad(user_ldap, pass_ldap)

        if success:
            return Response({'success': True, 'ldap_info': ldap_info}, status=status.HTTP_200_OK)
        else:
            return Response({'success': False, 'detail': 'Invalid credentials or user not found in AD'}, status=status.HTTP_401_UNAUTHORIZED)

    @action(detail=False, methods=['post'])
    def auth_and_get_student(self, request):
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
                serializer = StudentsInfoSerializer(student_info)
                return Response({'success': True, 'student_info': serializer.data}, status=status.HTTP_200_OK)
            except StudentsInfo.DoesNotExist:
                return Response({'success': False, 'detail': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({'success': False, 'detail': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        

#---------------------------------------------
class WalaiCheckUserViewSet(viewsets.ViewSet):
    
    # เปลี่ยนชื่อฟังก์ชันเป็น check_user_walai
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
                return Response(data, status=status.HTTP_200_OK)
            else:
                # กรณีที่ API ตอบกลับด้วย status code ที่ไม่ใช่ 200
                return Response({"error": f"Failed to retrieve data. Status code: {response.status_code}"}, status=response.status_code)
        
        except requests.RequestException as e:
            # กรณีที่มีข้อผิดพลาดในการเชื่อมต่อกับ API
            return Response({"error": f"Error fetching data from API: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#----------------------------------------------
class MikroTikHotspotViewSet(viewsets.ViewSet):
    """
    ViewSet สำหรับ list, enable, disable users ใน MikroTik Hotspot ผ่าน API
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
            api = self.connect_to_mikrotik()
            hotspot_users = api.path('ip', 'hotspot', 'user')
            users = []
            for user in hotspot_users:
                users.append({
                    'name': user['name'],
                    'disabled': user['disabled'],
                    'profile': user.get('profile', 'N/A')
                })
            return Response({'users': users}, status=status.HTTP_200_OK)
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
                    return Response({'status': f"User {username} enabled"}, status=status.HTTP_200_OK)

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
                    return Response({'status': f"User {username} disabled"}, status=status.HTTP_200_OK)

            if not user_found:
                return Response({'status': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#--------------------------------------------------------------------------
# ลบการประกาศตัวแปรเหล่านี้
# ตั้งค่าข้อมูล Home Assistant
# HA_IP = "202.29.55.30"  # IP ภายนอกของ Mikrotik
# HA_PORT = 8123          # Port ของ Home Assistant (8123 โดยปกติ)
# HA_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI1MTA4ZWRmNTU3Yzc0MjA2OTM4Njk3YjU0YTM3NDlmMCIsImlhdCI6MTcyOTk1NDMwMywiZXhwIjoyMDQ1MzE0MzAzfQ.0089Kp8tiXkkVGRweVRyD-pmXdRlJAlsXvyLOCopb7I"  # ใส่ Token ของ Home Assistant

# ลบการประกาศตัวแปร headers ที่ใช้ค่าคงที่
# headers = {
#     "Authorization": f"Bearer {HA_TOKEN}",
#     "Content-Type": "application/json"
# }

class SonoffControlViewSet(viewsets.ViewSet):
    """
    ViewSet สำหรับควบคุม Sonoff ผ่าน Home Assistant API
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
                return response.json().get("state")
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

        current_state = self.get_sonoff_state(entity_id)
        if current_state is None:
            return Response({'error': 'Failed to retrieve Sonoff state'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"status": "success", "current_state": current_state}, status=status.HTTP_200_OK)


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
        current_state = self.get_sonoff_state(entity_id)
        if current_state is None:
            return Response({'error': 'Failed to retrieve Sonoff state'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
                return Response({"status": "success", "new_state": new_state}, status=status.HTTP_200_OK)
            else:
                return Response({"error": f"Failed to toggle Sonoff"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({"error": f"Error toggling Sonoff: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)