from ldap3 import Server, Connection, ALL, NTLM
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
import requests
from django.conf import settings
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from urllib.parse import urlparse, parse_qs

# ข้อมูลการเชื่อมต่อกับ AD
server_name = '10.0.3.12'
domain_name = 'NPU.local'
api_url = "https://api.npu.ac.th/api/"

# เพิ่มการแมปชื่อห้อง
ROOM_NAMES = {
    1: "ห้อง Mini Theater",
    2: "โซน Netflix",
    3: "ห้อง Journal"
}

# ข้อมูลอุปกรณ์ในแต่ละห้อง
ROOM_DEVICES = {
    1: [  # room_mini  
        {"name": "ประตู", "entity_id": "switch.sonoff_1001f20182"},
        {"name": "ระบบแสงสว่าง", "entity_id": "switch.sonoff_1002115f1a"},
        {"name": "ระบบเสียง", "entity_id": "switch.sonoff_10021888d9_1"},
        {"name": "โปรเจ็คเตอร์", "entity_id": "switch.sonoff_1000bff56b"},   
        {"name": "เครื่องปรับอากาศ", "entity_id": "switch.sonoff_100211915b"},
        
    ],
    2: [  # room_netflix
        {"name": "ทีวีและปลั๊ก", "entity_id": "switch.sonoff_1001f579cb"}
    ],
    3: [  # room_journal
        {"name": "ทีวีและปลั๊ก", "entity_id": "switch.sonoff_10021861bd_1"},
    ]
}

# เชื่อมโยง room_id กับ Google Sheet URL
sheet_urls = {
        # Mini theater Room
        "1": "https://docs.google.com/spreadsheets/d/1LnhtWElm50PdQp4filiqNAgIJOnDUSS4pHgmW_J40s8/edit?gid=0#gid=0",
        # "1": "https://docs.google.com/spreadsheets/d/1jDI5vQ_1Zw7M7QkNMtUgGUmD5av4rZzj5NXEUUPiu2A/edit?gid=0#gid=0",

        # Netflix Zone
        "2": "https://docs.google.com/spreadsheets/d/1uluAqFI8-fR7ZA8bQIJ1KHI30nTZShUVh5yBXD8JKkg/edit?gid=0#gid=0",
        # "2": "https://docs.google.com/spreadsheets/d/1pbneBdRwfNEWTE5C37V15W2yhC_llqrPsxuJi0jvTLc/edit?gid=0#gid=0",

        # journal Zone
        "3": "https://docs.google.com/spreadsheets/d/1clLVM7zPoqHPDmioNBkjkFA2dW79om1TpWS2A4m1mPc/edit?gid=0#gid=0",
        # "3": "https://docs.google.com/spreadsheets/d/19HDhW-XfXulfYCaRdt9jKG0t1oYRCsbg82XoaKTGw4Q/edit?gid=0#gid=0",
        # เพิ่ม URL ของ Google Sheet สำหรับ room_id อื่นๆ ได้ที่นี่
}

def line_oa_home(request):
    return render(request, 'reservapp/home_oa.html')

def home(request):
    if request.method == 'POST':
        # รับค่า userId, displayName, pictureUrl และ page จาก POST request
        userId = request.POST.get('userId')
        displayName = request.POST.get('displayName')
        pictureUrl = request.POST.get('pictureUrl')
        page = request.POST.get('page')  # รับพารามิเตอร์ page

        # ตรวจสอบว่าค่าของ page ได้รับหรือไม่ และพิมพ์ค่า page ลงใน console ถ้ามี
        if page:
            print(f"Page: {page}")
            request.session['page'] = page  # เซ็ต session สำหรับ page เฉพาะเมื่อ page มีค่า

        # เซ็ต session สำหรับทั้ง 3 พารามิเตอร์
        request.session['userId'] = userId
        request.session['displayName'] = displayName
        request.session['pictureUrl'] = pictureUrl

        # Redirect ไปหน้า welcome
        return redirect('welcome')

    return render(request, 'reservapp/home.html')


def login(request):
    if request.method == 'POST':
        userLdap = request.POST.get('userLdap')
        passLdap = request.POST.get('passLdap')
        user_type = request.POST.get('user_type')  # ดึงค่าประเภทผู้ใช้งาน
        userId = request.session.get('userId', '')  # รับค่า userId จาก session

        # ทำการตรวจสอบ userLdap และ passLdap กับ Active Directory
        is_valid, ldap_info = check_user_in_ad(userLdap, passLdap)

        if is_valid:
            # ส่งข้อมูลไปยัง API
            data = {
                'userId': userId,
                'userLdap': userLdap,
                'user_type': user_type
            }
            response = requests.post(api_url, json=data)

            if response.status_code in [200, 201]:  # ตรวจสอบทั้งสถานะ 200 และ 201
                 # หาก POST สำเร็จ แสดงข้อความลงทะเบียนเรียบร้อยแล้ว และปิดหน้าต่าง
                success_message = "ลงทะเบียนเรียบร้อยแล้ว หน้าต่างจะปิดใน 3 วินาที"
                return render(request, 'reservapp/home.html')
            else:
                # หากเกิดข้อผิดพลาดจาก API
                error_message = f"ไม่สามารถบันทึกข้อมูลได้: {response.status_code}"
                return render(request, 'reservapp/login.html', {'error_message': error_message})

        else:
            # ถ้าตรวจสอบไม่สำเร็จ แสดง error
            error_message = "ไม่พบข้อมูลในระบบ LDAP หรือข้อมูลไม่ถูกต้อง"
            return render(request, 'reservapp/login.html', {'error_message': error_message})

    return render(request, 'reservapp/login.html')


