import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")  # finished
@login_required
def index():
    """Show portfolio of stocks"""
    portfolio = db.execute("SELECT * FROM portfolio WHERE user_id = ?", session["user_id"]) #user's portfolio of stocks
    temp = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    cash = temp[0]["cash"] #user's current cashd
    temp = db.execute("SELECT symbol FROM portfolio WHERE user_id = ?", session["user_id"]) #making a dictionary of symbols to prices
    prices = {}
    for symbol in temp:
        s = symbol["symbol"]
        price = lookup(s)["price"]
        prices[s] = float(price)
    stock_worth = 0 #get stock worth
    for stock in portfolio:
        stock_worth += (prices[stock["symbol"]] * stock["shares"])
    total = cash + stock_worth

    return render_template("home.html", portfolio=portfolio, prices=prices, cash=cash, total=total) #cash=cash, stock_worth=stock_worth


@app.route("/buy", methods=["GET", "POST"]) #works but doesn't pass 2/4 tests
@login_required
def buy():
    """Buy shares of stock"""

    #if method is post
    if request.method == "POST":

        #get symbol and amount of shares from user
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        #check if input is empty
        if not symbol:
            return apology("must provide symbol", 400)

        #check if shares is empty
        if not shares:
            return apology("must provide shares", 400)

        if int(shares) < 0:
            return apology("must have positive shares", 400)

        #check if valid symbol
        if not lookup(symbol):
            return apology("invalid symbol", 400)

        #check if user can afford the stocks
        price = lookup(symbol)["price"] #get current price of stock
        temp = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        cash = temp[0]["cash"] #getting user's current cash
        if float(price) * float(shares) > float(cash):
            return apology("can't afford", 403)

        #update user's cash
        new_cash = cash - (float(price) * float(shares))
        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_cash, session["user_id"])

        #update portfolio
        #if stock isn't already in portfolio, insert it as a new stock
        x = db.execute("SELECT symbol FROM portfolio WHERE symbol = ?", symbol)
        name = lookup(symbol)["name"]
        if not x:
            db.execute("INSERT INTO portfolio (symbol, name, shares, user_id) VALUES(?, ?, ?, ?)", symbol, name, shares, session["user_id"])

        #else update stock in portfolio
        else:
            temp = db.execute("SELECT shares FROM portfolio WHERE symbol = ? AND user_id = ?", symbol, session["user_id"])
            old_shares = temp[0]["shares"]
            new_shares = int(old_shares) + int(shares)
            db.execute("UPDATE portfolio SET shares = ? WHERE symbol = ? AND user_id = ?", new_shares, symbol, session["user_id"])

        db.execute("INSERT INTO history (symbol, shares, price, user_id) VALUES (?, ?, ?, ?)", symbol, shares, usd(price), session["user_id"])

        #if everything works, return to home page
        return redirect("/")

    #if user is in get method, display page
    else:
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    history = db.execute("SELECT * FROM history WHERE user_id = ?", session["user_id"])
    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"]) #done
@login_required
def quote():
    """Get stock quote."""

    #if user is trying to get quote
    if request.method == "POST":
        symbol = request.form.get("symbol")

        #check if symbol is blank
        if not symbol:
            return apology("missing symbol", 400)

        #check for invalid symbol
        if not lookup(symbol):
            return apology("invalid symbol", 400)

        #return quoted
        quote = lookup(symbol)
        name = quote["name"]
        price = quote["price"]
        s = quote["symbol"]
        return render_template("quoted.html", name=name, symbol=s, price=usd(price))

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"]) #done
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # if user is trying to register
    if request.method == "POST":

        #get username and password
        name = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        #if user name is blank or taken -- taken username doesn't seem to be working
        if not name:
            return apology("username cannot be blank", 400)

        #checking if duplicate username
        username = db.execute("SELECT username FROM users WHERE username = ?", name)
        if username:
            return apology("this username exists already", 400)

        #if password is blank
        if not password:
            return apology("must provide password", 400)

        #if passwords don't match
        if not password == confirmation:
            return apology("passwords do not match", 400)

        if not len(password) >= 5:
            return apology("password length should be at least 5", 400)

        #add user to system and send to home page
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", name, generate_password_hash(password))
        user = db.execute("SELECT * FROM users WHERE username = ?", name)
        session["user_id"] = user[0]["id"]
        return redirect("/")

    # if user wants to visit register page, request.method == "GET"
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":

        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        if not symbol:
            return apology("missing symbol", 400)

        valid = db.execute("SELECT symbol FROM portfolio WHERE user_id = ? AND symbol = ?", session["user_id"], symbol)
        if not valid:
            return apology("invalid symbol", 400)

        if not shares:
            return apology("missing shares", 400)

        if not int(shares) >= 0:
            return apology("invalid shares", 400)

        temp = db.execute("SELECT shares FROM portfolio WHERE symbol = ? AND user_id = ?", symbol, session["user_id"])
        owned_shares = temp[0]["shares"]
        if int(shares) > int(owned_shares):
            return apology("invalid shares", 400)

        new_shares = int(owned_shares) - int(shares)
        db.execute("UPDATE portfolio SET shares = ? WHERE symbol = ? AND user_id = ?", new_shares, symbol, session["user_id"])
        neg_shares = (-1) * int(shares)
        price = lookup(symbol)["price"]
        db.execute("INSERT INTO history (symbol, shares, price, user_id) VALUES (?, ?, ?, ?)", symbol, neg_shares, usd(price), session["user_id"])
        return redirect("/")

    else:
        stocks = db.execute("SELECT symbol FROM portfolio WHERE user_id = ?", session["user_id"])
        return render_template("sell.html", stocks=stocks)