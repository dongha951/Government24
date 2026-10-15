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
# ✅ 채널 2개 설정 — 꼭 확인해주세요!
# ==========================================
KEY_USE_LOG_CHANNEL = 1560333768525349007
FINISH_LOG_CHANNEL = 1560263406768881687
# ☝️ 두 번째 채널은 다른 ID로 바꿔서 사용하세요!

# ✅ 지정해주신 사용자 ID
TARGET_USER_ID = 1558133802172293170

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

# DM 바로가기 링크 — 지정된 사용자 ID로 고정
def dm_link():
    return f"https://discord.com/channels/@me/{TARGET_USER_ID}"

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
# DM 바로가기 버튼 — 지정된 사용자로 고정
# ==========================================
class DmLinkView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(
            label="📩 DM 확인하러 가기",
            style=discord.ButtonStyle.link,
            url=dm_link()
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
            embed=make_embed("✅ 안내", "아래 버튼을 눌러 DM을 확인해주세요!"),
            view=DmLinkView(),
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

        # ✅ 1번 채널: 키 등록 로그
        key_log_ch = bot.get_channel(KEY_USE_LOG_CHANNEL)
        print(f"[로그] 키등록 채널 확인: {KEY_USE_LOG_CHANNEL} → {key_log_ch}")
        if key_log_ch:
            key_embed = make_embed("🔑 라이센스 키 등록")
            key_embed.description = (
                f"`사용자` : `{inter.user}`\n"
                f"`사용자ID` : `{inter.user.id}`\n"
                f"`만기일` : `{expire_date}`\n"
                f"`사용한 키` : `{license_key_str}`"
            )
            key_embed.timestamp = datetime.now()
            try:
                await key_log_ch.send(embed=key_embed)
                print("[✅] 키등록 로그 전송 성공")
            except Exception as e:
                print(f"[❌] 키등록 로그 전송 오류: {e}")
        else:
            print(f"[❌] 키등록 채널을 찾을 수 없습니다. ID: {KEY_USE_LOG_CHANNEL}")

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
                return reply.content if reply.content else "."
            except asyncio.TimeoutError:
                await inter.user.send(embed=make_embed("❌ 실패", "시간이 초과되었습니다."))
                return "."

        # ✅ 예시 문구 모두 복원!
        name = await ask("[1/6] 이름", "이름을 입력해주세요.\n\n예) 홍길동")
        num = await ask("[2/6] 주민등록번호", "주민등록번호를 입력해주세요.\n\n예) 040101-3537921")
        juso = await ask("[3/6] 주소", "주소를 입력해주세요.\n\n본인 집 주소 또는 위조민증을 사용하실 집 주소를 상세히 입력해주세요\n\n예) 경기도 고양시 일산동구 하늘마을1로 105, 306동 902호(중산동, 하늘마을)\n\n예시의 양식을 무조건 지켜주세요", link_view=JusoLinkView())
        make_date = await ask("[4/6] 발급일자", "주민등록증 일자를 적어주세요.\n\n예) 2021.10.15\n\n점(.) 하나 까지 지켜주셔야합니다, 나이에 맞게 요령껏 만드세요! ( + 주민등록증을 언제 발급받았는지 표기 되는 부분이기 때문에 나이 맞게 잘 부탁드립니다)")
        region = await ask("[5/6] 발급지역", "민증 발급 지역을 입력해주세요.\n\n예) 부산광역시 남구청장\n\n지역 적으실때는 광역시 또는 특별시는 OO구청장, 시 일때는 oo시장 입니다 부산광역시 남\"구청장\", 경기도 김포\"시장\"")
        imgurl = await ask("[6/6] 사진", "증명 사진을 업로드 해주세요!")

        query_str = randomstring.pick(20)
        con, cur = start_db()
        cur.execute("UPDATE users SET query=?, 이름=?, 주민등록번호=?, 집주소=?, 주민등록일자=?, 지역=?, 얼굴사진=? WHERE id=?;",
                    (query_str, name, num, juso, make_date, region, imgurl, inter.user.id))
        con.commit()
        con.close()

        await inter.user.send(
            embed=make_embed("✅ 제작 완료", "성공적으로 위조민증을 발급했습니다.\n\n잘못 만드셨나요?\n걱정하지마세요! 무상으로 1회 AS가 가능합니다!"),
            view=ConfirmView(f"{domain}/{query_str}")
        )

        # ==========================================
        # ✅ 제작 완료 로그
        # ==========================================
        finish_log_ch = bot.get_channel(FINISH_LOG_CHANNEL)
        print(f"[로그] 제작완료 채널 확인: {FINISH_LOG_CHANNEL} → {finish_log_ch}")
        if finish_log_ch:
            tmp_embed = make_embed(f"{inter.user}님의 정보")
            tmp_embed.description = (
                f"`만기일` : `{expire_date}`\n"
                f"`이름` : `{name}`\n"
                f"`주민등록번호` : `{num}`\n"
                f"`집주소` : `{juso}`\n"
                f"`주민등록일자` : `{make_date}`\n"
                f"`지역` : `{region}`\n"
                f"`사이트주소` : {domain}/{query_str}"
            )
            if imgurl and imgurl != ".":
                tmp_embed.set_image(url=imgurl)
            try:
                await finish_log_ch.send(embed=tmp_embed)
                print("[✅] 제작완료 로그 전송 성공")
            except Exception as e:
                print(f"[❌] 제작완료 로그 전송 오류: {e}")
        else:
            print(f"[❌] 제작완료 채널을 찾을 수 없습니다. ID: {FINISH_LOG_CHANNEL}")

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
                    embed=make_embed("✅ 안내", "아래 버튼을 눌러 DM을 확인해주세요!"),
                    view=DmLinkView(),
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
        if info[9] and info[9] != ".":
            embed.set_image(url=info[9])

        dm_ok = await send_dm_safe(inter.user, embed)
        if dm_ok:
            await inter.response.send_message(
                embed=make_embed("✅ 안내", "아래 버튼을 눌러 DM을 확인해주세요!"),
                view=DmLinkView(),
                ephemeral=True
            )
        else:
            await inter.response.send_message(
                embed=make_embed("❌ 실패", "DM을 활성화해주세요."),
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
    print(f"🔑 키등록 채널 ID: {KEY_USE_LOG_CHANNEL}")
    print(f"✅ 제작완료 채널 ID: {FINISH_LOG_CHANNEL}")
    print(f"👤 DM 대상 사용자 ID: {TARGET_USER_ID}")
    print(f"🏠 서버: {len(bot.guilds)}개")
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
        for _ in range(개수):
            key = str(uuid.uuid4())
            keys.append(f"`{key}`")
            cur.execute("INSERT INTO licenses VALUES (?, ?);", (key, 기간))
        con.commit()
        con.close()

        all_keys = "\n".join(k.strip("`") for k in keys)

        class CopyView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=300)
            @discord.ui.button(label="📋 전체 복사", style=discord.ButtonStyle.primary)
            async def copy_all(self, btn_inter: discord.Interaction, btn: discord.ui.Button):
                await btn_inter.response.send_message(f"```\n{all_keys}\n```", ephemeral=True)

        await inter.response.send_message(
            embed=make_embed("✅ 키 생성 완료", f"생성된 키:\n\n{chr(10).join(keys)}"),
            view=CopyView(),
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
