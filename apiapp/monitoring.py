"""Utilities สำหรับ Monitor การผูกบัญชี (LINE UID + LDAP)

- check_ad_detailed(): ตรวจสอบกับ Active Directory แล้วคืน "สาเหตุ" ที่ชัดเจน
  เพื่อให้เจ้าหน้าที่หน้างานเอา error ไปแจ้งทีมคอมได้
- log_binding(): บันทึกผลการพยายามผูกบัญชีลง BindingLog (กันพังถ้า log ไม่ได้)
"""
from django.conf import settings
from ldap3 import Server, Connection, ALL, NTLM
from ldap3.core.exceptions import (
    LDAPBindError,
    LDAPSocketOpenError,
    LDAPException,
)
from rest_framework import status as drf_status
from rest_framework.response import Response

from apiapp.models import BindingLog


def check_ad_detailed(user_ldap, pass_ldap):
    """ตรวจสอบ user/pass กับ AD

    คืนค่า (success: bool, info: dict|None, reason_code: str, message: str)
    reason_code: ok | invalid_credentials | not_in_ad | ad_error
    """
    try:
        server = Server(settings.LDAP_SERVER, get_info=ALL)
        conn = Connection(
            server,
            user=f'{settings.DOMAIN_NAME}\\{user_ldap}',
            password=pass_ldap,
            authentication=NTLM,
            auto_bind=True,
        )

        # bind สำเร็จ -> ค้นข้อมูลเพิ่มเติม
        dc = settings.DOMAIN_NAME.split('.')
        base_dn = f'dc={dc[0]},dc={dc[1]}'
        conn.search(base_dn, f'(sAMAccountName={user_ldap})', attributes=['displayName', 'mail'])

        if conn.entries:
            info = {
                'displayName': conn.entries[0].displayName.value,
                'email': conn.entries[0].mail.value if conn.entries[0].mail else None,
            }
            return True, info, 'ok', 'ตรวจสอบกับ AD สำเร็จ'

        # bind ผ่านแต่ค้นไม่เจอ (พบได้น้อยมาก)
        return False, None, 'not_in_ad', 'เชื่อมต่อ AD ได้ แต่ไม่พบบัญชีผู้ใช้ใน AD'

    except LDAPBindError as e:
        return False, None, 'invalid_credentials', f'รหัสผ่านไม่ถูกต้อง หรือไม่มีบัญชีนี้ใน AD ({e})'
    except LDAPSocketOpenError as e:
        return False, None, 'ad_error', f'เชื่อมต่อ AD server ไม่ได้ (network/AD ล่ม) ({e})'
    except LDAPException as e:
        return False, None, 'ad_error', f'เกิดข้อผิดพลาดจาก AD ({e})'
    except Exception as e:  # noqa: BLE001 - กันทุกกรณีไม่ให้ flow พัง
        return False, None, 'ad_error', f'เกิดข้อผิดพลาดไม่ทราบสาเหตุ ({e})'


def get_client_ip(request):
    if request is None:
        return None
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_binding(request, *, event, user_ldap, status, reason_code, message,
                line_uid=None, display_name=None, user_type=None, api_version=None):
    """บันทึก 1 รายการลง BindingLog — ห้ามทำให้ flow หลักพังเด็ดขาด"""
    try:
        BindingLog.objects.create(
            event=event,
            line_uid=line_uid,
            display_name=display_name,
            user_ldap=user_ldap,
            user_type=user_type,
            status=status,
            reason_code=reason_code,
            message=message,
            ip_address=get_client_ip(request),
            api_version=api_version,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[BindingLog] failed to write log: {e}")


class BindLoggingCreateMixin:
    """Mixin สำหรับ ViewSet ที่สร้าง UserProfile (POST /api/, /v2/data/)

    บันทึก log สเต็ปที่ 2 ของการผูกบัญชี (LINE UID <-> LDAP) ทั้งสำเร็จและล้มเหลว
    (เช่น userId ซ้ำ) — subclass ตั้งค่า bind_api_version = 'v1' / 'v2'
    """
    bind_api_version = None

    def create(self, request, *args, **kwargs):
        line_uid = request.data.get('userId') or request.data.get('line_uid')
        user_ldap = request.data.get('userLdap')
        user_type = request.data.get('user_type')
        display_name = request.data.get('displayName') or request.data.get('display_name')

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            log_binding(
                request, event='bind', user_ldap=user_ldap,
                status='success', reason_code='ok',
                message='ผูกบัญชี LINE กับ LDAP สำเร็จ',
                line_uid=line_uid, display_name=display_name,
                user_type=user_type, api_version=self.bind_api_version,
            )
            return Response(serializer.data, status=drf_status.HTTP_201_CREATED, headers=headers)

        log_binding(
            request, event='bind', user_ldap=user_ldap,
            status='fail', reason_code='bind_error',
            message=str(serializer.errors),
            line_uid=line_uid, display_name=display_name,
            user_type=user_type, api_version=self.bind_api_version,
        )
        return Response(serializer.errors, status=drf_status.HTTP_400_BAD_REQUEST)
