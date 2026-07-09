from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.request import Request
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.test import APIRequestFactory

from .models import ExternalMember
from .views_v2 import ExternalAccessViewSetV2


def _call_approve(citizen_id, user, data=None):
    """เรียก action permanent_approve ตรง ๆ (ข้าม dispatch → ไม่แตะ JWT auth/access-log mixin)
    เพื่อทดสอบเฉพาะ logic การเลือก approved_by
    """
    raw = APIRequestFactory().post(f'/v2/external/permanent/{citizen_id}/approve/', data or {})
    drf_req = Request(raw, parsers=[FormParser(), MultiPartParser(), JSONParser()])
    drf_req.user = user
    view = ExternalAccessViewSetV2()
    view.request = drf_req
    return view.permanent_approve(drf_req, citizen_id=citizen_id)


class PermanentApproveApprovedByTests(TestCase):
    """endpoint approve เก็บ approved_by จาก request ถ้ามี ไม่งั้น fallback เป็น username ของ JWT"""

    def setUp(self):
        self.jwt_user = User.objects.create_user(username='reserv', password='x')
        self.member = ExternalMember.objects.create(
            citizen_id='3489900017383', first_name='สุรนารถ', last_name='สุพรรณ',
            member_type=ExternalMember.TYPE_PERMANENT, status=ExternalMember.STATUS_PENDING,
        )

    def test_uses_approved_by_from_request(self):
        resp = _call_approve(self.member.citizen_id, self.jwt_user, {'approved_by': 'admin_e'})
        self.assertEqual(resp.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.status, ExternalMember.STATUS_ACTIVE)
        self.assertEqual(self.member.approved_by, 'admin_e')      # ชื่อ staff ที่ส่งมา ไม่ใช่ "reserv"
        self.assertTrue(self.member.permanent_code)

    def test_falls_back_to_jwt_username_when_absent(self):
        # ไม่ส่ง approved_by → ต้องคง pattern เดิม (username ของ JWT = reserv)
        resp = _call_approve(self.member.citizen_id, self.jwt_user, {})
        self.assertEqual(resp.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.approved_by, 'reserv')

    def test_blank_approved_by_falls_back(self):
        resp = _call_approve(self.member.citizen_id, self.jwt_user, {'approved_by': '   '})
        self.assertEqual(resp.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.approved_by, 'reserv')
