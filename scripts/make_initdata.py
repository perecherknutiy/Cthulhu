"""Сгенерировать подписанную initData, чтобы дёргать API без Telegram (curl, Postman).

python scripts/make_initdata.py 123456789
curl -H "Authorization: tma $(python scripts/make_initdata.py 123456789)" http://localhost:8000/api/me
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.telegram_auth import sign_init_data  # noqa: E402

if __name__ == "__main__":
    uid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    start_param = sys.argv[2] if len(sys.argv) > 2 else None
    token = os.environ.get("BOT_TOKEN") or get_settings().bot_token
    fields = {"auth_date": str(int(time.time())),
              "user": json.dumps({"id": uid, "first_name": "Dev"}, separators=(",", ":"))}
    if start_param:
        fields["start_param"] = start_param
    print(sign_init_data(fields, token))
