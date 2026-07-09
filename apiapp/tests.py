from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.request import Request
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.test import APIRequestFactory

from .models import ExternalMember
from .views_v2 import ExternalAccessViewSetV2


def _call_action(action_name, citizen_id, user, data=None):
    """เรียก action ของ ExternalAccessViewSetV2 ตรง ๆ (ข้าม dispatch → ไม่แตะ JWT auth/access-log mixin)"""
    raw = APIRequestFactory().post(f'/v2/external/permanent/{citizen_id}/{action_name}/', data or {})
    drf_req = Request(raw, parsers=[FormParser(), MultiPartParser(), JSONParser()])
    drf_req.user = user
    view = ExternalAccessViewSetV2()
    view.request = drf_req
    return getattr(view, action_name)(drf_req, citizen_id=citizen_id)


def _call_approve(citizen_id, user, data=None):
    return _call_action('permanent_approve', citizen_id, user, data)


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


class PermanentDeleteTests(TestCase):
    """endpoint delete — hard delete สมาชิกถาวรออกจาก DB ทุกสถานะ"""

    def setUp(self):
        self.jwt_user = User.objects.create_user(username='reserv', password='x')

    def _make(self, citizen_id, status_):
        return ExternalMember.objects.create(
            citizen_id=citizen_id, first_name='ทดสอบ', last_name='ลบ',
            member_type=ExternalMember.TYPE_PERMANENT, status=status_,
        )

    def test_delete_active_member_removes_record(self):
        m = self._make('3489900017383', ExternalMember.STATUS_ACTIVE)
        m.permanent_code = '1234567890'
        m.save(update_fields=['permanent_code'])
        resp = _call_action('permanent_delete', m.citizen_id, self.jwt_user)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(ExternalMember.objects.filter(citizen_id=m.citizen_id).exists())

    def test_delete_pending_member_removes_record(self):
        m = self._make('1101700207366', ExternalMember.STATUS_PENDING)
        resp = _call_action('permanent_delete', m.citizen_id, self.jwt_user)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(ExternalMember.objects.filter(citizen_id=m.citizen_id).exists())

    def test_delete_missing_returns_404(self):
        resp = _call_action('permanent_delete', '9999999999999', self.jwt_user)
        self.assertEqual(resp.status_code, 404)
