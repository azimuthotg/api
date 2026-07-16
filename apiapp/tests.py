from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import resolve
from rest_framework.request import Request
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.test import APIRequestFactory

from .models import ExternalMember, ExternalAccessCode
from .views_v2 import ExternalAccessViewSetV2, _bkk_today


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


def _call_register(user, data):
    """เรียก permanent_register ตรง ๆ (detail=False ไม่มี citizen_id ใน path)"""
    raw = APIRequestFactory().post('/v2/external/permanent/register/', data)
    drf_req = Request(raw, parsers=[FormParser(), MultiPartParser(), JSONParser()])
    drf_req.user = user
    view = ExternalAccessViewSetV2()
    view.request = drf_req
    return view.permanent_register(drf_req)


class PermanentRegisterNoCitizenIdTests(TestCase):
    """ลงทะเบียนถาวรโดยไม่ใส่เลขบัตร (บุคคลสำคัญ/VVIP) → ระบบออก ID อ้างอิงขึ้นต้น V ให้"""

    def setUp(self):
        self.jwt_user = User.objects.create_user(username='reserv', password='x')

    def test_register_without_citizen_id_generates_ref_id(self):
        resp = _call_register(self.jwt_user, {'first_name': 'นายก', 'last_name': 'สภามหาวิทยาลัย'})
        self.assertEqual(resp.status_code, 201)
        cid = resp.data['member']['citizen_id']
        self.assertEqual(len(cid), 13)
        self.assertTrue(cid.startswith('V'))
        self.assertTrue(cid[1:].isdigit())
        member = ExternalMember.objects.get(citizen_id=cid)
        self.assertEqual(member.member_type, ExternalMember.TYPE_PERMANENT)
        self.assertEqual(member.status, ExternalMember.STATUS_PENDING)

    def test_register_with_invalid_citizen_id_still_400(self):
        # เว้นว่างเท่านั้นที่ gen ให้ — กรอกมาแต่ checksum ผิด ต้อง 400 เหมือนเดิม
        resp = _call_register(self.jwt_user, {
            'citizen_id': '1234567890123', 'first_name': 'ก', 'last_name': 'ข',
        })
        self.assertEqual(resp.status_code, 400)

    def test_ref_id_member_full_flow_approve_and_gate_check(self):
        # ลงทะเบียน (ไม่มีเลขบัตร) → approve → เช็คที่ประตูด้วย permanent_code ต้อง allow
        reg = _call_register(self.jwt_user, {'first_name': 'นายก', 'last_name': 'สภามหาวิทยาลัย'})
        cid = reg.data['member']['citizen_id']

        approve = _call_action('permanent_approve', cid, self.jwt_user, {'approved_by': 'admin_e'})
        self.assertEqual(approve.status_code, 200)
        member = ExternalMember.objects.get(citizen_id=cid)
        self.assertEqual(member.status, ExternalMember.STATUS_ACTIVE)
        self.assertTrue(member.permanent_code)

        raw = APIRequestFactory().get(f'/v2/external/check/{member.permanent_code}/')
        drf_req = Request(raw)
        drf_req.user = self.jwt_user
        view = ExternalAccessViewSetV2()
        view.request = drf_req
        check = view.check_external(drf_req, code=member.permanent_code)
        self.assertEqual(check.status_code, 200)
        self.assertTrue(check.data['allow'])
        self.assertEqual(check.data['member']['citizen_id'], cid)

    def test_url_routes_accept_v_prefixed_id(self):
        # regex ใน url_path ต้อง match ID ขึ้นต้น V (และยัง match เลขบัตรจริง 13 หลัก)
        for cid in ('V000000000001', '3489900017383'):
            for suffix in ('', 'approve/', 'revoke/', 'delete/', 'photo/'):
                match = resolve(f'/v2/external/permanent/{cid}/{suffix}')
                self.assertEqual(match.kwargs.get('citizen_id'), cid,
                                 f'route ไม่ match: {cid}/{suffix}')


