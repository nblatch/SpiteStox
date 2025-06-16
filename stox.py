import streamlit as st  # type: ignore
import pandas as pd     # type: ignore
import os
from supabase import create_client, Client
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from streamlit_autorefresh import st_autorefresh
import time

# --- Supabase Setup ---
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://dfhuqxvvyajbsawmmlzb.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRmaHVxeHZ2eWFqYnNhd21tbHpiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk5OTkzODgsImV4cCI6MjA2NTU3NTM4OH0.BRcyjG1pyVHvHogImc6atbICfAFddQ7KCM6VUniLVUU")  # Replace with actual secure key
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Game Config ---
MAX_SHARES_PER_STOX = 100
starting_balance = 15000
starting_price = 300
tickers = ['ANGL', 'ARYE', 'DANL', 'DRNC', 'ELLI', 'FRDY', 'JIN', 'RCHL']

st.set_page_config(page_title="Spite Stox Market", layout="wide")

# --- Load Prices ---
if "stox_df" not in st.session_state:
    response = supabase.table("prices").select("*").execute()
    prices = response.data

    if not prices:
        # Insert default prices if table is empty
        default_prices = [{"ticker": t, "price": starting_price, "original_price": starting_price} for t in tickers]
        supabase.table("prices").insert(default_prices).execute()
        # Re-fetch from Supabase after insert
        prices = supabase.table("prices").select("*").execute().data

    st.session_state.stox_df = pd.DataFrame(prices)

stox_df = st.session_state.stox_df

# --- Original Prices ---
if "original_prices" not in st.session_state:
    st.session_state.original_prices = {
        row["ticker"]: row["original_price"]
        for row in stox_df.to_dict(orient="records")
    }

# --- Price History ---
if "price_history" not in st.session_state:
    st.session_state.price_history = {row["ticker"]: [] for row in stox_df.to_dict(orient="records")}

# --- Players & Holdings ---
if "players" not in st.session_state:
    players = {}
    name_to_id = {}

    # Load all players from Supabase
    player_records = supabase.table("players").select("*").execute().data
    for p in player_records:
        players[p["name"]] = {
            "id": p["id"],  # Store UUID for use in foreign key lookups
            "balance": p["balance"],
            "holdings": {}
        }
        name_to_id[p["name"]] = p["id"]

    # Load holdings and match by player_id
    holdings_records = supabase.table("holdings").select("*").execute().data
    for h in holdings_records:
        for name, pdata in players.items():
            if h["player_id"] == pdata["id"]:
                pdata["holdings"][h["ticker"]] = h["quantity"]

    # Ensure all tickers are initialized
    for pdata in players.values():
        for t in tickers:
            pdata["holdings"].setdefault(t, 0)

    st.session_state.players = players
    st.session_state.name_to_id = name_to_id

# --- Transactions ---
if "transactions" not in st.session_state:
    txs = supabase.table("transactions").select("*").order("time", desc=False).execute().data
    st.session_state.transactions = [
        {
            "Player": t["player"],
            "Action": t["action"],
            "Stock": t["stock"],
            "Qty": t["qty"],
            "price": t["price"],
            "Total": t["total"],
            "Time": t["time"],
            "Memo": t.get("memo", "")
        } for t in txs
    ]

# Store stock price DataFrame
stox_df = st.session_state.stox_df

# --- Load Past Transactions from Supabase ---
if not st.session_state.transactions:
    tx_response = supabase.table("transactions").select("*").order("time", desc=False).execute()

    if tx_response.data:
        st.session_state.transactions = [
            {
                "Player": tx["player"],
                "Action": tx["action"],
                "Stock": tx["stock"],
                "Qty": tx["qty"],
                "price": tx["price"],
                "Total": tx["total"],
                "Time": tx["time"],
                "Memo": tx.get("memo", "")
            }
            for tx in tx_response.data
        ]

# --- Helper Functions ---
def show_player_info(player):
    st.markdown(f"<div style='text-align: center;'>💰 <strong>Balance</strong>: ₣{player['balance']}<br>📦 <strong>Holdings</strong>: {player['holdings']}</div>", unsafe_allow_html=True)

