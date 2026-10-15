import discord
import sqlite3
import os
import random
import asyncio
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
# ✅ 채널 ID 설정
# ==========================================
LOG_CHANNEL_ID = 1560263406768881687
LICENSE_LOG_CHANNEL_ID = 1560333768525349007

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
def make_embed(title, desc=""):
    return discord.Embed(
        title=title,
        description=desc,
        color=0x2b2d31
    )

# ==========================================
# 주소찾기 링크 버튼
# ==========================================
class JusoLinkView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(
            label="👉 주소찾기 바로가기",
            style=discord.ButtonStyle.link,
            url="https://www.juso.go.kr/"
        ))

# ==========================================
# 메인 메뉴
# ==========================================
class MainMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(
            label="정보",
            style=discord.ButtonStyle.blurple,
            emoji="👤",
            custom_id="myinfo",
            row=0
        ))
        self.add_item(discord.ui.Button(
            label="제작",
            style=discord.ButtonStyle.green,
            emoji="📜",
            custom_id="create_id",
            row=0
        ))
        self.add_item(discord.ui.Button(
            label="가입",
            style=discord.ButtonStyle.grey,
            emoji="🪪",
            custom_id="join",
            row=0
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
# 라이센스 입력 팝업
# ==========================================
class LicenseModal(discord.ui.Modal, title="라이센스 키 입력"):
    license_key = discord.ui.TextInput(
        label="라이센스 키",
        placeholder="여기에 라이센스 키를 입력하세요",
        required=True,
        min_length=10,
        max_length=50
    )

    async def on_submit(self, inter: discord.Interaction):
        await inter.response.send_message(
            embed=make_embed("✅ 안내", "DM을 확인해주세요."),
            ephemeral=True
        )

        license_key_str = self.license_key.value

        def check_dm(m):
            return isinstance(m.channel, discord.DMChannel) and m.author.id == inter.user.id

        con, cur = start_db()
        cur.execute("SELECT * FROM licenses WHERE key = ?;", (license_key_str,))
        key_info = cur.fetchone()
        if not key_info:
            con.close()
            try:
                await inter.user.send(embed=make_embed("❌ 실패", "사용할 수 없는 키입니다."))
            except:
                pass
            return

        expire_date = make_expiretime(key_info[1])
        cur.execute("UPDATE users SET expiredate = ? WHERE id = ?;", (expire_date, inter.user.id))
        cur.execute("DELETE FROM licenses WHERE key = ?;", (license_key_str,))
        con.commit()
        con.close()

        async def ask(title, desc, timeout=1800, attach=False, link_view=None):
            try:
                emb = make_embed(title, desc)
                if link_view:
                    await inter.user.send(embed=emb, view=link_view)
                else:
                    await inter.user.send(embed=emb)
                reply = await bot.wait_for("message", timeout=timeout, check=check_dm)
                if attach and reply.attachments:
                    return reply.attachments[0].url
                return reply.content
            except asyncio.TimeoutError:
                await inter.user.send(embed=make_embed("❌ 실패", "시간이 초과되었습니다."))
                return None

        name = await ask("[1/6] 이름", "이름을 입력해주세요.\n예: 홍길동")
        if not name: return
        num = await ask("[2/6] 주민등록번호", "주민등록번호를 입력해주세요.\n예: 040101-3537921")
        if not num: return
        juso = await ask("[3/6] 주소", "상세 주소를 입력해주세요.\n예: 경기도 고양시 일산동구 하늘마을1로 105, 306동 902호(중산동, 하늘마을)", link_view=JusoLinkView())
        if not juso: return
        make_date = await ask("[4/6] 발급일자", "발급일자를 입력해주세요.\n예: 2021.10.15")
        if not make_date: return
        region = await ask("[5/6] 발급지역", "발급 지역 및 기관명을 입력해주세요.\n예: 부산광역시 남구청장")
        if not region: return
        imgurl = await ask("[6/6] 사진", "증명 사진을 업로드해주세요.", timeout=1800, attach=True)
        if not imgurl: return

        query_str = randomstring.pick(20)
        con, cur = start_db()
        cur.execute("UPDATE users SET query=?, 이름=?, 주민등록번호=?, 집주소=?, 주민등록일자=?, 지역=?, 얼굴사진=? WHERE id=?;",
                    (query_str, name, num, juso, make_date, region, imgurl, inter.user.id))
        con.commit()
        con.close()

        await inter.user.send(
            embed=make_embed("✅ 제작 완료", "위조민증이 제작되었습니다.\n수정이 필요하신 경우 관리자에게 문의해주세요."),
            view=ConfirmView(f"{domain}/{query_str}")
        )

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = make_embed(f"{inter.user}님 제작 완료")
            log_embed.description = (
                f"`이름` : `{name}`\n"
                f"`주민등록번호` : `{num}`\n"
                f"`주소` : `{juso}`\n"
                f"`발급일자` : `{make_date}`\n"
                f"`발급지역` : `{region}`\n"
                f"`제작 링크` : {domain}/{query_str}"
            )
            log_embed.set_image(url=imgurl)
            try:
                await log_channel.send(embed=log_embed)
            except Exception as e:
                print(f"로그 전송 오류: {e}")

# ==========================================
# DM 전송 함수
# ==========================================
async def send_dm_safe(user, embed):
    try:
        await user.send(embed=embed)
        return True
    except discord.Forbidden:
        return False
    except Exception as e:
        print(f"DM 전송 오류: {e}")
        return False

# ==========================================
# 서버 채널 메시지 자동 삭제
# ==========================================
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if not isinstance(message.channel, discord.DMChannel) and not message.content.startswith('/'):
        await asyncio.sleep(5)
        try:
            await message.delete()
        except:
            pass

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

    elif custom_id == "myinfo":
        con, cur = start_db()
        cur.execute("SELECT * FROM users WHERE id = ?;", (inter.user.id,))
        info = cur.fetchone()
        con.close()
        if not info:
            await inter.response.send_message(
                embed=make_embed("❌ 실패", "가입이 필요합니다."),
                ephemeral=True
            )
            return
        if not info[2]:
            dm_ok = await send_dm_safe(inter.user, make_embed(f"{inter.user}님의 정보", "라이센스가 유효하지 않습니다."))
            if dm_ok:
                await inter.response.send_message(
                    embed=make_embed("✅ 안내", "DM을 확인해주세요."),
                    ephemeral=True
                )
            else:
                await inter.response.send_message(
                    embed=make_embed("❌ 실패", "DM을 활성화해주세요."),
                    ephemeral=True
                )
            return

        embed = make_embed(f"{inter.user}님의 정보")
        embed.description = (
            f"`만기일` : `{info[2]}`\n"
            f"`이름` : `{info[4]}`\n"
            f"`주민등록번호` : `{info[5]}`\n"
            f"`주소` : `{info[6]}`\n"
            f"`발급일자` : `{info[7]}`\n"
            f"`지역` : `{info[8]}`\n"
            f"`제작 링크` : {domain}/{info[3]}"
        )
        if info[9]:
            embed.set_image(url=info[9])

        dm_ok = await send_dm_safe(inter.user, embed)
        if dm_ok:
            await inter.response.send_message(
                embed=make_embed("✅ 안내", "DM을 확인해주세요."),
                ephemeral=True
            )
        else:
            await inter.response.send_message(
                embed=make_embed("❌ 실패", "DM을 활성화해주세요. (서버 설정 → 개인정보 보호)"),
                ephemeral=True
            )

    elif custom_id == "create_id":
        con, cur = start_db()
        cur.execute("SELECT * FROM users WHERE id = ?;", (inter.user.id,))
        if not cur.fetchone():
            con.close()
            await inter.response.send_message(
                embed=make_embed("❌ 실패", "가입이 필요합니다."),
                ephemeral=True
            )
            return
        con.close()
        await inter.response.send_modal(LicenseModal())

# ==========================================
# 슬래시 커맨드
# ==========================================
@bot.event
async def on_ready():
    print("")
    print("─────────────────────────────────────────────────────")
    print(f"✅ Gov24 실행: {bot.user}")
    print(f"🔗 초대 링크: https://discord.com/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot")
    print(f"🏠 서버: {len(bot.guilds)}개")
    print(f"📝 제작로그 채널: {LOG_CHANNEL_ID}")
    print("─────────────────────────────────────────────────────")

    @app_commands.command(name="메인", description="메인 메뉴를 엽니다 (관리자 전용)")
    async def main_cmd(inter: discord.Interaction):
        if inter.user.id not in admin_id:
            return await inter.response.send_message("❌ 권한이 없습니다.", ephemeral=True)
        embed = discord.Embed(
            title="[Gov24] 24H QR검증 서비스",
            color=0x1a1b1e
        )
        embed.set_footer(text="made by 동하")
        await inter.response.send_message(embed=embed, view=MainMenuView(), ephemeral=False)

    @app_commands.command(name="삭제", description="DM에서 제작 링크를 제외한 모든 메시지를 정리합니다")
    async def clear_dm_cmd(inter: discord.Interaction):
        if not isinstance(inter.channel, discord.DMChannel):
            return await inter.response.send_message("❌ DM에서만 사용할 수 있습니다.", ephemeral=True)
        await inter.response.send_message("✅ 정리 중... 제작 링크는 남겨둡니다.", ephemeral=True)
        deleted_count = 0
        async for msg in inter.channel.history(limit=100):
            keep = False
            if msg.author == bot.user and msg.embeds:
                emb = msg.embeds[0]
                if emb.title and "제작 완료" in emb.title:
                    keep = True
            if not keep:
                try:
                    await msg.delete()
                    deleted_count += 1
                    await asyncio.sleep(0.05)
                except:
                    pass
        await inter.channel.send(f"✅ 정리 완료! {deleted_count}개 메시지 삭제, 제작 링크는 유지됨")

    @app_commands.command(name="생성", description="라이센스 키 생성 (관리자 전용)")
    async def create_cmd(inter: discord.Interaction, 개수: int, 기간: int):
        if inter.user.id not in admin_id:
            return await inter.response.send_message("❌ 권한이 없습니다.", ephemeral=True)
        if not (1 <= 개수 <= 10):
            return await inter.response.send_message("❌ 최대 10개까지 생성 가능합니다.", ephemeral=True)
        con, cur = start_db()
        keys = []
        plain_keys = []
        for _ in range(개수):
            key = str(uuid.uuid4())
            keys.append(f"`{key}`")
            plain_keys.append(key)
            cur.execute("INSERT INTO licenses VALUES (?, ?);", (key, 기간))
        con.commit()
        con.close()

        all_keys_text = "\n".join(plain_keys)

        license_log_channel = bot.get_channel(LICENSE_LOG_CHANNEL_ID)
        if license_log_channel:
            log_embed = make_embed("🔑 라이센스 키 생성")
            log_embed.description = (
                f"`생성자` : `{inter.user}`\n"
                f"`사용자ID` : `{inter.user.id}`\n"
                f"`개수` : `{개수}개`\n"
                f"`기간` : `{기간}일`\n"
                f"`키` :\n```\n{all_keys_text}\n```"
            )
            log_embed.timestamp = datetime.now()
            try:
                await license_log_channel.send(embed=log_embed)
            except Exception as e:
                print(f"라이센스 로그 전송 오류: {e}")

        class CopyAllView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=300)
            @discord.ui.button(label="📋 전체 키 복사", style=discord.ButtonStyle.primary)
            async def copy_all_btn(self, btn_inter: discord.Interaction, button: discord.ui.Button):
                await btn_inter.response.send_message(
                    f"```\n{all_keys_text}\n```\n✅ 위 내용을 복사해서 사용하세요!",
                    ephemeral=True
                )

        await inter.response.send_message(
            embed=make_embed("✅ 생성 완료", f"{개수}개의 키:\n\n{chr(10).join(keys)}\n\n📋 아래 버튼을 누르면 전체 키가 표시됩니다 → 복사해서 사용하세요"),
            view=CopyAllView(),
            ephemeral=True
        )

    @app_commands.command(name="변경", description="유저 정보 수정 (관리자 전용)")
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
        await inter.response.send_message(
            embed=make_embed("✅ 변경 완료", f"{항목}이(가) 변경되었습니다."),
            ephemeral=True
        )

    tree.add_command(main_cmd)
    tree.add_command(clear_dm_cmd)

    async def is_admin(inter: discord.Interaction) -> bool:
        return inter.user.id in admin_id

    create_cmd.checks.append(is_admin)
    tree.add_command(create_cmd)

    edit_cmd.checks.append(is_admin)
    tree.add_command(edit_cmd)

    await tree.sync()
    await bot.change_presence(activity=discord.Game("Gov24 서비스"), status=discord.Status.online)

# ==========================================
# 실행
# ==========================================
bot.run(token)
