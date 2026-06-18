"""Utilities สำหรับ Monitor การผูกบัญชี (LINE UID + LDAP)

- check_ad_detailed(): ตรวจสอบกับ Active Directory แล้วคืน "สาเหตุ" ที่ชัดเจน
  เพื่อให้เจ้าหน้าที่หน้างานเอา error ไปแจ้งทีมคอมได้
- log_binding(): บันทึกผลการพยายามผูกบัญชีลง BindingLog (กันพังถ้า log ไม่ได้)
"""
import re

from django.conf import settings
from ldap3 import Server, Connection, ALL, NTLM
from ldap3.core.exceptions import (
    LDAPSocketOpenError,
    LDAPException,
)
from rest_framework import status as drf_status
from rest_framework.response import Response

from apiapp.models import BindingLog


# AD ส่ง sub-code ในข้อความ error ตอน bind ไม่ผ่าน (เช่น "data 52e")
# แปลเป็น (reason_code, ข้อความภาษาคน) ให้เจ้าหน้าที่หน้างานวินิจฉัยได้
AD_SUBCODE_REASONS = {
    '525': ('not_in_ad', 'ไม่พบ username นี้ใน AD'),
    '52e': ('invalid_credentials', 'รหัสผ่านไม่ถูกต้อง (หรือไม่มีบัญชีใน AD)'),
    '530': ('ad_denied', 'ไม่อนุญาตให้ล็อกอินในช่วงเวลานี้'),
    '531': ('ad_denied', 'ไม่อนุญาตให้ล็อกอินจากเครื่องนี้'),
    '532': ('password_expired', 'รหัสผ่านหมดอายุ — ต้องตั้งรหัสใหม่'),
    '533': ('account_disabled', 'บัญชีถูกปิดใช้งาน (disabled)'),
    '701': ('account_expired', 'บัญชีหมดอายุ (account expired)'),
    '773': ('must_reset_password', 'ต้องเปลี่ยนรหัสผ่านก่อนใช้งานครั้งแรก'),
    '775': ('account_locked', 'บัญชีถูกล็อก (กรอกรหัสผิดหลายครั้ง)'),
}


def check_ad_detailed(user_ldap, pass_ldap):
    """ตรวจสอบ user/pass กับ AD — bind ครั้งเดียว แล้วอ่าน sub-code สาเหตุ

    คืนค่า (success: bool, info: dict|None, reason_code: str, message: str)
    reason_code: ok | invalid_credentials | not_in_ad | account_locked |
                 account_disabled | password_expired | must_reset_password |
                 account_expired | ad_denied | ad_error
    """
    try:
        server = Server(settings.LDAP_SERVER, get_info=ALL)
        conn = Connection(
            server,
            user=f'{settings.DOMAIN_NAME}\\{user_ldap}',
            password=pass_ldap,
            authentication=NTLM,
            auto_bind=False,   # ไม่ throw — เพื่ออ่าน result['message'] ตอน fail
        )

        if conn.bind():
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
            return True, None, 'ok', 'ตรวจสอบกับ AD สำเร็จ (ไม่พบ attribute เพิ่มเติม)'

        # bind ไม่ผ่าน -> แกะ sub-code จากข้อความของ AD
        ad_msg = (conn.result or {}).get('message', '') or ''
        m = re.search(r'data ([0-9a-fA-F]+)', ad_msg)
        sub = m.group(1).lower() if m else None
        if sub in AD_SUBCODE_REASONS:
            reason_code, reason_text = AD_SUBCODE_REASONS[sub]
        else:
            reason_code, reason_text = 'invalid_credentials', 'รหัสผ่านไม่ถูกต้อง หรือไม่มีบัญชีใน AD'
        suffix = f' (AD data {sub})' if sub else ''
        return False, None, reason_code, f'{reason_text}{suffix}'

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