def calculate_net_worth(player):
    return player["balance"] + sum(
        player["holdings"][ticker] * stox_df.loc[stox_df["ticker"] == ticker, "price"].values[0]
        for ticker in player["holdings"]
    )

# --- App Header ---
st.title("🐟 Spite Stox Exchange")
st.markdown("Welcome to our own hate-fueled chaos market!")

# --- Leaderboard ---
leaderboard = [{"Player": name, "Net Worth": calculate_net_worth(p), "Balance": p["balance"]}
               for name, p in st.session_state.players.items()]
col1, col2 = st.columns(2)

# --- Market Overview ---
st.markdown("<h2 style='text-align: center;'>Market Overview</h2>", unsafe_allow_html=True)
col1, col2 = st.columns(2)

# --- Prepare styled stox data ---
styled_data = []
for ticker in stox_df["ticker"]:
    current_price = stox_df.loc[stox_df["ticker"] == ticker, "price"].values[0]
    original_price = st.session_state.original_prices.get(ticker, current_price)

    # Calculate % change
    pct_change = ((current_price - original_price) / original_price) * 100
    pct_str = f"{pct_change:+.2f}%"

    # Calculate available shares
    total_held = sum(p["holdings"].get(ticker, 0) for p in st.session_state.players.values())
    shares_available = MAX_SHARES_PER_STOX - total_held

    styled_data.append({
        "ticker": ticker,
        "price": current_price,
        "% Change": pct_str,
        "Available": shares_available
    })

# --- Left Column: Stox prices ---
with col1:
    st.markdown("### 📈 Current Stox prices")

    table_data = []
    for ticker in stox_df["ticker"]:
        current_price = stox_df.loc[stox_df["ticker"] == ticker, "price"].values[0]
        original_price = st.session_state.original_prices.get(ticker, current_price)

        pct_change = ((current_price - original_price) / original_price) * 100
        pct_str = f"{pct_change:+.2f}%"

        total_held = sum(p["holdings"].get(ticker, 0) for p in st.session_state.players.values())
        shares_available = MAX_SHARES_PER_STOX - total_held

        table_data.append({
            "ticker": ticker,
            "price": f"₣{current_price}",
            "% Change": pct_str,
            "Available": f"{shares_available} left"
        })

    df_stox = pd.DataFrame(table_data)

    def highlight_changes(val):
        if isinstance(val, str) and "%" in val:
            if "+" in val:
                return "color: limegreen;"
            elif "-" in val:
                return "color: crimson;"
        return ""

    st.dataframe(
        df_stox.style.applymap(highlight_changes, subset=["% Change"]),
        use_container_width=True
    )

# --- Right Column: Leaderboard ---
with col2:
    st.markdown("### 🏆 Leaderboard")
    if leaderboard:
        leaderboard_df = pd.DataFrame(leaderboard)
        leaderboard_df = leaderboard_df.sort_values(by="Net Worth (₣)", ascending=False)
        st.dataframe(leaderboard_df, use_container_width=True)
    else:
        st.info("No players in the game yet. Buy or sell to get on the board!")

# --- Most Loved / Hated Stocks ---
most_bought = {}
most_sold = {}
for t in st.session_state.transactions:
    ticker = t["Stock"]
    qty = t["Qty"]
    if t["Action"] == "BUY":
        most_bought[ticker] = most_bought.get(ticker, 0) + qty
    elif t["Action"] == "SELL":
        most_sold[ticker] = most_sold.get(ticker, 0) + qty

# --- Display Most Loved & Most Hated Section ---
st.markdown("<h3 style='text-align: center;'>Most Loved & Hated Stox</h3>", unsafe_allow_html=True)

loved_col, hated_col = st.columns(2)

