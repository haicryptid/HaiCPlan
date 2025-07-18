from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import random
import string

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# ---------------- 사용자 로그인/회원 시스템 ----------------

def init_user_db():
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            emoji TEXT DEFAULT ''
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        role = request.form['role']
        
        # 관리자 인증 키 확인
        if role == 'admin':
            admin_key = request.form.get('admin_key', '')
            if admin_key != 'admin123':
                return "❌ 관리자 인증 키가 올바르지 않습니다!"

        conn = sqlite3.connect('data.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                      (username, password, role))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "이미 존재하는 사용자입니다!"
        conn.close()
        return redirect(url_for('login'))
    return render_template('register.html')


from flask import render_template, request, redirect, url_for, session

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None  # 에러 메시지 초기화
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('data.db')
        c = conn.cursor()
        c.execute("SELECT password, role, emoji FROM users WHERE username=?", (username,))
        result = c.fetchone()
        conn.close()

        if result and check_password_hash(result[0], password):
            session['username'] = username
            session['role'] = result[1]
            session['emoji'] = result[2]
            return redirect(url_for('welcome'))
        else:
            error = "로그인 실패! 아이디나 비밀번호를 확인해주세요!"
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# 프로필 페이지 (이미지 관련 코드 제거됨)
@app.route('/profile')
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('profile.html')

# 프로필 업데이트 (이미지 관련 코드 제거됨)
@app.route('/update_profile', methods=['POST'])
def update_profile():
    new_username = request.form['new_username']
    new_password = request.form['new_password']
    emoji = request.form.get('emoji')

    conn = sqlite3.connect('data.db')
    c = conn.cursor()

    c.execute("SELECT * FROM users WHERE username=?", (session['username'],))
    user = c.fetchone()

    if user:
        if new_password:
            hashed_pw = generate_password_hash(new_password)
            c.execute("UPDATE users SET password=? WHERE username=?", (hashed_pw, session['username']))

        # new_username이 있을 때만 처리
        if new_username and new_username != session['username']:
            c.execute("SELECT * FROM users WHERE username=?", (new_username,))
            if c.fetchone():
                conn.close()
                return "이미 존재하는 아이디입니다."
            
            c.execute("UPDATE users SET username=? WHERE username=?", (new_username, session['username']))
            c.execute("UPDATE schedules SET username=? WHERE username=?", (new_username, session['username']))
            
            session['username'] = new_username

        # emoji 업데이트
        c.execute("UPDATE users SET emoji=? WHERE username=?", (emoji, session['username']))
        session['emoji'] = emoji

        conn.commit()

    conn.close()
    return redirect(url_for('profile'))


# 계정 삭제


@app.route('/delete_account', methods=['POST'])
def delete_account():
    username = session['username']
    conn = sqlite3.connect('data.db')
    c = conn.cursor()

    c.execute('DELETE FROM schedules WHERE username = ?', (username,))

    c.execute('DELETE FROM users WHERE username = ?', (username,))
    conn.commit()
    conn.close()
    session.clear()
    return redirect(url_for('index'))

# ---------------- 일정 관리 기능 ----------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/welcome')
def welcome():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('welcome.html', username=session['username'])

@app.route('/submit', methods=['GET', 'POST'])
def submit():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        task = request.form['task']
        deadline = request.form['deadline']
        username = session['username']

        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO schedules (name, task, deadline, username) VALUES (?, ?, ?, ?)', (name, task, deadline, username))
        conn.commit()
        conn.close()

        return render_template('success.html', message="일정이 등록되었습니다!", next_url=url_for('view'))
        
    return render_template('submit.html')

@app.route('/view')
def view():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()

    if session['role'] == 'admin':
        cursor.execute("SELECT id, name, task, deadline, username FROM schedules")
    else:
        cursor.execute("SELECT id, name, task, deadline, username FROM schedules WHERE username=?", (session['username'],))

    schedules = cursor.fetchall()
    conn.close()
    
    return render_template('view.html', schedules=schedules, role=session['role'])

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()

    cursor.execute('SELECT username FROM schedules WHERE id=?', (id,))
    result = cursor.fetchone()
    if not result:
        return "일정이 존재하지 않습니다."
    schedule_owner = result[0]

    if session['role'] != 'admin' and schedule_owner != session['username']:
        return "권한이 없습니다."

    if request.method == 'POST':
        name = request.form['name']
        task = request.form['task']
        deadline = request.form['deadline']
        cursor.execute('UPDATE schedules SET name=?, task=?, deadline=? WHERE id=?',
                       (name, task, deadline, id))
        conn.commit()
        conn.close()
        return redirect(url_for('view'))
    else:
        cursor.execute('SELECT name, task, deadline FROM schedules WHERE id=?', (id,))
        schedule = cursor.fetchone()
        conn.close()
        return render_template('edit.html', schedule=schedule, id=id)

@app.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()

    cursor.execute('SELECT username FROM schedules WHERE id=?', (id,))
    result = cursor.fetchone()
    if not result:
        return "일정이 존재하지 않습니다."
    schedule_owner = result[0]

    if session['role'] != 'admin' and schedule_owner != session['username']:
        return "권한이 없습니다."

    cursor.execute('DELETE FROM schedules WHERE id=?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('view'))

# -------------관리자만 접근 가능한 페이지-------------

@app.route('/admin')
def admin_users():
    if session.get('role') != 'admin':
        return "⚠️ 관리자만 접근할 수 있습니다!"

    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute("SELECT id, username, role, emoji FROM users")
    users = c.fetchall()
    conn.close()

    return render_template('admin.html', users=users)

@app.route('/admin/reset_password/<int:user_id>', methods=['POST'])
def reset_password(user_id):
    if session.get('role') != 'admin':
        return "⚠️ 관리자만 접근할 수 있습니다!"

    # 임시 비밀번호 생성
    new_password = 'HaiC' + ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    hashed_pw = generate_password_hash(new_password)

    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute("UPDATE users SET password=? WHERE id=?", (hashed_pw, user_id))
    conn.commit()
    conn.close()

    return f"✅ 비밀번호 초기화 완료! 임시 비밀번호: <b>{new_password}</b>"

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if session.get('role') != 'admin':
        return "⚠️ 관리자만 접근할 수 있습니다!"

    conn = sqlite3.connect('data.db')
    c = conn.cursor()

    # schedules 테이블에는 user_id 없고 username만 저장되어있음
	# 그래서 먼저 user_id에 해당하는 username 찾아주기
    c.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    result = c.fetchone()

    if result:
        username = result[0]

        # 일정 먼저 삭제
        c.execute("DELETE FROM schedules WHERE username = ?", (username,))

        # 사용자 삭제
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))

        conn.commit()

    conn.close()
    return redirect(url_for('admin_users'))



# ---------------- DB 초기화 및 실행 ----------------

def init_schedule_db():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            task TEXT NOT NULL,
            deadline TEXT NOT NULL,
            username TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

if __name__ == '__main__':
    
    init_user_db()
    init_schedule_db()
    app.run(host = '0.0.0.0', port=5001, debug=True)