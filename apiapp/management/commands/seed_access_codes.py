"""สร้าง/เติม pool รหัสเข้าประตู 10 หลัก สำหรับบุคคลภายนอก (ExternalAccessCode)

รหัสเป็นเลขสุ่ม 10 หลัก (หลักแรก 1-9 กันเลขศูนย์นำหายตอนสแกน) — สุ่มเพื่อให้เดายาก
(ป้องกันคนทายรหัสที่ใช้งานวันนี้แล้วเดินเข้าประตู) ไม่ชนกับ นศ. (12 หลัก)/บุคลากร (13 หลัก)

รันครั้งแรกหรือเติมเพิ่ม (idempotent — เติมจนครบ count ไม่ลบ/แก้ของเดิม):
    python manage.py seed_access_codes              # ตั้ง pool ให้ครบ 100
    python manage.py seed_access_codes --count 500  # ขยาย pool เป็น 500
"""
import random

from django.core.management.base import BaseCommand

from apiapp.models import ExternalAccessCode

DEFAULT_POOL_SIZE = 100
CODE_MIN = 1_000_000_000   # 10 หลัก หลักแรกไม่เป็น 0
CODE_MAX = 9_999_999_999


class Command(BaseCommand):
    help = 'สร้าง/เติม pool รหัสเข้าประตู 10 หลักสำหรับบุคคลภายนอก'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count', type=int, default=DEFAULT_POOL_SIZE,
            help=f'ขนาด pool เป้าหมาย (ค่าเริ่มต้น {DEFAULT_POOL_SIZE})',
        )

    def handle(self, *args, **options):
        target = options['count']
        existing = ExternalAccessCode.objects.count()
        if existing >= target:
            self.stdout.write(self.style.SUCCESS(
                f"pool มี {existing} รหัสอยู่แล้ว (>= {target}) — ไม่ต้องทำอะไร"
            ))
            return

        used_codes = set(ExternalAccessCode.objects.values_list('code', flat=True))
        max_seq = existing  # seq ปัจจุบันสูงสุด = จำนวนที่มี (seq เริ่มที่ 1 ต่อเนื่อง)
        to_create = []
        for i in range(existing, target):
            # สุ่มรหัสที่ยังไม่ซ้ำ
            while True:
                code = str(random.randint(CODE_MIN, CODE_MAX))
                if code not in used_codes:
                    used_codes.add(code)
                    break
            to_create.append(ExternalAccessCode(code=code, seq=max_seq + (i - existing) + 1))

        ExternalAccessCode.objects.bulk_create(to_create)
        self.stdout.write(self.style.SUCCESS(
            f"เพิ่มรหัสใหม่ {len(to_create)} รหัส (pool รวม {target})"
        ))
