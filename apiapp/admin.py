from django.contrib import admin
# from app import models
from apiapp.models import UserProfile,StudentsInfo,BindingLog

# Register your models here.
admin.site.register(UserProfile)
admin.site.register(StudentsInfo)


@admin.register(BindingLog)
class BindingLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'status', 'event', 'user_ldap', 'display_name', 'user_type', 'reason_code', 'api_version', 'ip_address')
    list_filter = ('status', 'event', 'reason_code', 'user_type', 'api_version')
    search_fields = ('user_ldap', 'line_uid', 'display_name', 'message')
    date_hierarchy = 'created_at'
    readonly_fields = [f.name for f in BindingLog._meta.fields]