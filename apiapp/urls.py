# apiproject/api/urls.py
from django.urls import path
from apiapp import views

'''
urlpatterns = [
    # path('list/', views.userList, name='userList'),
    path('list/', views.userList.as_view(), name='userList'),
    path('detail/<str:pk>', views.userDetail.as_view(), name='userDetail'),

]
'''