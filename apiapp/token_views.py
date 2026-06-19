"""ครอบ endpoint ออก JWT ของ simplejwt เพื่อบันทึกลง TokenIssueLog

ทำงานเหมือน TokenObtainPairView / TokenRefreshView เดิมทุกอย่าง
เพิ่มแค่การ log หลังออก token สำเร็จ (ถ้า log พังก็ไม่กระทบการออก token)
"""
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from apiapp.token_utils import decode_token, log_token_issue
from apiapp.models import TokenIssueLog


def _username_from_access(access_token):
    """หา username จาก user_id ใน access token (สำหรับ refresh ที่ไม่ส่ง username มา)"""
    try:
        info = decode_token(access_token)
        user_id = info.get('user_id')
        if user_id is None:
            return None
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.filter(pk=user_id).first()
        return user.get_username() if user else None
    except Exception:  # noqa: BLE001
        return None


class LoggingTokenObtainPairView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200 and 'access' in response.data:
            log_token_issue(
                request,
                event=TokenIssueLog.EVENT_OBTAIN,
                access_token=response.data['access'],
                username=request.data.get('username'),
            )
        return response


class LoggingTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200 and 'access' in response.data:
            access = response.data['access']
            log_token_issue(
                request,
                event=TokenIssueLog.EVENT_REFRESH,
                access_token=access,
                username=_username_from_access(access),
            )
        return response
