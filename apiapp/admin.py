from django.contrib import admin
# from app import models
from apiapp.models import UserProfile,StudentsInfo,BindingLog,TokenIssueLog,ApiAccessLog,ApiAccessArchive,ExternalMember,ExternalAccessCode

# Register your models here.
admin.site.register(UserProfile)
admin.site.register(StudentsInfo)


@admin.register(TokenIssueLog)
class TokenIssueLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'event', 'username', 'issued_at', 'expires_at', 'ip_address')
    list_filter = ('event',)
    search_fields = ('username', 'user_id', 'jti', 'ip_address')
    date_hierarchy = 'created_at'
    readonly_fields = [f.name for f in TokenIssueLog._meta.fields]


@admin.register(ApiAccessLog)
class ApiAccessLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'client_user', 'endpoint', 'target_user', 'result', 'http_status', 'reason_code', 'api_version', 'client_ip')
    list_filter = ('result', 'api_version', 'endpoint')
    search_fields = ('client_user', 'target_user', 'client_ip', 'endpoint', 'message')
    date_hierarchy = 'created_at'
    readonly_fields = [f.name for f in ApiAccessLog._meta.fields]


@admin.register(ApiAccessArchive)
class ApiAccessArchiveAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'client_user', 'endpoint', 'target_user', 'result', 'http_status', 'reason_code', 'api_version', 'client_ip')
    list_filter = ('result', 'api_version', 'endpoint')
    search_fields = ('client_user', 'target_user', 'client_ip', 'endpoint', 'message')
    date_hierarchy = 'created_at'
    readonly_fields = [f.name for f in ApiAccessArchive._meta.fields]


@admin.register(ExternalMember)
class ExternalMemberAdmin(admin.ModelAdmin):
    list_display = ('citizen_id', 'first_name', 'last_name', 'status', 'registered_at')
    list_filter = ('status',)
    search_fields = ('citizen_id', 'first_name', 'last_name')
    date_hierarchy = 'registered_at'


@admin.register(ExternalAccessCode)
class ExternalAccessCodeAdmin(admin.ModelAdmin):
    list_display = ('seq', 'code', 'assigned_citizen_id', 'assigned_date')
    list_filter = ('assigned_date',)
    search_fields = ('code', 'assigned_citizen_id')
    ordering = ('seq',)


@admin.register(BindingLog)
class BindingLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'status', 'event', 'user_ldap', 'display_name', 'user_type', 'reason_code', 'api_version', 'ip_address')
    list_filter = ('status', 'event', 'reason_code', 'user_type', 'api_version')
    search_fields = ('user_ldap', 'line_uid', 'display_name', 'message')
    date_hierarchy = 'created_at'
    readonly_fields = [f.name for f in BindingLog._meta.fields]