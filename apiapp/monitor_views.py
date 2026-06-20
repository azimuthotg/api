"""หน้า Monitor การผูกบัญชี (LINE UID + LDAP)

เข้าถึงด้วยรหัสผ่านร่วมแบบง่าย (settings.MONITOR_PASSWORD) — สำหรับบรรณารักษ์
เคาน์เตอร์ดูกิจกรรมการผูกบัญชี สำเร็จ/ไม่สำเร็จ พร้อมสาเหตุ เพื่อนำ error ไปแจ้งทีมคอม
"""
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apiapp.models import BindingLog, TokenIssueLog, ApiAccessLog, ApiAccessArchive
from apiapp.monitoring import check_ad_detailed, get_ad_user_attributes
from apiapp.token_utils import decode_token

SESSION_KEY = 'monitor_authed'

# ป้ายแสดงผล reason_code เป็นภาษาคนสำหรับเจ้าหน้าที่หน้างาน
REASON_LABELS = {
    'ok': 'สำเร็จ',
    'invalid_credentials': 'รหัสผ่านไม่ถูกต้อง / ไม่มีบัญชีใน AD',
    'not_in_ad': 'ไม่พบบัญชีใน AD',
    'account_locked': 'บัญชีถูกล็อก (กรอกผิดหลายครั้ง)',
    'account_disabled': 'บัญชีถูกปิดใช้งาน',
    'password_expired': 'รหัสผ่านหมดอายุ',
    'must_reset_password': 'ต้องเปลี่ยนรหัสก่อนใช้งาน',
    'account_expired': 'บัญชีหมดอายุ',
    'ad_denied': 'AD ไม่อนุญาต (เวลา/เครื่อง)',
    'ad_error': 'เชื่อมต่อ AD ไม่ได้ (network/AD ล่ม)',
    'db_not_found': 'ไม่พบข้อมูลในฐานข้อมูล',
    'missing_input': 'กรอกข้อมูลไม่ครบ',
    'bind_error': 'บันทึกการผูกบัญชีไม่สำเร็จ (เช่น ผูกซ้ำ)',
}

# ป้ายแสดงผลขั้นตอน (event)
EVENT_LABELS = {
    'ldap_auth': '1. ตรวจรหัส (AD)',
    'bind': '2. ผูกบัญชี',
}

# ป้ายตาม HTTP-based reason_code (สำหรับ ApiAccessLog ที่ไม่มีสาเหตุ AD)
ACCESS_REASON_LABELS = {
    'ok': 'สำเร็จ',
    'unauthorized': 'ไม่ได้ส่ง token หรือ token ไม่ถูกต้อง',
    'forbidden': 'ไม่มีสิทธิ์เรียก endpoint นี้',
    'not_found': 'ไม่พบข้อมูล',
    'bad_request': 'ส่งข้อมูลไม่ครบ/ไม่ถูกต้อง',
    'method_not_allowed': 'เรียกผิดวิธี (HTTP method)',
    'too_many_requests': 'เรียกถี่เกินไป',
    'server_error': 'เซิร์ฟเวอร์ผิดพลาด',
}

# แปลข้อความ (detail) เฉพาะที่ endpoint ส่งมา → คำอธิบายไทยกระชับชัดเจน
ACCESS_MESSAGE_LABELS = {
    'Personnel not found': 'ผ่าน AD แล้ว แต่ไม่พบในฐานข้อมูลบุคลากร',
    'Student not found': 'ผ่าน AD แล้ว แต่ไม่พบในฐานข้อมูลนักศึกษา',
    'Invalid credentials': 'รหัสผ่านไม่ถูกต้อง หรือไม่มีบัญชีใน AD',
    'Invalid credentials or user not found in AD': 'รหัสผ่านไม่ถูกต้อง หรือไม่มีบัญชีใน AD',
    'Missing userLdap or passLdap': 'ส่งข้อมูลไม่ครบ (ไม่มี username/password)',
    'Missing username or password': 'ส่งข้อมูลไม่ครบ (ไม่มี username/password)',
}


