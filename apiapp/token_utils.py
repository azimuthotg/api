"""Utilities สำหรับ Monitor เรื่อง JWT token

- decode_token(): แกะ JWT ออกมาดูข้อมูล/วันหมดอายุ โดยตรวจ signature
  แต่ไม่เช็ค exp (จะได้ดู token ที่หมดอายุไปแล้วได้ด้วย)
- log_token_issue(): บันทึก 1 รายการลง TokenIssueLog (กันพังถ้า log ไม่ได้)
"""
from datetime import datetime, timezone as dt_timezone

import jwt
from django.conf import settings

from apiapp.models import TokenIssueLog


def _ts_to_dt(ts):
    """unix timestamp (จาก claim iat/exp) -> aware datetime (UTC) หรือ None"""
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=dt_timezone.utc)
    except (ValueError, OSError, TypeError):
        return None


def decode_token(token):
    """แกะ JWT — คืน dict ที่พร้อมแสดงผล

    คืน {
      'valid': bool,            # signature ถูกต้องไหม
      'error': str|None,        # เหตุผลถ้าแกะไม่ได้
      'payload': dict|None,     # claim ทั้งหมด
      'token_type', 'user_id', 'jti': str|None,
      'issued_at', 'expires_at': aware datetime|None,
      'is_expired': bool|None,
    }
    """
    token = (token or '').strip()
    if not token:
        return {'valid': False, 'error': 'ไม่ได้กรอก token', 'payload': None}

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.SIMPLE_JWT.get('ALGORITHM', 'HS256')],
            options={'verify_exp': False},  # ยอมให้ token หมดอายุได้ เพื่ออ่าน exp
        )
        valid, error = True, None
    except jwt.InvalidSignatureError:
        return {'valid': False, 'error': 'signature ไม่ถูกต้อง — token นี้ไม่ได้ออกจากระบบนี้ หรือถูกแก้ไข', 'payload': None}
    except jwt.DecodeError:
        return {'valid': False, 'error': 'รูปแบบ token ไม่ถูกต้อง (ไม่ใช่ JWT)', 'payload': None}
    except Exception as e:  # noqa: BLE001
        return {'valid': False, 'error': f'แกะ token ไม่ได้ ({e})', 'payload': None}

    expires_at = _ts_to_dt(payload.get('exp'))
    is_expired = None
    if expires_at is not None:
        is_expired = datetime.now(tz=dt_timezone.utc) >= expires_at

    return {
        'valid': valid,
        'error': error,
        'payload': payload,
        'token_type': payload.get('token_type'),
        'user_id': payload.get('user_id'),
        'jti': payload.get('jti'),
        'issued_at': _ts_to_dt(payload.get('iat')),
        'expires_at': expires_at,
        'is_expired': is_expired,
    }


def log_token_issue(request, *, event, access_token, username=None):
    """บันทึกการออก token 1 ครั้งลง TokenIssueLog — ห้ามทำให้ flow auth พัง"""
    try:
        info = decode_token(access_token)
        if not info.get('payload'):
            return
        from apiapp.monitoring import get_client_ip  # ใช้ตัวเดิม เลี่ยง import วน
        TokenIssueLog.objects.create(
            event=event,
            username=username,
            user_id=str(info.get('user_id')) if info.get('user_id') is not None else None,
            jti=info.get('jti'),
            issued_at=info.get('issued_at'),
            expires_at=info.get('expires_at'),
            ip_address=get_client_ip(request),
            user_agent=(request.META.get('HTTP_USER_AGENT', '') or '')[:300] if request else None,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[TokenIssueLog] failed to write log: {e}")
