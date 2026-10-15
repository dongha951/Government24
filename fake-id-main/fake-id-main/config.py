import os
from dotenv import load_dotenv

load_dotenv()  # .env 파일 또는 Render 환경변수 불러오기

# ✅ 이제 여기에 직접 값을 적지 않고 환경변수에서 불러옴
token = os.getenv("DISCORD_BOT_TOKEN")
domain = os.getenv("DOMAIN")  # 기본값 로컬
admin_id_str = os.getenv("ADMIN_ID")

# admin_id는 숫자로 변환
admin_id = [int(admin_id_str)] if admin_id_str else []
