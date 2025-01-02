from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, lookup, egp, LivePrice
from mysql.connector import connect, Error

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["egp"] = egp

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure MySQL database
def get_db_connection():
    try:
        connection = connect(
            host="db-wallet-asmblxer.g.aivencloud.com",
            port=18977,
            user="avnadmin",
            password="AVNS_IxwKaxHEba4YTBjiCfV",
            database="defaultdb"
        )
        return connection
    except Error as e:
        print("Error while connecting to MySQL", e)
        exit(1)

def init_db():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("CREATE TABLE IF NOT EXISTS users (id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(255) NOT NULL, hash VARCHAR(255) NOT NULL, national_id VARCHAR(255) NOT NULL, cash FLOAT NOT NULL DEFAULT 10000.00)")
    cursor.execute("CREATE TABLE IF NOT EXISTS transactions (id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, karat INT NOT NULL, price FLOAT NOT NULL, weight FLOAT NOT NULL, total FLOAT NOT NULL, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id))")
    connection.commit()
    cursor.close()
    connection.close()

init_db()

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

@app.route("/")
@login_required
def index():
    """Show wallet of logged in user"""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    user_id = session["user_id"]
    cursor.execute("SELECT karat, SUM(weight) as total_weight, SUM(total) as total_price FROM transactions WHERE user_id = %s GROUP BY karat", (user_id,))
    transactions = cursor.fetchall()
    cursor.execute("SELECT cash FROM users WHERE id = %s", (user_id,))
    cash = cursor.fetchone()['cash']
    cursor.close()
    connection.close()
    return render_template("index.html", transactions=transactions, cash=cash)

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        name = request.form.get("username")
        national_id = request.form.get("national_id")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not name:
            return render_template("register.html", message="must provide username")
        if not national_id:
            return render_template("register.html", message="must provide national id")
        if not password:
            return render_template("register.html", message="must provide password")
        if not confirmation:
            return render_template("register.html", message="must provide confirmation password")
        if password != confirmation:
            return render_template("register.html", message="passwords do not match")
            
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (name,))
        result = cursor.fetchall()

        # Clear any unread results
        while cursor.nextset(): pass

        if result:
            cursor.close()
            connection.close()
            return render_template("register.html", message="username already exists")
        
        hash = generate_password_hash(password)
        cursor.execute("INSERT INTO users (username, hash, national_id) VALUES (%s, %s, %s)", (name, hash, national_id))
        connection.commit()
        cursor.close()
        connection.close()
        return redirect("/login")
    return render_template("register.html")



@app.route("/reset", methods=["GET", "POST"])
def reset():
    """Reset password"""
    if request.method == "POST":
        username = request.form.get("username")
        national_id = request.form.get("national_id")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return render_template("reset.html", message="must provide username")
        if not national_id:
            return render_template("reset.html", message="must provide national id")
        if not password:
            return render_template("reset.html", message="must provide password")
        if not confirmation:
            return render_template("reset.html", message="must provide confirmation password")
        if password != confirmation:
            return render_template("reset.html", message="passwords do not match")

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        result = cursor.fetchall()
        if not result:
            cursor.close()
            connection.close()
            return render_template("reset.html", message="username does not exist")
            
        # Clear any unread results
        while cursor.nextset(): pass
            
        cursor.execute("SELECT national_id FROM users WHERE username = %s", (username,))
        _national_id = cursor.fetchone()['national_id']
        
        # Clear any unread results
        while cursor.nextset(): pass
        
        if national_id != _national_id:
            cursor.close()
            connection.close()
            return render_template("reset.html", message="national id does not match")
            
        hash = generate_password_hash(password)
        cursor.execute("UPDATE users SET hash = %s WHERE username = %s", (hash, username))
        connection.commit()
        cursor.close()
        connection.close()
        return redirect("/login")

    return render_template("reset.html")




@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    session.clear()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username:
            return render_template("login.html", message="must provide username")
        if not password:
            return render_template("login.html", message="must provide password")

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        rows = cursor.fetchall()
        cursor.close()
        connection.close()

        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
            return render_template("login.html", message="invalid username and/or password")

        session["user_id"] = rows[0]["id"]
        return redirect("/")
    return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out"""
    session.clear()
    return redirect("/")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell Gold Grams"""
    if request.method == "POST":
        karat = request.form.get("karat")
        weight = request.form.get("weight")

        if not karat:
            return render_template("sell.html", message="must provide karat")
        if not weight or not weight.isdigit() or int(weight) <= 0:
            return render_template("sell.html", message="must provide valid weight")

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        user_id = session["user_id"]
        cursor.execute(
            "SELECT SUM(weight) as total FROM transactions WHERE user_id = %s AND karat = %s",
            (user_id, karat)
        )
        owned_gold = cursor.fetchone()['total']

        if owned_gold is None or owned_gold < float(weight):
            cursor.close()
            connection.close()
            return render_template("sell.html", message="not enough gold to sell")

        karat_price = LivePrice(karat)
        if karat_price is None:
            cursor.close()
            connection.close()
            return render_template("sell.html", message="invalid karat")

        total = karat_price * float(weight)
        cursor.execute("SELECT cash FROM users WHERE id = %s", (user_id,))
        cash = cursor.fetchone()['cash']

        cursor.execute("UPDATE users SET cash = %s WHERE id = %s", (cash + total, user_id))
        cursor.execute(
            "INSERT INTO transactions (user_id, karat, price, weight, total) VALUES (%s, %s, %s, %s, %s)",
            (user_id, karat, karat_price, -float(weight), -total)
        )
        connection.commit()
        cursor.close()
        connection.close()
        return redirect("/")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        "SELECT karat FROM transactions WHERE user_id = %s GROUP BY karat",
        (session["user_id"],)
    )
    karats = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template("sell.html", karats=karats)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        karat = request.form.get("karat")
        weight = request.form.get("weight")

        if not karat:
            return render_template("buy.html", message="must provide karat")
        if not weight or not weight.isdigit() or int(weight) <= 0:
            return render_template("buy.html", message="must provide valid weight")

        karat_price = LivePrice(karat)
        if not karat_price:
            return render_template("buy.html", message="invalid karat")

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        user_id = session["user_id"]
        total = karat_price * float(weight)
        cursor.execute("SELECT cash FROM users WHERE id = %s", (user_id,))
        cash = cursor.fetchone()['cash']

        if cash < total:
            cursor.close()
            connection.close()
            return render_template("buy.html", message="not enough cash to buy")

        cursor.execute("UPDATE users SET cash = %s WHERE id = %s", (cash - total, user_id))
        cursor.execute(
            "INSERT INTO transactions (user_id, karat, weight, price, total) VALUES (%s, %s, %s, %s, %s)",
            (user_id, karat, weight, karat_price, total)
        )
        connection.commit()
        cursor.close()
        connection.close()
        return redirect("/")
    return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM transactions WHERE user_id = %s", (session["user_id"],))
    transactions = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template("history.html", transactions=transactions)

if __name__ == "__main__":
    app.run(debug=True)