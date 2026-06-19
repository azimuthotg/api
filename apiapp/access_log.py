"""บันทึกการเรียกใช้ endpoint (API access log) สำหรับหน้า Monitor

ใช้ ApiAccessLogMixin ครอบ ViewSet ที่ต้องการติดตาม — ดักที่ finalize_response
(จุดเดียวที่ครอบได้ทั้ง custom action และ list/retrieve) แล้วบันทึก 1 แถวต่อ 1 request
โดยไม่ทำให้ flow หลักพัง และไม่เก็บรหัสผ่าน

ระบุ "ระบบที่เรียก" จาก client_user (username ของ JWT) เป็นหลัก + ip/user_agent เป็นตัวช่วย
"""
import time

from apiapp.models import ApiAccessLog
from apiapp.monitoring import get_client_ip


# แปลง HTTP status -> reason_code ภาษาเครื่อง (กรณีที่ view ไม่ได้ระบุ reason เอง)
def _reason_from_status(http_status):
    if http_status is None:
        return None
    if 200 <= http_status < 300:
        return 'ok'
    return {
        400: 'bad_request',
        401: 'unauthorized',
        403: 'forbidden',
        404: 'not_found',
        405: 'method_not_allowed',
        429: 'too_many_requests',
    }.get(http_status, 'server_error' if http_status >= 500 else str(http_status))


def _target_user(view, request):
    """รหัส นศ./บุคลากร ที่ถูกตรวจ/ดึง — เดาจาก body, lookup kwarg, แล้ว query param"""
    data = getattr(request, 'data', None) or {}
    for key in ('userLdap', 'user_ldap'):
        if data.get(key):
            return str(data.get(key))
    lookup = getattr(view, 'lookup_field', None)
    kwargs = getattr(view, 'kwargs', None) or {}
    if lookup and kwargs.get(lookup):
        return str(kwargs.get(lookup))
    # endpoint แบบค้นหา (list): เก็บคำค้นไว้ดูได้
    qp = request.query_params if hasattr(request, 'query_params') else {}
    parts = [f'{k}={v}' for k, v in qp.items() if k in ('name', 'surname', 'department')]
    return ('search:' + '&'.join(parts)) if parts else None


def _short_message(request, response):
    """ข้อความสรุปผล — จาก reason ที่ view ฝากไว้ ก่อน, ไม่งั้นเอา detail จาก body"""
    meta = getattr(request, '_api_access_reason', None)
    if meta:
        return meta  # (reason_code, message)
    data = getattr(response, 'data', None)
    if isinstance(data, dict):
        detail = data.get('detail') or data.get('error')
        if detail:
            return None, str(detail)[:500]
    return None, None


def log_api_access(view, request, response):
    """บันทึก 1 รายการลง ApiAccessLog — ห้ามทำให้ flow หลักพังเด็ดขาด"""
    try:
        http_status = getattr(response, 'status_code', None)
        result = (ApiAccessLog.RESULT_SUCCESS
                  if http_status is not None and 200 <= http_status < 400
                  else ApiAccessLog.RESULT_FAIL)

        user = getattr(request, 'user', None)
        client_user = user.get_username() if (user and user.is_authenticated) else None

        reason_code, message = _short_message(request, response)
        if not reason_code:
            reason_code = _reason_from_status(http_status)

        t0 = getattr(request, '_api_access_t0', None)
        duration_ms = round((time.monotonic() - t0) * 1000) if t0 else None

        action = getattr(view, 'action', None) or (request.method or '').lower()
        endpoint = f'{view.__class__.__name__}.{action}'

        ApiAccessLog.objects.create(
            client_user=client_user,
            client_ip=get_client_ip(request),
            user_agent=(request.META.get('HTTP_USER_AGENT', '') or '')[:300],
            api_version=getattr(view, 'access_log_api_version', None),
            endpoint=endpoint[:100],
            method=request.method,
            target_user=_target_user(view, request),
            http_status=http_status,
            result=result,
            reason_code=reason_code,
            message=message,
            duration_ms=duration_ms,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[ApiAccessLog] failed to write log: {e}")


class ApiAccessLogMixin:
    """Mixin: บันทึกทุก request ที่เข้า ViewSet นี้ลง ApiAccessLog

    subclass ตั้ง access_log_api_version = 'v1' / 'v2'
    ใส่ไว้หน้าสุดของ base class list เพื่อให้ครอบ finalize_response ได้ถูกต้อง
    """
    access_log_api_version = None

    def initial(self, request, *args, **kwargs):
        request._api_access_t0 = time.monotonic()
        return super().initial(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        log_api_access(self, request, response)
        return response
