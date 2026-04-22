from django.urls import path
from reservapp import views

urlpatterns = [
    path('',views.home,name='home'),
    path('lineoa/',views.line_oa_home,name='line_oa_home'),
    path('login/',views.login,name='login'),
    path('welcome/',views.welcome,name='welcome'),
    path('logout/', views.logout, name='logout'),  # เส้นทางสำหรับลบ session
    path('rooms/', views.room_list_view, name='room_list'),
    path('rooms/<int:room_id>/', views.room_control_view, name='room_control'),
]