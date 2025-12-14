from flask import Blueprint, request, jsonify, session, render_template
import sqlite3, requests, time
from datetime import datetime
from collections import deque

stock_bp = Blueprint('stock_bp', __name__)
DB_PATH = 'userstocks.db' 
FINNHUB_API_KEY = "d3p21ipr01quo6o6g38gd3p21ipr01quo6o6g390"

refresh_count = 0

def get_db_connection():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

# ---------------- Add Stock ----------------
@stock_bp.route('/add_stock', methods=['POST'])
def add_stock():
    user_id = session.get('user_id')
    stock_symbol = (request.get_json() or {}).get('stock_symbol') or request.form.get('stock_symbol')

    if not user_id or not stock_symbol:
        return jsonify({'error': 'Missing user_id or stock_symbol'}), 400

    stock_symbol = stock_symbol.upper().strip()

    con = get_db_connection()
    cur = con.cursor()

    cur.execute("SELECT * FROM user_stocks WHERE user_id=? AND stock_symbol=?", (user_id, stock_symbol))
    if cur.fetchone():
        con.close()
        return jsonify({'message': 'Stock already added'})

    cur.execute("INSERT INTO user_stocks (user_id, stock_symbol) VALUES (?, ?)", (user_id, stock_symbol))
    con.commit()
    con.close()

    return jsonify({'message': 'Stock added successfully', 'stock_symbol': stock_symbol})

# ---------------- Get Stocks ----------------
@stock_bp.route('/get_stocks', methods=['GET'])
def get_stocks():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not logged in'}), 401

    con = get_db_connection()
    cur = con.cursor()
    cur.execute("SELECT stock_symbol FROM user_stocks WHERE user_id=?", (user_id,))
    stocks = [row['stock_symbol'] for row in cur.fetchall()]
    con.close()

    return jsonify({'stocks': stocks})

# ---------------- Remove Stock ----------------
@stock_bp.route('/remove_stock', methods=['POST'])
def remove_stock():
    user_id = session.get('user_id')
    stock_symbol = request.json.get('stock_symbol')

    if not user_id or not stock_symbol:
        return jsonify({'error': 'Missing parameters'}), 400

    con = get_db_connection()
    cur = con.cursor()
    cur.execute("DELETE FROM user_stocks WHERE user_id=? AND stock_symbol=?", (user_id, stock_symbol))
    con.commit()
    con.close()

    return jsonify({'message': 'Stock removed successfully'})

# Keep last 14 candles per stock
ohlc_data = {}

def add_candle(stock_symbol, candle):
    if stock_symbol not in ohlc_data:
        ohlc_data[stock_symbol] = deque(maxlen=14)
    
    ohlc_data[stock_symbol].append(candle)

    # Once we have 14 data points, print ready message
    if len(ohlc_data[stock_symbol]) == 14:
        print(f"{stock_symbol}: Ready for calculation ✅")

#------------find stock details in finnhub-----
@stock_bp.route("/stock/data/<stock_symbol>")
def get_price(stock_symbol):
    global refresh_count
    refresh_count += 1
    now = datetime.now().strftime("%H:%M:%S")

    print(f"{refresh_count} → Fetching data for {stock_symbol.upper()} at {now}")

    url = f"https://finnhub.io/api/v1/quote?symbol={stock_symbol}&token={FINNHUB_API_KEY}"
    res = requests.get(url)
    data = res.json()

    if "c" not in data:
        return jsonify({"error": "No data found"}), 404

    # Build one candle
    candle_data = {
        "time": now,
        "open": data.get("o"),
        "high": data.get("h"),
        "low": data.get("l"),
        "close": data.get("c"),
        "previous_close": data.get("pc")
    }

    # Store in memory list per stock
    symbol = stock_symbol.upper()
    if symbol not in ohlc_data:
        ohlc_data[symbol] = []

    ohlc_data[symbol].append(candle_data)

    # Keep only 14
    if len(ohlc_data[symbol]) > 14:
        ohlc_data[symbol].pop(0)

    print(f"{symbol} → Stored candles: {len(ohlc_data[symbol])}")

    # Return JSON to match your JS
    return jsonify({
        "symbol": symbol,
        "current": candle_data["close"],
        "open": candle_data["open"],
        "high": candle_data["high"],
        "low": candle_data["low"],
        "previous_close": candle_data["previous_close"],
        "history": ohlc_data[symbol]         # Important addition
    })
# ---------------- Stock Page ----------------
@stock_bp.route("/stock/<symbol>")
def stock_page(symbol):
    symbol = symbol.upper()
    return render_template("stock.html", stock_symbol=symbol)

