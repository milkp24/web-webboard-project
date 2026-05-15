from flask import Flask, render_template, request, redirect, session
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
import os

app = Flask(__name__)
app.secret_key = "webboard_secret"

bcrypt = Bcrypt(app)

# ---------------- MYSQL (สำหรับ deploy ต้องเปลี่ยนเป็น cloud DB) ----------------
app.config['MYSQL_HOST'] = os.getenv("MYSQL_HOST", "localhost")
app.config['MYSQL_USER'] = os.getenv("MYSQL_USER", "root")
app.config['MYSQL_PASSWORD'] = os.getenv("MYSQL_PASSWORD", "")
app.config['MYSQL_DB'] = os.getenv("MYSQL_DB", "webboard_db")

mysql = MySQL(app)

# ---------------- HOME ----------------
@app.route('/')
def home():
    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM posts ORDER BY id DESC")
    posts = cur.fetchall()

    cur.execute("SELECT * FROM comments")
    comments = cur.fetchall()

    cur.execute("SELECT * FROM likes")
    likes = cur.fetchall()

    cur.close()

    return render_template("index.html",
                           posts=posts,
                           comments=comments,
                           likes=likes)

# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users(username,email,password) VALUES(%s,%s,%s)",
                    (username, email, password))
        mysql.connection.commit()
        cur.close()

        return redirect('/login')

    return render_template("register.html")

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email=%s", [email])
        user = cur.fetchone()
        cur.close()

        if user and bcrypt.check_password_hash(user[3], password):
            session['user'] = user[1]
            return redirect('/')
        else:
            return "Login Failed"

    return render_template("login.html")

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ---------------- CREATE POST ----------------
@app.route('/create', methods=['POST'])
def create():
    if 'user' not in session:
        return redirect('/login')

    title = request.form['title']
    content = request.form['content']

    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO posts(title,content) VALUES(%s,%s)", (title, content))
    mysql.connection.commit()
    cur.close()

    return redirect('/')

# ---------------- COMMENT ----------------
@app.route('/comment/<int:post_id>', methods=['POST'])
def comment(post_id):
    content = request.form['content']

    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO comments(post_id,content) VALUES(%s,%s)", (post_id, content))
    mysql.connection.commit()
    cur.close()

    return redirect('/')

# ---------------- LIKE ----------------
@app.route('/like/<int:post_id>')
def like(post_id):
    if 'user' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM likes WHERE post_id=%s AND user=%s",
                (post_id, session['user']))
    exist = cur.fetchone()

    if not exist:
        cur.execute("INSERT INTO likes(post_id,user) VALUES(%s,%s)",
                    (post_id, session['user']))
        mysql.connection.commit()

    cur.close()
    return redirect('/')

# ---------------- EDIT ----------------
@app.route('/edit/<int:id>')
def edit(id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM posts WHERE id=%s", [id])
    post = cur.fetchone()
    cur.close()

    return render_template("edit.html", post=post)

# ---------------- UPDATE ----------------
@app.route('/update/<int:id>', methods=['POST'])
def update(id):
    title = request.form['title']
    content = request.form['content']

    cur = mysql.connection.cursor()
    cur.execute("UPDATE posts SET title=%s, content=%s WHERE id=%s",
                (title, content, id))
    mysql.connection.commit()
    cur.close()

    return redirect('/')

# ---------------- DEPLOY ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)