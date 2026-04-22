from django.contrib import admin
# from app import models
from apiapp.models import UserProfile,StudentsInfo

# Register your models here.
admin.site.register(UserProfile)
admin.site.register(StudentsInfo)