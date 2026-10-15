import traceback
import discord
import sqlite3
import os
import random
import asyncio
import json
import uuid
from datetime import datetime, timedelta
from config import *
from discord import app_commands
import string

# ==========================================
# 429 제한 자동 처리
# ==========================================
import logging
logging.basicConfig(level=logging.WARNING)

from discord.http import HTTPClient

_original_request = HTTPClient.request

async def _safe_request(self, *args, **kwargs):
    for attempt in range(5):
        try:
            return await _original_request(self, *args, **kwargs)
        except discord.HTTPException as e:
            if e.status == 429:
                retry_after = 5
                try:
                    retry_after = float(e.response.headers.get("Retry-After", 5)) + 1
                except:
                    pass
                print(f"⚠️ 429 제한! {retry_after:.1f}초 후 재시도 ({attempt+1}/5)")
                await asyncio.sleep(retry_after)
            else:
                raise
    raise Exception("최대 재시도 횟수를 초과했습니다")

HTTPClient.request = _safe_request

# ==========================================
# 초기화
# ==========================================
class RandomString:
    def pick(self, length=20):
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))

randomstring = RandomString()

intents = discord.Intents.all()
intents.members = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# ==========================================
# DB
# ==========================================
with sqlite3.connect("./database.db") as con:
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            key TEXT PRIMARY KEY,
            expire_date INTEGER
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            status TEXT,
            expiredate TEXT,
            query TEXT,
            이름 TEXT,
            주민등록번호 TEXT,
            집주소 TEXT,
            주민등록일자 TEXT,
            지역 TEXT,
            얼굴사진 TEXT
        );
    """)
    con.commit()

def start_db():
    con = sqlite3.connect("database.db")
    cur = con.cursor()
    return con, cur

def make_expiretime(days):
    return (datetime.now() + timedelta(days=int(days))).strftime('%Y-%m-%d %H:%M')

# ==========================================
# 공통 임베드 스타일
# ==========================================
def make_embed(title, desc):
    return discord.Embed(
        title=title,
        description=desc,
        color=0x2b2d31
    )

# ==========================================
# 메인 메뉴 버튼 — 사진과 똑같이
# ==========================================
class MainMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(
            label="정보",
            style=discord.ButtonStyle.blurple,
            emoji="👤",
            custom_id="myinfo"
        ))
        self.add_item(discord.ui.Button(
            label="제작",
            style=discord.ButtonStyle.green,
            emoji="📜",
            custom_id="create_id"
        ))
        self.add_item(discord.ui.Button(
            label="가입",
            style=discord.ButtonStyle.grey,
            emoji="🪪",
            custom_id="join"
        ))

# ==========================================
# 확인 버튼
# ==========================================
class ConfirmView(discord.ui.View):
    def __init__(self, url: str):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(
            label="확인하러 가기",
            style=discord.ButtonStyle.link,
            url=url
        ))

# ==========================================
# 버튼 클릭 이벤트
# ==========================================
@bot.event
async def on_interaction(inter: discord.Interaction):
    if inter.type != discord.InteractionType.component:
        return

    custom_id = inter.data.get("custom_id")
    if not custom_id:
        return

    def check_dm(m):
        return isinstance(m.channel, discord.DMChannel) and m.author.id == inter.user.id

    # === 가입 ===
    if custom_id == "join":
        con, cur = start_db()
        cur.execute("SELECT * FROM users WHERE id = ?;", (inter.user.id,))
        if cur.fetchone():
            embed = make_embed("❌ 실패", "이미 가입되어 있습니다.")
        else:
            cur.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
                        (inter.user.id, None, None, None, None, None, None, None, None, None))
            con.commit()
            embed = make_embed("✅ 가입 완료", f"{inter.user}님\n서비스에 오신 것을 환영합니다!")
        con.close()
        await inter.response.send_message(embed=embed, ephemeral=True)

    # === 내정보 ===
    elif custom_id == "myinfo":
        con, cur = start_db()
        cur.execute("SELECT * FROM users WHERE id = ?;", (inter.user.id,))
        info = cur.fetchone()
        con.close()
        if not info:
            embed = make_embed("❌ 실패", "가입이 필요합니다.")
        elif not info[2]:
            embed = make_embed(f"{inter.user}님의 정보", "라이센스가 유효하지 않습니다.")
        else:
            embed = make_embed(f"{inter.user}님의 정보", f"""
