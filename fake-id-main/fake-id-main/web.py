from flask import Flask, render_template, request, redirect, url_for, session, abort
import sqlite3
from datetime import datetime

app = Flask(__name__)

def get_expiretime(time_str):
    try:
        server_time = datetime.now()
        expire_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
        
        diff = expire_time - server_time
        if diff.total_seconds() > 0:
            days = diff.days
            hours = diff.seconds // 3600
            minutes = (diff.seconds // 60) % 60
            return f"{days}일 {hours}시간 {minutes}분"
        return False
    except:
        return False

def is_expired(time_str):
    try:
        server_time = datetime.now()
        expire_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
        return server_time > expire_time
    except:
        return True

@app.before_request
def log_user_ip():
    if request.path == '/favicon.ico':
        return
        
    user_ip = request.remote_addr
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"{user_ip}:{current_time}\n"
    
    try:
        with open('ip.log', "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Logging Error: {e}")

@app.route('/favicon.ico')
def favicon():
    return abort(404)

@app.route('/<code>')
def index(code):
    user_info = None
    try:
        with sqlite3.connect("./database.db") as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM users WHERE query = ?;", (code,))
            user_info = cur.fetchone()
    except Exception as e:
        print(f"DB Error: {e}")
        return render_template("error.html", title="시스템 오류", dese="데이터베이스 연결에 실패했습니다.")

    if user_info is None:
        return render_template("error.html", title="접속 실패", dese="존재하지 않거나 삭제된 주소입니다.")

    if is_expired(user_info[2]):
        try:
            with sqlite3.connect("./database.db") as con:
                cur = con.cursor()
                cur.execute("UPDATE users SET query = ? WHERE id = ?;", (None, user_info[0]))
                con.commit()
        except:
            pass
        return render_template("error.html", title="접속 실패", dese="라이센스 유효기간이 만료되었습니다.")

    try:
        tmp = user_info[5].split("-")[0]
        date_str = f"{tmp[0:2]}.{tmp[2:4]}.{tmp[4:6]}"
    except:
        date_str = "00.00.00"

    return render_template("sex.html", 
                           name=user_info[4], 
                           num=user_info[5], 
                           date=date_str, 
                           juso=user_info[6], 
                           make=user_info[7], 
                           jiname=user_info[8], 
                           imgurl=user_info[9])

if __name__ == '__main__':
    from waitress import serve
    serve(app, host="0.0.0.0", port=10000, threads=16)
