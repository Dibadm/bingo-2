import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional
from contextlib import contextmanager
import config

_local = threading.local()


def get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(config.DB_PATH), timeout=10)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


@contextmanager
def tx():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            phone TEXT,
            lang TEXT DEFAULT 'en',
            balance REAL DEFAULT 0,
            total_deposited REAL DEFAULT 0,
            total_withdrawn REAL DEFAULT 0,
            total_games_played INTEGER DEFAULT 0,
            total_games_won INTEGER DEFAULT 0,
            referred_by INTEGER,
            referral_code TEXT UNIQUE,
            referral_count INTEGER DEFAULT 0,
            last_transfer_time REAL DEFAULT 0,
            last_daily_bonus TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            balance_before REAL NOT NULL,
            balance_after REAL NOT NULL,
            ref TEXT,
            status TEXT DEFAULT 'completed',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            phone TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            admin_id INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS deposit_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL UNIQUE,
            last4 TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            usage_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_fee INTEGER NOT NULL,
            status TEXT DEFAULT 'waiting',
            prize_pool REAL DEFAULT 0,
            called_numbers TEXT DEFAULT '',
            current_number INTEGER DEFAULT 0,
            winner_ids TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            started_at TEXT,
            ended_at TEXT
        );

        CREATE TABLE IF NOT EXISTS game_players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            card_count INTEGER DEFAULT 0,
            auto_win INTEGER DEFAULT 0,
            has_won INTEGER DEFAULT 0,
            prize_amount REAL DEFAULT 0,
            FOREIGN KEY(game_id) REFERENCES games(id),
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            UNIQUE(game_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS game_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            card_index INTEGER NOT NULL,
            numbers TEXT NOT NULL,
            marked TEXT DEFAULT '',
            has_line INTEGER DEFAULT 0,
            has_corners INTEGER DEFAULT 0,
            FOREIGN KEY(game_id) REFERENCES games(id)
        );

        CREATE TABLE IF NOT EXISTS game_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            number INTEGER NOT NULL,
            called_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(game_id) REFERENCES games(id)
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS used_references (
            ref TEXT PRIMARY KEY,
            used_at TEXT DEFAULT (datetime('now'))
        );

        INSERT OR IGNORE INTO settings(key, value) VALUES ('deposit_account_index', '0');
        INSERT OR IGNORE INTO settings(key, value) VALUES ('house_commission', '0.20');
        INSERT OR IGNORE INTO settings(key, value) VALUES ('call_interval', '2');
        """)

        for acct in config.DEPOSIT_ACCOUNTS:
            conn.execute(
                "INSERT OR IGNORE INTO deposit_accounts(name, phone, last4) VALUES (?, ?, ?)",
                (acct["name"], acct["phone"], acct["last4"]),
            )


def get_setting(key: str, default: str = "") -> str:
    cur = get_conn().execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    get_conn().execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", (key, value))


def get_user(user_id: int) -> Optional[sqlite3.Row]:
    cur = get_conn().execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    return cur.fetchone()


def create_user(user_id: int, referred_by: int = None):
    ref_code = f"HB{user_id:x}".upper()
    get_conn().execute(
        "INSERT OR IGNORE INTO users(user_id, referred_by, referral_code) VALUES (?, ?, ?)",
        (user_id, referred_by, ref_code),
    )


def set_user_phone(user_id: int, phone: str):
    get_conn().execute("UPDATE users SET phone=? WHERE user_id=?", (phone, user_id))


def set_user_lang(user_id: int, lang: str):
    get_conn().execute("UPDATE users SET lang=? WHERE user_id=?", (lang, user_id))


def atomic_balance_update(user_id: int, delta: float, tx_type: str, ref: str = None) -> float:
    with tx() as conn:
        row = conn.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            raise ValueError("User not found")
        balance_before = row["balance"]
        balance_after = balance_before + delta
        if balance_after < 0:
            raise ValueError("Insufficient balance")
        conn.execute("UPDATE users SET balance=? WHERE user_id=?", (balance_after, user_id))
        conn.execute(
            "INSERT INTO transactions(user_id, type, amount, balance_before, balance_after, ref) VALUES (?,?,?,?,?,?)",
            (user_id, tx_type, delta, balance_before, balance_after, ref),
        )
        if tx_type == "deposit":
            conn.execute(
                "UPDATE users SET total_deposited = total_deposited + ? WHERE user_id=?",
                (delta, user_id),
            )
        elif tx_type == "withdrawal":
            conn.execute(
                "UPDATE users SET total_withdrawn = total_withdrawn + ? WHERE user_id=?",
                (abs(delta), user_id),
            )
    return balance_after


def add_referral_bonus(referrer_id: int, amount: float):
    atomic_balance_update(referrer_id, amount, "referral_bonus")
    get_conn().execute(
        "UPDATE users SET referral_count = referral_count + 1 WHERE user_id=?",
        (referrer_id,),
    )


def get_transactions(user_id: int, limit: int = 20) -> list:
    cur = get_conn().execute(
        "SELECT * FROM transactions WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    )
    return cur.fetchall()


def get_all_users() -> list:
    return get_conn().execute("SELECT * FROM users").fetchall()


def get_user_count() -> int:
    row = get_conn().execute("SELECT COUNT(*) as cnt FROM users").fetchone()
    return row["cnt"]


# --- Deposit Accounts ---
def get_deposit_accounts() -> list:
    return get_conn().execute(
        "SELECT * FROM deposit_accounts WHERE is_active=1 ORDER BY id"
    ).fetchall()


def get_current_deposit_account():
    idx = int(get_setting("deposit_account_index", "0"))
    accounts = get_deposit_accounts()
    if not accounts:
        return config.DEPOSIT_ACCOUNTS[0]
    account = accounts[idx % len(accounts)]
    return {"name": account["name"], "phone": account["phone"], "last4": account["last4"]}


def rotate_deposit_account():
    accounts = get_deposit_accounts()
    if not accounts:
        return
    idx = (int(get_setting("deposit_account_index", "0")) + 1) % len(accounts)
    set_setting("deposit_account_index", str(idx))
    acct = accounts[idx]
    get_conn().execute(
        "UPDATE deposit_accounts SET usage_count = usage_count + 1 WHERE id=?",
        (acct["id"],),
    )


def add_deposit_account(name: str, phone: str, last4: str):
    get_conn().execute(
        "INSERT INTO deposit_accounts(name, phone, last4) VALUES (?,?,?)",
        (name, phone, last4),
    )


def remove_deposit_account(acct_id: int):
    get_conn().execute("UPDATE deposit_accounts SET is_active=0 WHERE id=?", (acct_id,))


# --- Withdrawals ---
def create_withdrawal(user_id: int, amount: float, phone: str):
    get_conn().execute(
        "INSERT INTO withdrawals(user_id, amount, phone) VALUES (?,?,?)",
        (user_id, amount, phone),
    )


def get_pending_withdrawals() -> list:
    return get_conn().execute(
        "SELECT w.*, u.phone as user_phone FROM withdrawals w JOIN users u ON w.user_id=u.user_id WHERE w.status='pending' ORDER BY w.created_at ASC"
    ).fetchall()


def approve_withdrawal(wid: int, admin_id: int):
    with tx() as conn:
        w = conn.execute("SELECT * FROM withdrawals WHERE id=?", (wid,)).fetchone()
        if not w or w["status"] != "pending":
            return False
        conn.execute(
            "UPDATE withdrawals SET status='approved', admin_id=?, updated_at=datetime('now') WHERE id=?",
            (admin_id, wid),
        )
    return True


def reject_withdrawal(wid: int, admin_id: int):
    with tx() as conn:
        w = conn.execute("SELECT * FROM withdrawals WHERE id=?", (wid,)).fetchone()
        if not w or w["status"] != "pending":
            return False, ""
        conn.execute(
            "UPDATE withdrawals SET status='rejected', admin_id=?, updated_at=datetime('now') WHERE id=?",
            (admin_id, wid),
        )
        atomic_balance_update(w["user_id"], w["amount"], "withdrawal_refund", ref=f"wd_refund_{wid}")
    return True


# --- References ---
def is_ref_used(ref: str) -> bool:
    cur = get_conn().execute("SELECT 1 FROM used_references WHERE ref=?", (ref,))
    return cur.fetchone() is not None


def mark_ref_used(ref: str):
    get_conn().execute("INSERT OR IGNORE INTO used_references(ref) VALUES (?)", (ref,))


# --- Games ---
def create_game(room_fee: int) -> int:
    cur = get_conn().execute(
        "INSERT INTO games(room_fee, status) VALUES (?, 'waiting')", (room_fee,)
    )
    return cur.lastrowid


def get_game(game_id: int) -> Optional[sqlite3.Row]:
    return get_conn().execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone()


def get_active_game_for_room(room_fee: int) -> Optional[sqlite3.Row]:
    cur = get_conn().execute(
        "SELECT * FROM games WHERE room_fee=? AND status IN ('waiting','playing') ORDER BY id DESC LIMIT 1",
        (room_fee,),
    )
    return cur.fetchone()


def get_room_card_count(room_fee: int) -> int:
    game = get_active_game_for_room(room_fee)
    if not game:
        return 0
    cur = get_conn().execute(
        "SELECT COALESCE(SUM(card_count),0) as cnt FROM game_players WHERE game_id=?",
        (game["id"],),
    )
    return cur.fetchone()["cnt"]


def get_room_player_count(room_fee: int) -> int:
    game = get_active_game_for_room(room_fee)
    if not game:
        return 0
    cur = get_conn().execute(
        "SELECT COUNT(*) as cnt FROM game_players WHERE game_id=?", (game["id"],)
    )
    return cur.fetchone()["cnt"]


def add_game_player(game_id: int, user_id: int, card_count: int):
    get_conn().execute(
        "INSERT OR REPLACE INTO game_players(game_id, user_id, card_count) VALUES (?,?,?)",
        (game_id, user_id, card_count),
    )


def get_game_player(game_id: int, user_id: int) -> Optional[sqlite3.Row]:
    return get_conn().execute(
        "SELECT * FROM game_players WHERE game_id=? AND user_id=?", (game_id, user_id)
    ).fetchone()


def get_game_players(game_id: int) -> list:
    return get_conn().execute(
        "SELECT gp.*, u.lang FROM game_players gp JOIN users u ON gp.user_id=u.user_id WHERE gp.game_id=?",
        (game_id,),
    ).fetchall()


def add_game_card(game_id: int, user_id: int, card_index: int, numbers: list):
    get_conn().execute(
        "INSERT INTO game_cards(game_id, user_id, card_index, numbers) VALUES (?,?,?,?)",
        (game_id, user_id, card_index, ",".join(map(str, numbers))),
    )


def get_user_cards_in_game(game_id: int, user_id: int) -> list:
    return get_conn().execute(
        "SELECT * FROM game_cards WHERE game_id=? AND user_id=? ORDER BY card_index",
        (game_id, user_id),
    ).fetchall()


def get_all_game_cards(game_id: int) -> list:
    return get_conn().execute(
        "SELECT * FROM game_cards WHERE game_id=? ORDER BY card_index", (game_id,)
    ).fetchall()


def update_card_marked(game_id: int, user_id: int, card_index: int, marked: list):
    get_conn().execute(
        "UPDATE game_cards SET marked=? WHERE game_id=? AND user_id=? AND card_index=?",
        (",".join(map(str, marked)), game_id, user_id, card_index),
    )


def set_card_win(game_id: int, user_id: int, card_index: int, has_line: bool, has_corners: bool):
    get_conn().execute(
        "UPDATE game_cards SET has_line=?, has_corners=? WHERE game_id=? AND user_id=? AND card_index=?",
        (1 if has_line else 0, 1 if has_corners else 0, game_id, user_id, card_index),
    )


def set_game_winners(game_id: int, winner_ids: list):
    get_conn().execute(
        "UPDATE games SET winner_ids=? WHERE id=?", (",".join(map(str, winner_ids)), game_id)
    )
    for uid in winner_ids:
        get_conn().execute(
            "UPDATE game_players SET has_won=1 WHERE game_id=? AND user_id=?",
            (game_id, uid),
        )
        get_conn().execute(
            "UPDATE users SET total_games_won = total_games_won + 1 WHERE user_id=?",
            (uid,),
        )


def set_game_prize(game_id: int, user_id: int, amount: float):
    get_conn().execute(
        "UPDATE game_players SET prize_amount=? WHERE game_id=? AND user_id=?",
        (amount, game_id, user_id),
    )


def add_called_number(game_id: int, number: int):
    get_conn().execute(
        "INSERT INTO game_numbers(game_id, number) VALUES (?,?)", (game_id, number)
    )
    game = get_game(game_id)
    called = game["called_numbers"].split(",") if game["called_numbers"] else []
    called.append(str(number))
    get_conn().execute(
        "UPDATE games SET called_numbers=?, current_number=? WHERE id=?",
        (",".join(called), number, game_id),
    )


def get_called_numbers(game_id: int) -> list:
    game = get_game(game_id)
    if not game or not game["called_numbers"]:
        return []
    return [int(x) for x in game["called_numbers"].split(",") if x]


def set_game_status(game_id: int, status: str):
    col = ""
    if status == "playing" and get_game(game_id)["started_at"] is None:
        col = ", started_at=datetime('now')"
    elif status in ("ended", "refunded"):
        col = ", ended_at=datetime('now')"
    get_conn().execute(f"UPDATE games SET status=?{col} WHERE id=?", (status, game_id))


def update_game_prize_pool(game_id: int):
    cur = get_conn().execute(
        "SELECT COALESCE(SUM(gp.card_count * g.room_fee),0) as pool FROM game_players gp JOIN games g ON gp.game_id=g.id WHERE gp.game_id=?",
        (game_id,),
    )
    total = cur.fetchone()["pool"]
    get_conn().execute("UPDATE games SET prize_pool=? WHERE id=?", (total, game_id))


def get_game_stats() -> dict:
    conn = get_conn()
    total_games = conn.execute("SELECT COUNT(*) as c FROM games").fetchone()["c"]
    total_collected = conn.execute(
        "SELECT COALESCE(SUM(prize_pool),0) as c FROM games WHERE status IN ('ended','refunded')"
    ).fetchone()["c"]
    total_profit = conn.execute(
        "SELECT COALESCE(SUM(prize_pool * 0.2),0) as c FROM games WHERE status='ended'"
    ).fetchone()["c"]
    total_players = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    return {
        "total_games": total_games,
        "total_collected": total_collected,
        "total_profit": total_profit,
        "total_players": total_players,
    }


def get_daily_games() -> list:
    return get_conn().execute(
        "SELECT strftime('%H', created_at) as hour, COUNT(*) as cnt FROM games WHERE created_at > datetime('now', '-7 days') GROUP BY hour ORDER BY hour"
    ).fetchall()


def get_leaderboard(limit: int = 10) -> list:
    return get_conn().execute(
        "SELECT user_id, total_games_won, total_deposited FROM users ORDER BY total_games_won DESC LIMIT ?",
        (limit,),
    ).fetchall()