def _access_explain(log):
    """คำอธิบายสาเหตุไทยกระชับสำหรับ 1 แถวของ ApiAccessLog (ไล่จากเจาะจงสุด)"""
    # 1) สาเหตุ AD ละเอียด (จาก auth_ldap) มีใน REASON_LABELS อยู่แล้ว เช่น บัญชีถูกล็อก
    if log.reason_code in REASON_LABELS:
        return REASON_LABELS[log.reason_code]
    # 2) ข้อความเฉพาะจาก endpoint เช่น Personnel not found
    if log.message and log.message in ACCESS_MESSAGE_LABELS:
        return ACCESS_MESSAGE_LABELS[log.message]
    # 3) ตาม HTTP status
    if log.reason_code in ACCESS_REASON_LABELS:
        return ACCESS_REASON_LABELS[log.reason_code]
    return log.reason_code or '-'


def _is_authed(request):
    return request.session.get(SESSION_KEY) is True


@require_http_methods(["GET", "POST"])
def monitor_login(request):
    if _is_authed(request):
        return redirect('monitor_dashboard')

    if request.method == 'POST':
        password = request.POST.get('password', '')
        if password == settings.MONITOR_PASSWORD:
            request.session[SESSION_KEY] = True
            return redirect('monitor_dashboard')
        messages.error(request, 'รหัสผ่านไม่ถูกต้อง')

    return render(request, 'monitor/login.html')


def monitor_logout(request):
    request.session.pop(SESSION_KEY, None)
    return redirect('monitor_login')


@require_http_methods(["GET", "POST"])
def monitor_adtest(request):
    """หน้าทดสอบ login กับ AD สำหรับเจ้าหน้าที่หน้างาน

    กรอก username + password แล้วยิงตรงไป AD ทันที เห็นผลว่าผ่าน/ไม่ผ่าน + สาเหตุ
    (ถ้ารหัสถูกแต่บัญชีมีปัญหา จะเห็น code จริง เช่น ถูกปิด/รหัสหมดอายุ)
    ไม่บันทึกลง BindingLog — เป็นเครื่องมือทดสอบเฉยๆ
    """
    if not _is_authed(request):
        return redirect('monitor_login')

    result = None
    username = ''
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        if not username or not password:
            result = {'error': 'กรุณากรอก username และ password ให้ครบ'}
        else:
            success, info, reason_code, message = check_ad_detailed(username, password)
            result = {
                'success': success,
                'reason_code': reason_code,
                'reason_label': REASON_LABELS.get(reason_code, reason_code),
                'message': message,
                'info': info,
            }
            # ถ้ารหัสผ่าน + ติ๊ก "ดึง attribute ทั้งหมด" -> ดึงทุก attribute มาช่วย diagnose
            # ว่ามีตัวไหน map กับ staff_info (staffid / staffcitizenid) ได้
            if success and request.POST.get('dump_attrs'):
                ok, attrs, attr_msg = get_ad_user_attributes(username, password)
                result['ad_attributes'] = attrs if ok else None
                result['ad_attributes_msg'] = attr_msg

    return render(request, 'monitor/adtest.html', {'result': result, 'username': username})


# เกณฑ์เตือน "ใกล้หมดอายุ" (วัน)
TOKEN_SOON_DAYS = 30


def _token_status(expires_at):
    """คืน (status_code, days_left) สำหรับ token: expired / soon / ok / unknown"""
    if expires_at is None:
        return 'unknown', None
    now = timezone.now()
    days_left = (expires_at - now).days
    if expires_at <= now:
        return 'expired', days_left
    if days_left <= TOKEN_SOON_DAYS:
        return 'soon', days_left
    return 'ok', days_left


@require_http_methods(["GET", "POST"])
def monitor_token_inspect(request):
    """วาง JWT แล้วดูว่าเป็นของ user ไหน / ออกเมื่อไหร่ / หมดเมื่อไหร่ / เหลือกี่วัน

    decode แบบตรวจ signature แต่ไม่เช็ค exp — จึงดู token ที่หมดอายุไปแล้วได้
    (ช่วยวินิจฉัยเวลาระบบล่มเพราะ token หมด)
    """
    if not _is_authed(request):
        return redirect('monitor_login')

    result = None
    token = ''
    if request.method == 'POST':
        token = request.POST.get('token', '').strip()
        info = decode_token(token)
        if info.get('valid'):
            status_code, days_left = _token_status(info.get('expires_at'))
            info['status_code'] = status_code
            info['days_left'] = days_left
            info['overdue_days'] = abs(days_left) if days_left is not None and days_left < 0 else None
        result = info

    return render(request, 'monitor/token_inspect.html', {'result': result, 'token': token})


