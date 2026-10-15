import os
from dotenv import load_dotenv

load_dotenv()

# 환경변수에서 불러오기
token = os.getenv("DISCORD_BOT_TOKEN")
domain = os.getenv("DOMAIN", "http://localhost:8080")
admin_id_str = os.getenv("ADMIN_ID")

# 관리자 ID 정수로 변환
admin_id = [int(admin_id_str)] if admin_id_str else []
