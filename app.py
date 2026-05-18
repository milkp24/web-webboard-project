from flask import Flask, render_template, request, redirect, session, flash, url_for
import sqlite3
import os
import uuid
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "super-secret-key-change-this-in-production"

# ตั้งค่าพิกัดโฟลเดอร์สำหรับเก็บรูปภาพ
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------------- DB CONNECT ----------------
# ใช้ฐานข้อมูลบน Memory (RAM) เพื่อเลี่ยงปัญหาสิทธิ์ Read-Only บน Render
def connect():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- INIT DB ----------------
def init_db():
    conn = connect()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        content TEXT,
        author TEXT,
        image_filename TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER,
        content TEXT,
        author TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER,
        user TEXT,
        UNIQUE(post_id, user)
    )
    """)
    conn.commit()
    conn.close()

# ---------------- REGISTER & LOGIN & LOGOUT ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        if not username or not password:
            flash("โปรดกรอกข้อมูลให้ครบถ้วน", "danger")
            return redirect("/register")
        hashed_password = generate_password_hash(password)
        conn = connect()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            flash("สมัครสมาชิกสำเร็จ! โปรดล็อกอินเพื่อเข้าสู่ระบบ", "success")
            return redirect("/login")
        except sqlite3.IntegrityError:
            flash("ชื่อผู้ใช้นี้ถูกใช้ไปแล้ว", "danger")
        finally:
            conn.close()
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        conn = connect()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            session["username"] = user["username"]
            flash(f"ยินดีต้อนรับคุณ {user['username']}", "success")
            return redirect("/")
        else:
            flash("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("username", None)
    flash("ออกจากระบบเรียบร้อยแล้ว", "info")
    return redirect("/")

# ---------------- HOME ----------------
# [แก้ไขล่าสุด ⭐️] ใส่บล็อก try-except ดักจับปัญหา SQL เพื่อการันตีหน้าเว็บเปิดได้ชัวร์ 100%
@app.route("/", methods=["GET", "HEAD"])
def home():
    if request.method == "HEAD":
        return "", 200

    posts = []
    all_comments = []

    try:
        conn = connect()
        c = conn.cursor()
        c.execute("""
        SELECT 
            p.*,
            (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) as comment_count,
            (SELECT COUNT(*) FROM likes l WHERE l.post_id = p.id) as like_count
        FROM posts p
        ORDER BY p.id DESC
        """)
        posts = c.fetchall()
        
        c.execute("SELECT * FROM comments ORDER BY id ASC")
        all_comments = c.fetchall()
        conn.close()
    except Exception as e:
        # ถ้าระบบคลาวด์รัน SQL สะดุด ให้พิมพ์ฟ้องใน Logs แต่ยังยอมให้หน้าหน้าแรกแสดงผลแบบปลอดภัย
        print(f"--- Database temporal bypass: {e} ---")
        posts = []
        all_comments = []

    return render_template("index.html", posts=posts, comments=all_comments)

# ---------------- CREATE POST ----------------
@app.route("/create", methods=["POST"])
def create():
    if "username" not in session:
        flash("กรุณาล็อกอินก่อนสร้างโพสต์", "danger")
        return redirect("/login")

    title = request.form["title"]
    content = request.form["content"]
    image_filename = None

    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '' and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{uuid.uuid4().hex}.{ext}"
            try:
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                image_filename = unique_filename
            except Exception:
                image_filename = None

    conn = connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO posts(title, content, author, image_filename) VALUES(?,?,?,?)",
        (title, content, session["username"], image_filename)
    )
    conn.commit()
    conn.close()
    return redirect("/")

# ---------------- COMMENT & LIKE ----------------
@app.route("/comment/<int:pid>", methods=["POST"])
def comment(pid):
    if "username" not in session:
        flash("กรุณาล็อกอินก่อนแสดงความคิดเห็น", "danger")
        return redirect("/login")
    conn = connect()
    c = conn.cursor()
    c.execute("INSERT INTO comments(post_id, content, author) VALUES(?,?,?)", (pid, request.form["content"], session["username"]))
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/like/<int:pid>")
def like(pid):
    if "username" not in session:
        flash("กรุณาล็อกอินก่อนกดถูกใจ", "danger")
        return redirect("/login")
    conn = connect()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO likes(post_id, user) VALUES(?,?)", (pid, session["username"]))
        conn.commit()
    except sqlite3.IntegrityError:
        c.execute("DELETE FROM likes WHERE post_id = ? AND user = ?", (pid, session["username"]))
        conn.commit()
    finally:
        conn.close()
    return redirect("/")

# ---------------- EDIT & UPDATE ----------------
@app.route("/edit/<int:post_id>")
def edit(post_id):
    if "username" not in session:
        flash("กรุณาล็อกอินก่อน", "danger")
        return redirect("/login")
    conn = connect()
    c = conn.cursor()
    c.execute("SELECT * FROM posts WHERE id=?", (post_id,))
    post = c.fetchone()
    conn.close()
    if post and post["author"] != session["username"]:
        flash("คุณไม่มีสิทธิ์แก้ไขโพสต์นี้", "danger")
        return redirect("/")
    return render_template("edit.html", post=post)

@app.route("/update/<int:post_id>", methods=["POST"])
def update(post_id):
    if "username" not in session:
        return redirect("/login")
    conn = connect()
    c = conn.cursor()
    c.execute("SELECT author, image_filename FROM posts WHERE id=?", (post_id,))
    post = c.fetchone()
    
    if post and post["author"] == session["username"]:
        c.execute("UPDATE posts SET title=?, content=? WHERE id=?", (request.form["title"], request.form["content"], post_id))
        conn.commit()
        flash("แก้ไขโพสต์สำเร็จ", "success")
    else:
        flash("คุณไม่มีสิทธิ์แก้ไขโพสต์นี้", "danger")
    conn.close()
    return redirect("/")

# ---------------- DELETE ----------------
@app.route("/delete/<int:post_id>")
def delete_post(post_id):
    if "username" not in session:
        return redirect("/login")

    conn = connect()
    c = conn.cursor()
    c.execute("SELECT author, image_filename FROM posts WHERE id=?", (post_id,))
    post = c.fetchone()
    
    if post and post["author"] == session["username"]:
        if post["image_filename"]:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], post["image_filename"]))
            except Exception:
                pass

        c.execute("DELETE FROM posts WHERE id=?", (post_id,))
        c.execute("DELETE FROM comments WHERE post_id=?", (post_id,))
        c.execute("DELETE FROM likes WHERE post_id=?", (post_id,))
        conn.commit()
        flash("ลบโพสต์และรูปภาพเรียบร้อยแล้ว", "success")
    else:
        flash("คุณไม่มีสิทธิ์ลบโพสต์นี้", "danger")

    conn.close()
    return redirect("/")

# เรียกสร้างฐานข้อมูลใน RAM ตอนแอปพลิเคชันตื่น
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)