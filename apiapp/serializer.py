# apiproject/apiapp/serializers.py
from rest_framework import serializers
from apiapp.models import UserProfile,StudentsInfo,StaffInfo

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = "__all__"

class StudentsInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentsInfo
        fields = '__all__' 
        
class StaffInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffInfo
        fields = '__all__'  # หรือระบุเฉพาะฟิลด์ที่คุณต้องการ