def monitor_token_log(request):
    """Dashboard token ที่ออกไป — สรุป 'token ล่าสุดของแต่ละ user หมดเมื่อไหร่'

    เรียงตามใกล้หมดก่อน เพื่อให้เห็นว่าระบบไหนกำลังจะล่มก่อน
    """
    if not _is_authed(request):
        return redirect('monitor_login')

    # ---- สรุป token ล่าสุดต่อ user (ระบบที่ login ด้วย username เดียวกัน) ----
    usernames = (
        TokenIssueLog.objects.exclude(username__isnull=True)
        .exclude(username='')
        .values_list('username', flat=True)
        .distinct()
    )
    latest_per_user = []
    for u in usernames:
        row = TokenIssueLog.objects.filter(username=u).order_by('-created_at').first()
        if row is None:
            continue
        status_code, days_left = _token_status(row.expires_at)
        latest_per_user.append({
            'username': u,
            'event': row.get_event_display(),
            'issued_at': row.issued_at,
            'expires_at': row.expires_at,
            'ip_address': row.ip_address,
            'status_code': status_code,
            'days_left': days_left,
            'overdue_days': abs(days_left) if days_left is not None and days_left < 0 else None,
        })
    # เรียง: หมดแล้ว/ใกล้หมดก่อน (วันเหลือน้อยขึ้นก่อน), unknown ไปท้าย
    latest_per_user.sort(key=lambda r: (r['days_left'] is None, r['days_left'] if r['days_left'] is not None else 0))

    summary = {
        'users_total': len(latest_per_user),
        'users_expired': sum(1 for r in latest_per_user if r['status_code'] == 'expired'),
        'users_soon': sum(1 for r in latest_per_user if r['status_code'] == 'soon'),
        'issues_total': TokenIssueLog.objects.count(),
    }

    # ---- รายการออก token ทั้งหมด (กรอง + แบ่งหน้า) ----
    qs = TokenIssueLog.objects.all()
    username_filter = request.GET.get('username', '').strip()
    if username_filter:
        qs = qs.filter(username__icontains=username_filter)

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))
    for row in page_obj:
        row.status_code, row.days_left = _token_status(row.expires_at)

    params = request.GET.copy()
    params.pop('page', None)
    base_query = params.urlencode()

    context = {
        'latest_per_user': latest_per_user,
        'summary': summary,
        'page_obj': page_obj,
        'soon_days': TOKEN_SOON_DAYS,
        'username_filter': username_filter,
        'base_query': base_query,
    }
    return render(request, 'monitor/token_log.html', context)