def check_user_in_ad(userLdap, passLdap):
    try:
        # สร้างการเชื่อมต่อไปยัง AD
        server = Server(server_name, get_info=ALL)
        conn = Connection(server, user=f'{domain_name}\\{userLdap}', password=passLdap, authentication=NTLM, auto_bind=True)

        if conn.bind():
            # ถ้าการเชื่อมต่อสำเร็จ ดึงข้อมูลจาก AD
            conn.search(f'dc={domain_name.split(".")[0]},dc={domain_name.split(".")[1]}', f'(sAMAccountName={userLdap})', attributes=['displayName', 'mail'])
            
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
    
def welcome(request):
    if 'userId' in request.session:
        userId = request.session['userId']
        displayName = request.session.get('displayName', 'Guest')
        pictureUrl = request.session.get('pictureUrl', '')
        page = request.session.get('page', '')  # รับค่า page จาก session

        # เช็คข้อมูล userId กับ API
        user_exists, user_ldap, user_info, user_type, is_walai_member = check_user_in_api(userId)

        if user_exists and user_ldap:
            return render(request, 'reservapp/welcome.html', {
                'userId': userId,
                'displayName': displayName,
                'pictureUrl': pictureUrl,
                'page': page,  # ส่งค่า page ไปยัง template
                'userLdap': user_ldap,
                'user_info': user_info,
                'user_type': user_type,
                'is_walai_member': is_walai_member  # ส่งผลการเป็นสมาชิก Walai
            })
        else:
            return redirect('login')  # ถ้าไม่พบข้อมูลใน API ให้กลับไปหน้า login
    else:
        return redirect('login')


    
# ฟังก์ชันสำหรับเช็คข้อมูล userId กับ API
def check_user_in_api(userId):
    # API URL สำหรับเช็คข้อมูลของ userId
    api_url = f"https://api.npu.ac.th/api/{userId}"

    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            user_type = data.get('user_type')
            user_ldap = data.get('userLdap')
            
            if user_type == "นักศึกษา":
                student_info = get_user_info_from_api(user_ldap)
                is_walai_member = check_walai_membership(user_ldap)  # เช็คสมาชิก Walai
                return True, user_ldap, student_info, user_type, is_walai_member
            
            elif user_type == "บุคลากรภายในมหาวิทยาลัย":
                staff_info = get_staff_info_from_api(user_ldap)
                is_walai_member = check_walai_membership(user_ldap)  # เช็คสมาชิก Walai
                return True, user_ldap, staff_info, user_type, is_walai_member
            
            else:
                return False, None, None, None, None
        else:
            print(f"API returned non-200 status: {response.status_code}")
            return False, None, None, None, None

    except requests.RequestException as e:
        print(f"Error fetching data from API: {e}")
        return False, None, None, None, None
    

# ฟังก์ชันสำหรับดึงข้อมูล userLdap จาก API ที่สอง
def get_user_info_from_api(user_ldap):
    api_url = f"https://api.npu.ac.th/std-info/{user_ldap}/"
    try:
        # ทำการเรียก API ด้วย GET request
        response = requests.get(api_url)
        if response.status_code == 200:
            return response.json()  # แปลงการตอบกลับเป็น JSON
        else:
            print(f"API returned non-200 status: {response.status_code}")
            return None
    except requests.RequestException as e:
        print(f"Error fetching data from API: {e}")
        return None

def get_staff_info_from_api(user_ldap):
    api_url = f"https://api.npu.ac.th/staff-info/{user_ldap}"
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            return response.json()  # แปลงการตอบกลับเป็น JSON
        else:
            print(f"API returned non-200 status: {response.status_code}")
            return None
    except requests.RequestException as e:
        print(f"Error fetching data from API: {e}")
        return None


