"""หน้า Monitor การผูกบัญชี (LINE UID + LDAP)

เข้าถึงด้วยรหัสผ่านร่วมแบบง่าย (settings.MONITOR_PASSWORD) — สำหรับบรรณารักษ์
เคาน์เตอร์ดูกิจกรรมการผูกบัญชี สำเร็จ/ไม่สำเร็จ พร้อมสาเหตุ เพื่อนำ error ไปแจ้งทีมคอม
"""
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apiapp.models import BindingLog
from apiapp.monitoring import check_ad_detailed

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

    return render(request, 'monitor/adtest.html', {'result': result, 'username': username})


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