`만기일` : `{info[2]}`
`이름` : `{info[4]}`
`주민등록번호` : `{info[5]}`
`주소` : `{info[6]}`
`발급일자` : `{info[7]}`
`지역` : `{info[8]}`
`링크` : {domain}/{info[3]}
            """)
            embed.set_image(url=info[9])
        try:
            await inter.user.send(embed=embed)
            await inter.response.send_message(embed=make_embed("✅ 안내", "DM을 확인해주세요."), ephemeral=True)
        except:
            await inter.response.send_message(embed=make_embed("❌ 실패", "DM이 차단되어 있습니다."), ephemeral=True)

    # === 제작 ===
    elif custom_id == "create_id":
        con, cur = start_db()
        cur.execute("SELECT * FROM users WHERE id = ?;", (inter.user.id,))
        if not cur.fetchone():
            con.close()
            await inter.response.send_message(embed=make_embed("❌ 실패", "가입이 필요합니다."), ephemeral=True)
            return
        con.close()

        try:
            await inter.user.send(embed=make_embed("라이센스 입력", "라이센스 키를 입력해주세요."))
        except:
            await inter.response.send_message(embed=make_embed("❌ 실패", "DM이 차단되어 있습니다."), ephemeral=True)
            return

        await inter.response.send_message(embed=make_embed("✅ 안내", "DM을 확인해주세요."), ephemeral=True)

        try:
            license_msg = await bot.wait_for("message", timeout=60, check=check_dm)
            license_key = license_msg.content
        except asyncio.TimeoutError:
            await inter.user.send(embed=make_embed("❌ 실패", "시간이 초과되었습니다."))
            return

        con, cur = start_db()
        cur.execute("SELECT * FROM licenses WHERE key = ?;", (license_key,))
        key_info = cur.fetchone()
        if not key_info:
            con.close()
            await inter.user.send(embed=make_embed("❌ 실패", "사용할 수 없는 키입니다."))
            return

        expire_date = make_expiretime(key_info[1])
        cur.execute("UPDATE users SET expiredate = ? WHERE id = ?;", (expire_date, inter.user.id))
        cur.execute("DELETE FROM licenses WHERE key = ?;", (license_key,))
        con.commit()
        con.close()

        async def ask(title, desc, timeout=60, attach=False):
            await inter.user.send(embed=make_embed(title, desc))
            try:
                reply = await bot.wait_for("message", timeout=timeout, check=check_dm)
                if attach and reply.attachments:
                    return reply.attachments[0].url
                return reply.content
            except asyncio.TimeoutError:
                await inter.user.send(embed=make_embed("❌ 실패", "시간이 초과되었습니다."))
                return None

        name = await ask("[1/6] 이름", "이름을 입력해주세요.\n예: 홍길동")
        if not name: return
        num = await ask("[2/6] 주민등록번호", "예: 040101-3537921")
        if not num: return
        juso = await ask("[3/6] 주소", "상세 주소를 입력해주세요.")
        if not juso: return
        make_date = await ask("[4/6] 발급일자", "예: 2021.10.15")
        if not make_date: return
        region = await ask("[5/6] 발급지역", "예: 부산광역시 남구청장")
        if not region: return
        imgurl = await ask("[6/6] 사진", "증명 사진을 업로드해주세요.", timeout=300, attach=True)
        if not imgurl: return

        query_str = randomstring.pick(20)
        con, cur = start_db()
        cur.execute("UPDATE users SET query=?, 이름=?, 주민등록번호=?, 집주소=?, 주민등록일자=?, 지역=?, 얼굴사진=? WHERE id=?;",
                    (query_str, name, num, juso, make_date, region, imgurl, inter.user.id))
        con.commit()
        con.close()

        await inter.user.send(
            embed=make_embed("✅ 발급 완료", "위조민증이 발급되었습니다.\n1회 무상 수정 가능합니다!"),
            view=ConfirmView(f"{domain}/{query_str}")
        )

        log_channel = bot.get_channel(1560263406768881687)
        if log_channel:
            log_embed = make_embed(f"{inter.user}님의 정보", f"""
