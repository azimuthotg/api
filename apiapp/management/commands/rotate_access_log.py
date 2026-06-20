"""ย้าย API access log ออกจากตารางสด -> คลัง แล้วลบคลังที่เกินอายุเก็บ

จุดประสงค์: ให้ตารางสด `api_access_log` มีเฉพาะ "วันนี้" เท่านั้น หน้า Monitor
real-time จึง query เบาตลอด ไม่ว่าจะรีเฟรชถี่แค่ไหน ส่วนข้อมูลย้อนหลังเก็บไว้ใน
คลัง `api_access_archive` (ดิบครบ) ไว้วิเคราะห์/ตรวจสอบระบบที่เข้ามา

ทำ 2 ขั้นตามลำดับ:
  1) ย้ายแถวที่ "เก่ากว่าวันนี้" (created_at__date < today) จากตารางสด -> คลัง
     แล้วลบออกจากตารางสด — ทำเป็นชุด (chunk) กันล็อกตารางยาว และคงค่า created_at เดิม
  2) ลบแถวในคลังที่เกิน RETENTION_DAYS วัน

ออกแบบให้รันซ้ำได้ปลอดภัย (idempotent): ถ้ารันสองครอบในวันเดียว ครอบที่สองจะไม่เจอ
แถวเก่าให้ย้ายอีก ตั้งรันทุกเที่ยงคืนผ่าน Windows Task Scheduler (ดู rotate_access_log.ps1)

ตัวอย่าง:
    python manage.py rotate_access_log
    python manage.py rotate_access_log --retention-days 90 --dry-run
"""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apiapp.models import ApiAccessLog, ApiAccessArchive

RETENTION_DAYS = 90       # อายุเก็บในคลัง
CHUNK_SIZE = 2000         # จำนวนแถวต่อรอบการย้าย/ลบ กันล็อกตารางยาว
BANGKOK_TZ = ZoneInfo('Asia/Bangkok')  # เส้นแบ่ง "วัน" ใช้เวลาไทย

# คอลัมน์ที่ก๊อปข้ามตาราง (โครงสร้างสองตารางตรงกัน ยกเว้น pk/auto)
COPY_FIELDS = (
    'created_at', 'client_user', 'client_ip', 'user_agent', 'api_version',
    'endpoint', 'method', 'target_user', 'http_status', 'result',
    'reason_code', 'message', 'duration_ms',
)


class Command(BaseCommand):
    help = 'ย้าย API access log ของวันก่อนหน้าเข้าคลัง แล้วลบคลังที่เกินอายุเก็บ'

    def add_arguments(self, parser):
        parser.add_argument(
            '--retention-days', type=int, default=RETENTION_DAYS,
            help=f'อายุเก็บในคลัง (วัน) ค่าเริ่มต้น {RETENTION_DAYS}',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='แสดงว่าจะทำอะไรโดยไม่แก้ข้อมูลจริง',
        )

    def handle(self, *args, **options):
        retention_days = options['retention_days']
        dry_run = options['dry_run']
        # เที่ยงคืนวันนี้ (เวลาไทย) เป็น datetime aware — แถวก่อนหน้านี้ = "พ้นวันแล้ว"
        # ใช้ filter __lt=cutoff (range) แทน __date เพื่อเลี่ยง MySQL CONVERT_TZ
        today_bkk = timezone.now().astimezone(BANGKOK_TZ).date()
        cutoff = datetime.combine(today_bkk, time.min, tzinfo=BANGKOK_TZ)

        moved = self._archive_old_rows(cutoff, dry_run)
        purged = self._purge_archive(retention_days, dry_run)

        tag = '[dry-run] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f"{tag}rotate_access_log เสร็จ: ย้ายเข้าคลัง {moved} แถว, "
            f"ลบคลังที่เกิน {retention_days} วัน {purged} แถว"
        ))

    def _archive_old_rows(self, cutoff, dry_run):
        """ย้ายแถวที่เกิดก่อน cutoff (เที่ยงคืนวันนี้ เวลาไทย) จากตารางสด -> คลัง ทีละชุด"""
        base_qs = ApiAccessLog.objects.filter(created_at__lt=cutoff)
        total = base_qs.count()
        if total == 0:
            self.stdout.write('ไม่มีแถวเก่าให้ย้าย (ตารางสดมีเฉพาะวันนี้แล้ว)')
            return 0
        if dry_run:
            self.stdout.write(f'[dry-run] จะย้าย {total} แถวเข้าคลัง')
            return total

        moved = 0
        while True:
            # ดึง pk ของชุดถัดไป (เรียงเก่า->ใหม่ เพื่อย้ายของเก่าก่อน)
            pk_chunk = list(
                ApiAccessLog.objects.filter(created_at__lt=cutoff)
                .order_by('created_at')
                .values_list('pk', flat=True)[:CHUNK_SIZE]
            )
            if not pk_chunk:
                break
            with transaction.atomic():
                rows = ApiAccessLog.objects.filter(pk__in=pk_chunk)
                archives = [
                    ApiAccessArchive(**{f: getattr(r, f) for f in COPY_FIELDS})
                    for r in rows
                ]
                ApiAccessArchive.objects.bulk_create(archives, batch_size=CHUNK_SIZE)
                rows.delete()
            moved += len(pk_chunk)
            self.stdout.write(f'  ย้ายแล้ว {moved}/{total}')
        return moved

    def _purge_archive(self, retention_days, dry_run):
        """ลบแถวในคลังที่เกินอายุเก็บ ทีละชุด"""
        cutoff = timezone.now() - timedelta(days=retention_days)
        base_qs = ApiAccessArchive.objects.filter(created_at__lt=cutoff)
        total = base_qs.count()
        if total == 0:
            return 0
        if dry_run:
            self.stdout.write(f'[dry-run] จะลบคลัง {total} แถว (เก่ากว่า {cutoff:%Y-%m-%d})')
            return total

        purged = 0
        while True:
            pk_chunk = list(
                ApiAccessArchive.objects.filter(created_at__lt=cutoff)
                .values_list('pk', flat=True)[:CHUNK_SIZE]
            )
            if not pk_chunk:
                break
            ApiAccessArchive.objects.filter(pk__in=pk_chunk).delete()
            purged += len(pk_chunk)
        return purged
