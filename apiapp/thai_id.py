"""ตรวจสอบเลขบัตรประจำตัวประชาชนไทย 13 หลัก (checksum หลักที่ 13)

อัลกอริทึม: นำ 12 หลักแรกคูณกับน้ำหนัก 13..2 บวกกัน, หา 11 - (ผลรวม % 11) แล้ว % 10
ต้องเท่ากับหลักที่ 13. กรองเลขมั่ว/พิมพ์ผิดได้โดยไม่ต้องเชื่อมต่อระบบทะเบียนราษฎร์
"""


def is_valid_thai_citizen_id(cid):
    """True ถ้า cid เป็นเลขบัตร ปชช. 13 หลักที่ checksum ถูกต้อง"""
    if not cid or not isinstance(cid, str):
        return False
    cid = cid.strip()
    if len(cid) != 13 or not cid.isdigit():
        return False
    total = sum(int(cid[i]) * (13 - i) for i in range(12))
    check_digit = (11 - (total % 11)) % 10
    return check_digit == int(cid[12])
