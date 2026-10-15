import os
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("DISCORD_BOT_TOKEN")
domain = os.getenv("DOMAIN", "http://localhost:8080")
admin_id_str = os.getenv("ADMIN_ID")
admin_id = [int(admin_id_str)] if admin_id_str else []
