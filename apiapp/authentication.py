# apiapp/authentication.py
from rest_framework.authentication import SessionAuthentication
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