def monitor_api_usage(request):
    """Dashboard การเรียกใช้ endpoint ตรวจสอบ/ดึงข้อมูล นศ.-บุคลากร

    ตอบคำถาม "ระบบไหนเรียกเข้ามาบ้าง ผลเป็นยังไง" และค้นด้วยรหัส นศ./บุคลากร
    เพื่อตอบ "ทำไมคนนี้จากระบบ X เข้าไม่ได้"
    """
    if not _is_authed(request):
        return redirect('monitor_login')

    # หน้านี้เป็น real-time monitor: ดูเฉพาะ "วันนี้" เท่านั้น เพื่อให้ query เบาตลอด
    # แม้รีเฟรชถี่ (5-10 วิ) — ข้อมูลย้อนหลังอยู่หน้า Analysis (อ่านจากคลัง api_access_archive)
    # หลัง management command rotate_access_log เดินทุกคืน ตารางสดจะเหลือเฉพาะวันนี้อยู่แล้ว
    today = timezone.localtime().date()
    today_qs = ApiAccessLog.objects.filter(created_at__date=today)
    qs = today_qs

    # ---- ตัวกรอง ----
    client_filter = request.GET.get('client_user', '').strip()
    result_filter = request.GET.get('result', '')
    version_filter = request.GET.get('api_version', '')
    q = request.GET.get('q', '').strip()

    if client_filter:
        qs = qs.filter(client_user=client_filter)
    if result_filter in (ApiAccessLog.RESULT_SUCCESS, ApiAccessLog.RESULT_FAIL):
        qs = qs.filter(result=result_filter)
    if version_filter:
        qs = qs.filter(api_version=version_filter)
    if q:
        qs = qs.filter(
            Q(target_user__icontains=q)
            | Q(client_user__icontains=q)
            | Q(client_ip__icontains=q)
            | Q(endpoint__icontains=q)
        )

    # ---- สรุปวันนี้ (ทุกตัวอ่านจากตารางสด = วันนี้เท่านั้น จึงเบา) ----
    today_total = today_qs.count()
    today_fail = today_qs.filter(result=ApiAccessLog.RESULT_FAIL).count()
    summary = {
        'today_total': today_total,
        'today_fail': today_fail,
        'today_success': today_total - today_fail,
        'today_systems': today_qs.exclude(client_user__isnull=True).values('client_user').distinct().count(),
    }

    # ---- ภาพรวมต่อระบบ (วันนี้) ----
    systems = list(
        today_qs
        .values('client_user')
        .annotate(
            total=Count('id'),
            fails=Count('id', filter=Q(result=ApiAccessLog.RESULT_FAIL)),
        )
        .order_by('-total')[:20]
    )

    # ตัวเลือก client สำหรับ dropdown (เฉพาะระบบที่เรียกวันนี้)
    client_choices = list(
        today_qs.exclude(client_user__isnull=True).exclude(client_user='')
        .values_list('client_user', flat=True).distinct().order_by('client_user')
    )

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    for log in page_obj:
        log.reason_label = _access_explain(log)

    params = request.GET.copy()
    params.pop('page', None)
    base_query = params.urlencode()

    context = {
        'page_obj': page_obj,
        'summary': summary,
        'systems': systems,
        'client_choices': client_choices,
        'filters': {
            'client_user': client_filter,
            'result': result_filter,
            'api_version': version_filter,
            'q': q,
        },
        'base_query': base_query,
    }
    return render(request, 'monitor/api_usage.html', context)


def _parse_iso_date(value, default):
    """แปลง 'YYYY-MM-DD' จาก query เป็น date, ไม่ผ่านก็คืนค่า default"""
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return default


def monitor_api_usage_analysis(request):
    """หน้าวิเคราะห์ย้อนหลัง — อ่านจากคลัง ApiAccessArchive (ไม่ใช่ตารางสด)

    แยกจากหน้า real-time โดยตั้งใจ: หน้านี้ไว้ "วิเคราะห์/ตรวจสอบระบบที่เข้ามา" เลือก
    ช่วงวันที่เองได้ ไม่มี auto-refresh จึง query หนักได้โดยไม่กระทบหน้า monitor ที่รีเฟรชถี่
    (คนละตาราง) ข้อมูล "วันนี้" ยังอยู่ในตารางสด → ดูที่หน้า real-time. คลังมีเฉพาะวันที่ปิดแล้ว
    """
    if not _is_authed(request):
        return redirect('monitor_login')

    today = timezone.localtime().date()
    # ค่าเริ่มต้น: 7 วันก่อนหน้า (ถึงเมื่อวาน — วันนี้ยังไม่ถูกย้ายเข้าคลัง)
    date_to = _parse_iso_date(request.GET.get('date_to'), today - timedelta(days=1))
    date_from = _parse_iso_date(request.GET.get('date_from'), date_to - timedelta(days=6))
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    qs = ApiAccessArchive.objects.filter(
        created_at__date__gte=date_from, created_at__date__lte=date_to,
    )

    # ---- ตัวกรอง (ชุดเดียวกับหน้า real-time) ----
    client_filter = request.GET.get('client_user', '').strip()
    result_filter = request.GET.get('result', '')
    version_filter = request.GET.get('api_version', '')
    q = request.GET.get('q', '').strip()

    if client_filter:
        qs = qs.filter(client_user=client_filter)
    if result_filter in (ApiAccessArchive.RESULT_SUCCESS, ApiAccessArchive.RESULT_FAIL):
        qs = qs.filter(result=result_filter)
    if version_filter:
        qs = qs.filter(api_version=version_filter)
    if q:
        qs = qs.filter(
            Q(target_user__icontains=q)
            | Q(client_user__icontains=q)
            | Q(client_ip__icontains=q)
            | Q(endpoint__icontains=q)
        )

    # ---- สรุปทั้งช่วง ----
    range_total = qs.count()
    range_fail = qs.filter(result=ApiAccessArchive.RESULT_FAIL).count()
    summary = {
        'range_total': range_total,
        'range_fail': range_fail,
        'range_success': range_total - range_fail,
        'range_systems': qs.exclude(client_user__isnull=True).values('client_user').distinct().count(),
    }

    # ---- ภาพรวมต่อระบบ ทั้งช่วง (ไว้ดูว่าระบบไหนเรียกเยอะ/ล้มเหลวเยอะ/ใช้ IP กี่ตัว) ----
    systems = list(
        qs.values('client_user')
        .annotate(
            total=Count('id'),
            fails=Count('id', filter=Q(result=ApiAccessArchive.RESULT_FAIL)),
            ips=Count('client_ip', distinct=True),
            last_seen=Max('created_at'),
        )
        .order_by('-total')[:50]
    )

    client_choices = list(
        qs.exclude(client_user__isnull=True).exclude(client_user='')
        .values_list('client_user', flat=True).distinct().order_by('client_user')
    )

    paginator = Paginator(qs, 100)
    page_obj = paginator.get_page(request.GET.get('page'))

    for log in page_obj:
        log.reason_label = _access_explain(log)

    params = request.GET.copy()
    params.pop('page', None)
    base_query = params.urlencode()

    context = {
        'page_obj': page_obj,
        'summary': summary,
        'systems': systems,
        'client_choices': client_choices,
        'filters': {
            'date_from': date_from.isoformat(),
            'date_to': date_to.isoformat(),
            'client_user': client_filter,
            'result': result_filter,
            'api_version': version_filter,
            'q': q,
        },
        'base_query': base_query,
    }
    return render(request, 'monitor/api_usage_analysis.html', context)