with loved_col:
    if most_bought:
        loved_stock = max(most_bought, key=most_bought.get)
        loved_count = most_bought[loved_stock]
        st.success(f"💚 Most Loved: {loved_stock} with {loved_count} shares bought 💚")

        top_buys = sorted(most_bought.items(), key=lambda x: x[1], reverse=True)[:3]
        st.markdown("#### Top 3 Most Bought:")
        st.table(pd.DataFrame(top_buys, columns=["Stock", "Shares Bought"]))
    else:
        st.info("No love yet. No stox have been bought.")

with hated_col:
    if most_sold:
        hated_stock = max(most_sold, key=most_sold.get)
        hated_count = most_sold[hated_stock]
        st.error(f"💔 Most Hated: {hated_stock} with {hated_count} shares sold 💔")

        top_sells = sorted(most_sold.items(), key=lambda x: x[1], reverse=True)[:3]
        st.markdown("#### Top 3 Most Sold:")
        st.table(pd.DataFrame(top_sells, columns=["Stock", "Shares Sold"]))
    else:
        st.info("No hate yet. No stox have been sold.")


# --- 📈 Unified Stox price History (Filtered + Animated) ---
from streamlit_autorefresh import st_autorefresh
import matplotlib.dates as mdates

# Enable auto-refresh every 10 seconds (comment out to disable)
st_autorefresh(interval=10 * 1000, key="auto_refresh")

st.markdown("<h3 style='text-align: center;'>Stox price History</h3>", unsafe_allow_html=True)

# Dropdown to filter stox
all_tickers = list(st.session_state.price_history.keys())
selected_tickers = st.multiselect(
    "Select Stox to Display:",
    options=all_tickers,
    default=all_tickers,
    key="stox_filter"
)

# Flatten price history into DataFrame
all_data = []
for ticker, records in st.session_state.price_history.items():
    if ticker not in selected_tickers:
        continue
    for entry in records:
        all_data.append({
            "Time": entry["Time"],
            "price": entry["price"],
            "ticker": ticker
        })