# เลขบัตรประชาชนที่ผ่าน checksum จริง (ใช้ซ้ำจากเคสอื่นในไฟล์นี้)
VALID_ID_1 = '3489900017383'


def _call_issue(user, data):
    """เรียก issue ตรง ๆ (detail=False, ไม่มี citizen_id ใน path)"""
    raw = APIRequestFactory().post('/v2/external/issue/', data)
    drf_req = Request(raw, parsers=[FormParser(), MultiPartParser(), JSONParser()])
    drf_req.user = user
    view = ExternalAccessViewSetV2()
    view.request = drf_req
    return view.issue(drf_req)


def _call_check(code, user):
    """เรียก check_external ที่ประตู ด้วยรหัส 10 หลัก"""
    raw = APIRequestFactory().get(f'/v2/external/check/{code}/')
    drf_req = Request(raw)
    drf_req.user = user
    view = ExternalAccessViewSetV2()
    view.request = drf_req
    return view.check_external(drf_req, code=code)


class DailyPoolAccessCodeTests(TestCase):
    """เส้นรหัสหมุนเวียนรายวัน: ออกรหัส (issue) + เช็คที่ประตู (check_external)

    เดิมมีเทสเฉพาะเส้นสมาชิกถาวร — เส้นรายวัน (ที่ทีมประตูใช้จริงเป็นหลัก) ยังไม่มีเทส automated
    """

    def setUp(self):
        self.jwt_user = User.objects.create_user(username='reserv', password='x')
        # pool 3 รหัส ยังไม่ถูกจอง (seq/code ไม่ซ้ำ)
        for i in range(1, 4):
            ExternalAccessCode.objects.create(code=f'100000000{i}', seq=i)

    # ── issue ────────────────────────────────────────────────────────────────
    def test_issue_assigns_code_for_today(self):
        resp = _call_issue(self.jwt_user, {'citizen_id': VALID_ID_1, 'first_name': 'สม', 'last_name': 'ชาย'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['success'])
        self.assertEqual(resp.data['valid_date'], _bkk_today().isoformat())
        entry = ExternalAccessCode.objects.get(code=resp.data['access_code'])
        self.assertEqual(entry.assigned_citizen_id, VALID_ID_1)
        self.assertEqual(entry.assigned_date, _bkk_today())
        self.assertTrue(ExternalMember.objects.filter(citizen_id=VALID_ID_1).exists())

    def test_issue_same_person_twice_returns_same_code(self):
        # ขอซ้ำในวันเดียว = ได้รหัสเดิม ไม่เปลือง slot ที่ 2
        r1 = _call_issue(self.jwt_user, {'citizen_id': VALID_ID_1, 'first_name': 'สม', 'last_name': 'ชาย'})
        r2 = _call_issue(self.jwt_user, {'citizen_id': VALID_ID_1, 'first_name': 'สม', 'last_name': 'ชาย'})
        self.assertEqual(r1.data['access_code'], r2.data['access_code'])
        self.assertEqual(ExternalAccessCode.objects.filter(assigned_date=_bkk_today()).count(), 1)

    def test_issue_invalid_citizen_id_400(self):
        resp = _call_issue(self.jwt_user, {'citizen_id': '1234567890123', 'first_name': 'ก', 'last_name': 'ข'})
        self.assertEqual(resp.status_code, 400)

    def test_issue_missing_name_400(self):
        resp = _call_issue(self.jwt_user, {'citizen_id': VALID_ID_1, 'first_name': '', 'last_name': ''})
        self.assertEqual(resp.status_code, 400)

    def test_issue_without_citizen_id_generates_ref_id(self):
        # นโยบายใหม่: เลขบัตร optional — ไม่ส่งมา → gen ref id ขึ้นต้น V แล้วออกรหัสได้
        resp = _call_issue(self.jwt_user, {'first_name': 'สม', 'last_name': 'ชาย'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['success'])
        ref = resp.data['member']['citizen_id']
        self.assertTrue(ref.startswith('V'))
        entry = ExternalAccessCode.objects.get(code=resp.data['access_code'])
        self.assertEqual(entry.assigned_citizen_id, ref)
        # ประตูต้อง allow รหัสนี้ได้ (member ref-id ถูกสร้างและไม่ถูกระงับ)
        chk = _call_check(resp.data['access_code'], self.jwt_user)
        self.assertEqual(chk.status_code, 200)
        self.assertTrue(chk.data['allow'])

    def test_issue_without_citizen_id_each_request_consumes_new_slot(self):
        # ไม่มีเลขบัตร = แยกคนไม่ได้ → ไม่ dedupe, กินสล็อตใหม่ทุกครั้ง (ต่างจากเส้นมีเลขบัตร)
        r1 = _call_issue(self.jwt_user, {'first_name': 'สม', 'last_name': 'ชาย'})
        r2 = _call_issue(self.jwt_user, {'first_name': 'สม', 'last_name': 'ชาย'})
        self.assertNotEqual(r1.data['access_code'], r2.data['access_code'])
        self.assertEqual(ExternalAccessCode.objects.filter(assigned_date=_bkk_today()).count(), 2)

    def test_issue_revoked_member_403(self):
        ExternalMember.objects.create(citizen_id=VALID_ID_1, first_name='ก', last_name='ข',
                                      status=ExternalMember.STATUS_REVOKED)
        resp = _call_issue(self.jwt_user, {'citizen_id': VALID_ID_1, 'first_name': 'ก', 'last_name': 'ข'})
        self.assertEqual(resp.status_code, 403)

    def test_issue_pool_exhausted_503(self):
        # จองรหัสทั้ง pool ให้คนอื่นวันนี้จนหมด → คนใหม่ต้อง 503
        ExternalAccessCode.objects.all().update(
            assigned_citizen_id='9999999999999', assigned_date=_bkk_today())
        resp = _call_issue(self.jwt_user, {'citizen_id': VALID_ID_1, 'first_name': 'ก', 'last_name': 'ข'})
        self.assertEqual(resp.status_code, 503)

    # ── check_external (เส้นรายวัน) ───────────────────────────────────────────
    def test_check_valid_today_code_allows(self):
        issue = _call_issue(self.jwt_user, {'citizen_id': VALID_ID_1, 'first_name': 'สม', 'last_name': 'ชาย'})
        resp = _call_check(issue.data['access_code'], self.jwt_user)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['allow'])
        self.assertEqual(resp.data['member']['citizen_id'], VALID_ID_1)

    def test_check_unassigned_pool_code_404(self):
        # รหัสที่มีใน pool แต่ยังไม่ถูกจองวันนี้ → ไม่อนุญาต
        resp = _call_check('1000000001', self.jwt_user)
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(resp.data['allow'])

    def test_check_yesterday_code_404(self):
        # รหัสของเมื่อวาน (assigned_date != วันนี้) ต้องหมดอายุ
        entry = ExternalAccessCode.objects.get(seq=1)
        entry.assigned_citizen_id = VALID_ID_1
        entry.assigned_date = _bkk_today() - timedelta(days=1)
        entry.save()
        ExternalMember.objects.create(citizen_id=VALID_ID_1, first_name='ก', last_name='ข')
        resp = _call_check(entry.code, self.jwt_user)
        self.assertEqual(resp.status_code, 404)

    def test_check_daily_code_revoked_member_403(self):
        issue = _call_issue(self.jwt_user, {'citizen_id': VALID_ID_1, 'first_name': 'ก', 'last_name': 'ข'})
        ExternalMember.objects.filter(citizen_id=VALID_ID_1).update(status=ExternalMember.STATUS_REVOKED)
        resp = _call_check(issue.data['access_code'], self.jwt_user)
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(resp.data['allow'])