def check_walai_membership(user_ldap):
    walai_url = f"https://api.npu.ac.th/walai/check_user_walai/{user_ldap}"
    headers = {
        'token': '3YhnCZzmyr+8HELDMzufoZ6vccyK1KIoAl30SdYhoFLJD8pRV8emesbLSSya2/NgtjY1dMaqzvClDSHFzF4B3A=='
    }
    
    try:
        response = requests.get(walai_url, headers=headers)
        if response.status_code == 200:
            # แปลงการตอบกลับเป็น JSON
            data = response.json()
            
            # ตรวจสอบว่า response เป็น list หรือไม่
            if isinstance(data, list):
                # ถ้าเป็น list, ตรวจสอบสมาชิกจากข้อมูลที่ส่งกลับมา
                # สมมุติว่าเราตรวจสอบจาก key หรือค่าบางอย่างใน list
                # ตัวอย่าง: ตรวจสอบว่า list มี length มากกว่า 0 ถือว่าผู้ใช้เป็นสมาชิก
                return len(data) > 0
            else:
                # กรณี response ไม่ได้เป็น list (รองรับทั้งกรณี dict)
                return data.get('is_member', False)  # คืนค่า True ถ้าเป็นสมาชิก, False ถ้าไม่ใช่
        else:
            print(f"Walai API returned non-200 status: {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"Error fetching data from Walai API: {e}")
        return False


# ฟังก์ชันสำหรับลบ session
def logout(request):
    try:
        del request.session['userId']
    except KeyError:
        pass
    return redirect('home')


# ฟังก์ชันใหม่สำหรับแสดงรายการห้อง
def room_list_view(request):
    rooms = [
        {"name": "ห้อง Mini Theater", "id": 1},
        {"name": "โซน Netflix", "id": 2},
        {"name": "ห้อง Journal", "id": 3},
    ]
    return render(request, 'reservapp/room_list.html', {'rooms': rooms})

# ฟังก์ชันใหม่สำหรับแสดงอุปกรณ์และควบคุมในแต่ละห้อง
def get_room_id_and_user_id_from_url(url):
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.split('/')
    room_id = path_parts[-2]
    query_params = parse_qs(parsed_url.query)
    user_id = query_params.get("userId", [None])[0]
    return room_id, user_id

def room_control_view(request, room_id):
    user_id = request.GET.get('userId')
    if not user_id:
        return HttpResponse("ไม่พบ userId ใน URL", status=400)

    # ตรวจสอบว่า room_id มี Google Sheet ที่สอดคล้อง
    sheet_url = sheet_urls.get(str(room_id))
    if not sheet_url:
        return HttpResponse(f"ไม่มี Google Sheet ที่ตรงกับ room_id: {room_id}", status=404)

    room_name = ROOM_NAMES.get(int(room_id), "Unknown Room")

    # ตั้งค่า Google Sheets API และตรวจสอบสิทธิ์การเข้าถึง
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file('c:/inetpub/wwwroot/NPUAPI/apiproject/control-room-440116-eda428ec17d3.json', scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_url(sheet_url)
    worksheet = sheet.get_worksheet(0)

    def check_access(user_data):
        current_time = datetime.now().time()  # เวลาปัจจุบัน
        for record in user_data:
            # ตรวจสอบว่า 'เวลาเข้า' และ 'เวลาออก' มีอยู่ในข้อมูลหรือไม่
            check_in_time = datetime.strptime(record['เวลาเข้า'], "%H:%M").time()
            check_out_time = datetime.strptime(record['เวลาออก'], "%H:%M").time()
            # ตรวจสอบว่าเวลาปัจจุบันอยู่ในช่วงเวลาการจองหรือไม่
            if check_in_time <= current_time <= check_out_time:
                return True  # อนุญาตการเข้าถึง
        return False  # ปฏิเสธการเข้าถึง

    # ดึงข้อมูลผู้ใช้งานจาก Google Sheet
    def get_user_data(user_id):
        date = datetime.now().strftime("%Y-%m-%d")
        records = worksheet.get_all_records()
        user_data = [
            row for row in records
            if row.get("UserID") == user_id and row.get("วันที่") == date
        ]
        return user_data

    data = get_user_data(user_id)
    if data:
        time_start = data[0].get('เวลาเข้า')
        time_end = data[0].get('เวลาออก')
        display_name = data[0].get('displayname', 'Unknown User')  # ดึง displayName จาก Google Sheet
        access_granted = check_access(data)
    else:
        time_start, time_end = None, None
        display_name = 'Unknown User'
        access_granted = False

    if access_granted:
        devices = ROOM_DEVICES.get(int(room_id), [])
        return render(request, 'reservapp/room_control.html', {
            'devices': devices,
            'room_id': room_id,
            'room_name': room_name,
            'user_name': display_name,  # ส่งค่า display_name ไปที่ template
            'time_start': time_start,
            'time_end': time_end
        })
    else:
        context = {
            'room_name': room_name,
            'time_start': time_start,
            'time_end': time_end,
            'error_message': 'ไม่อยู่ในช่วงเวลาที่ท่านได้ทำการจองไว้',
            'user_name': display_name,
            'user_type': data[0].get('user_type') if data else None,  # เพิ่มประเภทผู้ใช้
            'user_ldap': data[0].get('user_ldap') if data else None,  # เพิ่มรหัสผู้ใช้
        }
        return render(request, 'reservapp/error_access.html', context, status=403)