def monitor_dashboard(request):
    if not _is_authed(request):
        return redirect('monitor_login')

    qs = BindingLog.objects.all()

    # ---- ตัวกรอง ----
    status_filter = request.GET.get('status', '')
    user_type_filter = request.GET.get('user_type', '')
    reason_filter = request.GET.get('reason_code', '')
    event_filter = request.GET.get('event', '')
    q = request.GET.get('q', '').strip()

    if status_filter in (BindingLog.STATUS_SUCCESS, BindingLog.STATUS_FAIL):
        qs = qs.filter(status=status_filter)
    if event_filter:
        qs = qs.filter(event=event_filter)
    if user_type_filter:
        qs = qs.filter(user_type=user_type_filter)
    if reason_filter:
        qs = qs.filter(reason_code=reason_filter)
    if q:
        qs = qs.filter(
            Q(user_ldap__icontains=q)
            | Q(line_uid__icontains=q)
            | Q(display_name__icontains=q)
        )

    # ---- สรุปยอดวันนี้ ----
    today = timezone.localtime().date()
    today_qs = BindingLog.objects.filter(created_at__date=today)
    summary = {
        'today_total': today_qs.count(),
        'today_success': today_qs.filter(status=BindingLog.STATUS_SUCCESS).count(),
        'today_fail': today_qs.filter(status=BindingLog.STATUS_FAIL).count(),
        'all_total': BindingLog.objects.count(),
    }

    # ---- แบ่งหน้า ----
    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    # แปลง code -> ป้ายภาษาคน สำหรับแถวในหน้านี้
    for log in page_obj:
        log.reason_label = REASON_LABELS.get(log.reason_code, log.reason_code)
        log.event_label = EVENT_LABELS.get(log.event, log.event)

    # querystring สำหรับคงตัวกรองตอนเปลี่ยนหน้า
    params = request.GET.copy()
    params.pop('page', None)
    base_query = params.urlencode()

    context = {
        'page_obj': page_obj,
        'summary': summary,
        'reason_labels': REASON_LABELS,
        'filters': {
            'status': status_filter,
            'user_type': user_type_filter,
            'reason_code': reason_filter,
            'event': event_filter,
            'q': q,
        },
        'reason_choices': REASON_LABELS,
        'event_choices': EVENT_LABELS,
        'base_query': base_query,
    }
    return render(request, 'monitor/dashboard.html', context)
