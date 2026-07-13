"""
Script ทดสอบ Walai Autolib API - KeyWordSearch
รันแยกจากระบบหลัก ไม่ต้องเปิด Django server

Usage:
    python tests/test_walai_search.py
    python tests/test_walai_search.py --keyword "python" --type TITLE
"""

import os
import sys
import requests
import json
import argparse

import environ

# --- Config (อ่านจาก .env ที่ราก project — ไม่ hardcode secret) ---
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env = environ.Env()
environ.Env.read_env(os.path.join(_BASE_DIR, ".env"))

WALAI_BASE_URL = env("WALAI_BASE_URL", default="https://opacapi.npu.ac.th/v3")
WALAI_API_TOKEN = env("WALAI_API_TOKEN", default="")

if not WALAI_API_TOKEN:
    sys.exit("ERROR: ไม่พบ WALAI_API_TOKEN ใน .env — เพิ่มบรรทัด WALAI_API_TOKEN=... ในไฟล์ .env ก่อนรัน")

HEADERS = {
    "token": WALAI_API_TOKEN,
    "Content-Type": "application/json"
}

SEARCH_TYPES = ["KEYWORD", "AUTHOR", "TITLE", "SUBJECT", "ISBNISSN"]


def search_books(keyword: str, search_type: str = "KEYWORD", page: int = 1, per_page: int = 10):
    url = f"{WALAI_BASE_URL}/api/KeyWordSearch"

    payload = {
        "Ntk": search_type,
        "Ntt": keyword,
        "Nto": "and",
        "CurrentPage": page,
        "RowPerPage": per_page,
        "Orderby": "relevance"
    }

    print(f"\n{'='*50}")
    print(f"URL    : {url}")
    print(f"Type   : {search_type}")
    print(f"Keyword: {keyword}")
    print(f"Page   : {page} | Per page: {per_page}")
    print(f"{'='*50}")

    try:
        response = requests.post(url, headers=HEADERS, json=payload, timeout=10)

        print(f"Status : {response.status_code}")
        print(f"\nResponse:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))

    except requests.exceptions.ConnectionError:
        print("ERROR: ไม่สามารถเชื่อมต่อ Walai API ได้")
    except requests.exceptions.Timeout:
        print("ERROR: Request timeout")
    except Exception as e:
        print(f"ERROR: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ทดสอบ Walai KeyWordSearch API")
    parser.add_argument("--keyword", default="python", help="คำที่ต้องการค้นหา")
    parser.add_argument("--type", default="KEYWORD", choices=SEARCH_TYPES, help="ประเภทการค้นหา")
    parser.add_argument("--page", type=int, default=1, help="หน้าที่ต้องการ")
    parser.add_argument("--per-page", type=int, default=10, help="จำนวนผลลัพธ์ต่อหน้า")
    args = parser.parse_args()

    search_books(
        keyword=args.keyword,
        search_type=args.type,
        page=args.page,
        per_page=args.per_page
    )