if len(all_data) >= 2:
    df_all = pd.DataFrame(all_data)
    df_all["Time"] = pd.to_datetime(df_all["Time"])

    fig, ax = plt.subplots(figsize=(10, 3))
    fig.patch.set_facecolor('#0e1117')
    ax.set_facecolor('#0e1117')

    for ticker in selected_tickers:
        df_ticker = df_all[df_all["ticker"] == ticker]
        if not df_ticker.empty:
            ax.plot(df_ticker["Time"], df_ticker["price"],
                    label=ticker, linewidth=1.5, marker='o', markersize=4)

    ax.set_title("Stox price History (Filtered)", fontsize=10, color='white')
    ax.set_xlabel("Time", fontsize=8, color='gray')
    ax.set_ylabel("price (₣)", fontsize=8, color='gray')
    ax.tick_params(axis='both', colors='gray', labelsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

    ax.spines['bottom'].set_color('gray')
    ax.spines['left'].set_color('gray')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    ax.legend(title="Stox", fontsize=8, title_fontsize=9, facecolor='#0e1117', edgecolor='gray', labelcolor='white')
    fig.tight_layout()
    st.pyplot(fig)
else:
    st.info("Not enough price history for selected stox to display chart.")

# --- Player Input ---
st.markdown("<h2 style='text-align: center;'>Trade Stox</h2>", unsafe_allow_html=True)
with st.container():
    centered_col = st.columns([3, 2, 3])[1]
    with centered_col:
        player_name = st.text_input("Your name")

if player_name:
    if player_name not in st.session_state.players:
        st.session_state.players[player_name] = {
            "balance": starting_balance,
            "holdings": {ticker: 0 for ticker in stox_df["ticker"]}
        }

        # --- Supabase Write: Save new player ---
        supabase.table("players").upsert([{
            "name": player_name,
            "balance": starting_balance
        }]).execute()

    player = st.session_state.players[player_name]
    show_player_info(player)

# --- Buy & Sell Columns ---
buy_col, sell_col = st.columns(2)

with buy_col:
    st.markdown("### 🟢 Buy Shares")
    selected_stock = st.selectbox("Which stox to buy?", stox_df["ticker"])
    price = stox_df.loc[stox_df["ticker"] == selected_stock, "price"].values[0]
    broker_fee = 5

    buy_mode = st.radio("Buy mode:", ["By quantity", "By amount"], horizontal=True)

    if buy_mode == "By quantity":
        quantity = st.number_input("How many to buy?", min_value=1, step=1)
        total_cost = price * quantity + broker_fee
    else:
        spend_amount = st.number_input("How much to spend? (₣)", min_value=price + broker_fee, step=1)
        quantity = int((spend_amount - broker_fee) // price)
        total_cost = quantity * price + broker_fee

    st.markdown(f"💸 {quantity}x ₣{price} + ₣{broker_fee} = ₣{total_cost}", unsafe_allow_html=True)
    memo = st.text_input("Reason for buying?")

    if st.button("Place Buy Order"):
        available = MAX_SHARES_PER_STOX - sum(p["holdings"].get(selected_stock, 0) for p in st.session_state.players.values())

        if quantity < 1:
            st.error("❌ That amount won’t buy a single stox.")
        elif quantity > available:
            st.error(f"❌ Only {available} shares of {selected_stock} are available.")
        elif player["balance"] >= total_cost:
            player["balance"] -= total_cost
            player["holdings"][selected_stock] += quantity

            new_price = round(price * (1 + 0.01 * quantity))
            st.session_state.stox_df.loc[stox_df["ticker"] == selected_stock, "price"] = new_price

            # 🔁 Update Supabase
            player_id = st.session_state.name_to_id[player_name]

            supabase.table("prices").update({"price": new_price}).eq("ticker", selected_stock).execute()

            supabase.table("transactions").insert([{
                "player_id": player_id,
                "action": "BUY",
                "ticker": selected_stock,
                "qty": quantity,
                "price": price,
                "total": total_cost,
                "time": datetime.now().isoformat(),
                "memo": memo
            }]).execute()

            supabase.table("holdings").upsert([{
                "player_id": player_id,
                "ticker": selected_stock,
                "quantity": player["holdings"][selected_stock]
            }]).execute()

            st.success(f"✅ {player_name} bought {quantity}x {selected_stock} for ₣{total_cost}!")
            show_player_info(player)
            time.sleep(1)
            st.rerun()
        else:
            st.error("❌ Not enough funds.")

with sell_col:
    st.markdown("### 🔴 Sell Shares")
    sell_stock = st.selectbox("Which stox to sell?", stox_df["ticker"], key="sell_stock")
    sell_price = stox_df.loc[stox_df["ticker"] == sell_stock, "price"].values[0]
    broker_fee = 5

    sell_mode = st.radio("Sell mode:", ["By quantity", "By amount"], horizontal=True, key="sell_mode")

    if sell_mode == "By quantity":
        sell_quantity = st.number_input("How many to sell?", min_value=1, step=1, key="sell_qty")
        earnings = sell_price * sell_quantity - broker_fee
    else:
        sell_amount = st.number_input("How much value to sell? (₣)", min_value=sell_price + broker_fee, step=1, key="sell_amt")
        sell_quantity = int((sell_amount - broker_fee) // sell_price)
        earnings = sell_quantity * sell_price - broker_fee

    st.markdown(f"💰 Sell earnings: ₣{earnings} after fee", unsafe_allow_html=True)
    sell_memo = st.text_input("Reason for selling?", key="sell_memo")

    if st.button("Sell Shares"):
        owned_qty = player["holdings"].get(sell_stock, 0)

        if sell_quantity < 1:
            st.error("❌ That won’t sell anything.")
        elif sell_quantity > owned_qty:
            st.error(f"❌ You only own {owned_qty} shares of {sell_stock}.")
        else:
            player["balance"] += earnings
            player["holdings"][sell_stock] -= sell_quantity

            new_price = max(1, round(sell_price * (1 - 0.01 * sell_quantity)))
            st.session_state.stox_df.loc[stox_df["ticker"] == sell_stock, "price"] = new_price

            # 🔁 Update Supabase
            player_id = st.session_state.name_to_id[player_name]

            supabase.table("prices").update({"price": new_price}).eq("ticker", sell_stock).execute()

            supabase.table("transactions").insert([{
                "player_id": player_id,
                "action": "SELL",
                "ticker": sell_stock,
                "qty": sell_quantity,
                "price": sell_price,
                "total": earnings,
                "time": datetime.now().isoformat(),
                "memo": sell_memo
            }]).execute()

            supabase.table("holdings").upsert([{
                "player_id": player_id,
                "ticker": sell_stock,
                "quantity": player["holdings"][sell_stock]
            }]).execute()

            st.success(f"✅ {player_name} sold {sell_quantity}x {sell_stock} for ₣{earnings}!")
            show_player_info(player)
            st.rerun()

# --- 💼 My Portfolio ---
if player_name:
    st.markdown("<h3 style='text-align: center;'>💼 Your Portfolio</h3>", unsafe_allow_html=True)

    holdings = player["holdings"]
    rows = []
    portfolio_total = 0

    for ticker, qty in holdings.items():
        if qty > 0:
            current_price = stox_df.loc[stox_df["ticker"] == ticker, "price"].values[0]
            total_value = qty * current_price
            portfolio_total += total_value
            rows.append({
                "Stox": ticker,
                "Shares Held": qty,
                "Current price (₣)": current_price,
                "Total Value (₣)": total_value
            })

    if rows:
        portfolio_df = pd.DataFrame(rows)
        st.dataframe(portfolio_df, use_container_width=True)

        st.markdown(
            f"<div style='text-align: right; font-size: 16px; font-weight: bold; margin-top: 10px;'>"
            f"💰 Total Holdings Value: ₣{portfolio_total:,}"
            f"</div>",
            unsafe_allow_html=True
        )
    else:
        st.info("You don’t own any stox yet. Time to get spiteful.")

# --- Transaction History ---
if player_name:
    st.markdown("<h3 style='text-align: center;'>Your Transaction History</h3>", unsafe_allow_html=True)
    player_history = [t for t in st.session_state.transactions if t["Player"] == player_name]
    if player_history:
        st.dataframe(pd.DataFrame(player_history[::-1]), use_container_width=True)
    else:
        st.info("You haven't made any trades yet.")


# --- 📢 Market Feed: Player Memos ---
with st.sidebar.expander("Market Feed: Player Memos", expanded=True):
    st.markdown("Spite is best served publicly.")

    # Show most recent 10 trades with memos
    recent_memos = [
        t for t in reversed(st.session_state.transactions)
        if t.get("Memo") and t["Memo"].strip()
    ][:10]

    if recent_memos:
        for t in recent_memos:
            action_word = "bought" if t["Action"] == "BUY" else "sold"
            action_emoji = "🟢" if t["Action"] == "BUY" else "🔴"
            st.markdown(f"""
            {action_emoji} **{t['Player']}** {action_word} **{t['Qty']}x {t['Stock']}**  
            📝 *"{t['Memo']}"*  
            ⏰ `{t['Time']}`
            ---
            """)
    else:
        st.info("No memos yet.")

# --- 🔁 Reset Game Button ---
st.markdown("---")
st.markdown("<h4 style='text-align: center;'>Danger Zone</h4>", unsafe_allow_html=True)
st.warning("⚠️ Hitting this button will wipe the entire market. Portfolios? Gone. Memos? Vaporized. Drama? Reset. Proceed only if the group unanimously agrees... or if you're feeling *really* spiteful.")

if st.button("💥 Reset Game"):
    # Clear Supabase tables
    supabase.table("transactions").delete().neq("id", 0).execute()
    supabase.table("holdings").delete().neq("id", 0).execute()
    supabase.table("players").delete().neq("id", 0).execute()
    supabase.table("prices").delete().neq("id", 0).execute()

    # Clear local session state
    for key in ["players", "transactions", "stox_df", "price_history", "original_prices"]:
        if key in st.session_state:
            del st.session_state[key]

    st.success("💥 The market has been obliterated.")
    st.rerun()

