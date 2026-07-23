# apiapp/authentication.py
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated, AllowAny

class JWTV2Authentication:
    """
    Mixin สำหรับเพิ่ม JWT Authentication ใน ViewSet ของ API v2
    """
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

class PublicEndpointAuthentication:
    """
    Mixin สำหรับ endpoints ที่ไม่ต้องการ authentication
    """
    authentication_classes = []
    permission_classes = [AllowAny]

class NoListMixin:
    """
    Mixin ปิดการเรียกแบบ list (ดึงทั้งตาราง) — ให้ดึงได้ทีละคนด้วยรหัสใน URL เท่านั้น

    ใช้กับ StudentsInfo/StaffInfo ซึ่ง list เดิมเปิดให้ดึงข้อมูลทุกคนออกไปได้
    วางไว้ก่อน viewsets.* ใน base class list เพื่อให้ override list() ได้
    """
    def list(self, request, *args, **kwargs):
        return Response(
            {'detail': 'ปิดการเรียกแบบรายการทั้งหมด — ระบุรหัสรายบุคคลใน URL แทน'},
            status=status.HTTP_403_FORBIDDEN,
        )