`만기일` : `{expire_date}`
`이름` : `{name}`
`주민등록번호` : `{num}`
`주소` : `{juso}`
`발급일자` : `{make_date}`
`지역` : `{region}`
`링크` : {domain}/{query_str}
            """)
            log_embed.set_image(url=imgurl)
            try:
                await log_channel.send(embed=log_embed)
            except:
                pass

# ==========================================
# 슬래시 커맨드 — 관리자만 보임
# ==========================================
@bot.event
async def on_ready():
    print("")
    print("─────────────────────────────────────────────────────")
    print(f"✅ HolyGov24 실행: {bot.user}")
    print(f"🔗 초대 링크: https://discord.com/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot")
    print(f"🏠 서버: {len(bot.guilds)}개")
    print("─────────────────────────────────────────────────────")

    @app_commands.command(name="메뉴", description="메인 메뉴를 엽니다")
    async def menu_cmd(inter: discord.Interaction):
        embed = discord.Embed(
            title="[HolyGov24] 24H 무료 QR검증 서비스",
            description="""
사용
#📋 | 이용방법

질문
#❓ | 도움말

문의
#💬 | 문의하기
            """,
            color=0x1a1b1e
        )
        await inter.response.send_message(embed=embed, view=MainMenuView(), ephemeral=False)

    @app_commands.command(name="생성", description="라이센스 키 생성 (관리자 전용)")
    @app_commands.checks.has_permissions(administrator=True)
    async def create_cmd(inter: discord.Interaction, 개수: int, 기간: int):
        if inter.user.id not in admin_id:
            return await inter.response.send_message("❌ 권한이 없습니다.", ephemeral=True)
        if not (1 <= 개수 <= 10):
            return await inter.response.send_message("❌ 최대 10개까지 생성 가능합니다.", ephemeral=True)
        con, cur = start_db()
        keys = []
        for _ in range(개수):
            key = str(uuid.uuid4())
            keys.append(key)
            cur.execute("INSERT INTO licenses VALUES (?, ?);", (key, 기간))
        con.commit()
        con.close()
        await inter.response.send_message(
            embed=make_embed("✅ 생성 완료", f"{개수}개의 키:\n\n`{chr(10).join(keys)}`"),
            ephemeral=True
        )

    @app_commands.command(name="변경", description="유저 정보 수정 (관리자 전용)")
    @app_commands.checks.has_permissions(administrator=True)
    async def edit_cmd(inter: discord.Interaction, 유저: discord.User, 항목: str, 값: str):
        if inter.user.id not in admin_id:
            return await inter.response.send_message("❌ 권한이 없습니다.", ephemeral=True)

        col_map = {
            "이름": "이름",
            "집주소": "집주소",
            "주민등록번호": "주민등록번호",
            "주민등록날짜": "주민등록일자",
            "지역": "지역",
            "사진": "얼굴사진"
        }
        if 항목 not in col_map:
            return await inter.response.send_message(
                "❌ 항목이 올바르지 않습니다.\n가능: 이름, 집주소, 주민등록번호, 주민등록날짜, 지역, 사진",
                ephemeral=True
            )

        target_id = 유저.id
        con, cur = start_db()
        cur.execute("SELECT id FROM users WHERE id = ?;", (target_id,))
        if not cur.fetchone():
            con.close()
            return await inter.response.send_message("❌ 가입되지 않은 유저입니다.", ephemeral=True)

        cur.execute(f"UPDATE users SET `{col_map[항목]}` = ? WHERE id = ?;", (값, target_id))
        con.commit()
        con.close()
        await inter.response.send_message(embed=make_embed("✅ 변경 완료", f"{항목}이(가) 변경되었습니다."), ephemeral=True)

    # 명령어 등록
    tree.add_command(menu_cmd)
    tree.add_command(create_cmd)
    tree.add_command(edit_cmd)

    await tree.sync()
    await bot.change_presence(activity=discord.Game("위조민증 제작"), status=discord.Status.online)

# ==========================================
# 실행
# ==========================================
bot.run(token)
