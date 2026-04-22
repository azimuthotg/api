# apiproject/apiproject/urls.py
"""
URL configuration for apiproject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from apiapp import views,views_v2
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

# Router สำหรับ API v1 (เดิม)
router = DefaultRouter()
router.register('api',views.userViewset)
router.register('std-info',views.StudentsInfoViewset)
router.register('auth-ldap',views.LDAPAuthViewSet, basename='auth-ldap')
router.register('staff-info',views.StaffInfoViewSet, basename='staff-info')
router.register('walai', views.WalaiCheckUserViewSet, basename='walai')
router.register('mt', views.MikroTikHotspotViewSet, basename='mikrotik_hotspot')
router.register('sonoff', views.SonoffControlViewSet, basename='sonoff_control')

# Router สำหรับ API v2 (ใหม่)
router_v2 = DefaultRouter()
router_v2.register('data', views_v2.UserViewSetV2)# เปลี่ยนจาก 'api' เป็น 'data'
router_v2.register('student', views_v2.StudentsInfoViewSetV2)# เปลี่ยนจาก 'std-info' เป็น 'student'
router_v2.register('auth', views_v2.AuthViewSetV2, basename='auth-v2')  # เพิ่ม endpoint auth ใหม่
router_v2.register('ldap', views_v2.LDAPAuthViewSetV2, basename='auth-ldap-v2') # เปลี่ยนจาก 'auth-ldap' เป็น 'ldap'
router_v2.register('personnel', views_v2.StaffInfoViewSetV2, basename='staff-info-v2')# เปลี่ยนจาก 'staff-info' เป็น 'personnel'
router_v2.register('library', views_v2.WalaiCheckUserViewSetV2, basename='walai-v2')# เปลี่ยนจาก 'walai' เป็น 'library'
router_v2.register('mt', views_v2.MikroTikHotspotViewSetV2, basename='mikrotik_hotspot-v2')
router_v2.register('iot', views_v2.SonoffControlViewSetV2, basename='sonoff_control-v2')# เปลี่ยนจาก 'sonoff' เป็น 'iot'

urlpatterns = [
    # ใช้ custom_api_root สำหรับหน้าแรกแทน router.urls
    #path('', custom_views, name='api-root'),

    # ใช้ router.urls สำหรับหน้า��้อมูลแทน custom_api_root
    path('', views.restricted_api_root, name='api-root'),
    
    # API v1 (เดิม)
    path('', include(router.urls)),
    
    # API v2 (ใหม่)
    path('v2/', include(router_v2.urls)),
    # JWT Authentication endpoints (เฉพาะ v2)
    path('v2/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('v2/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('admin/', admin.site.urls),
    path('reserv/',include('reservapp.urls')),
    # path('api/', include("apiapp.urls"))

]
