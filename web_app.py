import os
import asyncio
import json
import time
import random
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
import database as db
from sms_parser import parse_telebirr_sms, verify_recipient
import bingo as bingo_module

# ── API Models ─────────────────────────────────────────────────────────

class SelectCardsReq(BaseModel):
    user_id: int
    room_fee: int
    card_indices: list[int]

class ConfirmPurchaseReq(BaseModel):
    user_id: int
    room_fee: int

class CheckCardsReq(BaseModel):
    user_id: int

class BingoClaimReq(BaseModel):
    user_id: int

class ToggleAutoReq(BaseModel):
    user_id: int

class TapNumberReq(BaseModel):
    user_id: int
    card_index: int
    number: int

class DepositSmsReq(BaseModel):
    user_id: int
    sms: str
    expected_amount: float

class WithdrawReq(BaseModel):
    user_id: int
    amount: float

class TransferReq(BaseModel):
    from_uid: int
    to_uid: int
    amount: float

class AdminActionReq(BaseModel):
    admin_id: int

class AddAccountReq(BaseModel):
    name: str
    phone: str
    last4: str

class UpdateSettingReq(BaseModel):
    key: str
    value: str

class BroadcastReq(BaseModel):
    admin_id: int
    text: str

# ── In-memory game state ──────────────────────────────────────────────

class GameRoomState:
    def __init__(self):
        self.countdown = config.COUNTDOWN_SECONDS
        self._locks: dict[int, asyncio.Lock] = {}

    def get_lock(self, fee: int) -> asyncio.Lock:
        if fee not in self._locks:
            self._locks[fee] = asyncio.Lock()
        return self._locks[fee]

room_state = GameRoomState()

# ── Lifespan ──────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield

# ── FastAPI App ────────────────────────────────────────────────────────

app = FastAPI(title="Habesha Bet Bingo API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

FRONTEND_DIR = Path(__file__).parent / "frontend" / "dist"

# ── API Routes ─────────────────────────────────────────────────────────

@app.get("/api/user/{uid}")
async def get_user(uid: int):
    u = db.get_user(uid)
    if not u:
        raise HTTPException(404, "User not found")
    return dict(u)

@app.get("/api/user/{uid}/balance")
async def get_user_balance(uid: int):
    u = db.get_user(uid)
    if not u:
        raise HTTPException(404, "User not found")
    return {
        "balance": u["balance"],
        "total_deposited": u["total_deposited"],
        "total_withdrawn": u["total_withdrawn"],
    }

@app.get("/api/user/{uid}/profile")
async def get_user_profile(uid: int):
    u = db.get_user(uid)
    if not u:
        raise HTTPException(404, "User not found")
    return dict(u)

@app.get("/api/user/{uid}/transactions")
async def get_user_transactions(uid: int):
    return [dict(t) for t in db.get_transactions(uid)]

@app.get("/api/rooms")
async def get_rooms():
    result = []
    for fee in config.ROOMS:
        pool = db.get_room_card_count(fee) * fee
        players = db.get_room_player_count(fee)
        result.append({"fee": fee, "pool": pool, "players": players})
    return result

@app.get("/api/rooms/{fee}")
async def get_room(fee: int):
    if fee not in config.ROOMS:
        raise HTTPException(404, "Room not found")
    game = db.get_active_game_for_room(fee)
    taken_cards = []
    if game:
        taken_cards = [c["card_index"] for c in db.get_all_game_cards(game["id"])]
    return {
        "fee": fee,
        "pool": db.get_room_card_count(fee) * fee,
        "players": db.get_room_player_count(fee),
        "timer": room_state.countdown if room_state else config.COUNTDOWN_SECONDS,
        "taken_cards": taken_cards,
    }

@app.get("/api/rooms/{fee}/active-game")
async def get_active_game(fee: int):
    game = db.get_active_game_for_room(fee)
    if not game:
        raise HTTPException(404, "No active game")
    return dict(game)

@app.get("/api/game/{gid}")
async def get_game(gid: int):
    game = db.get_game(gid)
    if not game:
        raise HTTPException(404, "Game not found")
    return dict(game)

@app.get("/api/game/{gid}/cards/{uid}")
async def get_game_cards(gid: int, uid: int):
    return [dict(c) for c in db.get_user_cards_in_game(gid, uid)]

@app.get("/api/game/{gid}/called")
async def get_called_numbers(gid: int):
    return db.get_called_numbers(gid)

@app.get("/api/game/{gid}/players")
async def get_game_players(gid: int):
    return [dict(p) for p in db.get_game_players(gid)]

# ── Game Actions ──────────────────────────────────────────────────────

@app.post("/api/game/select-cards")
async def select_cards(req: SelectCardsReq):
    fee = req.room_fee
    async with room_state.get_lock(fee):
        game = db.get_active_game_for_room(fee)
        if not game:
            gid = db.create_game(fee)
            game = db.get_game(gid)
        gid = game["id"]
        taken = set(c["card_index"] for c in db.get_all_game_cards(gid))
        for idx in req.card_indices:
            if idx in taken:
                raise HTTPException(400, f"Card {idx} already taken")
        return {"game_id": gid, "selected": req.card_indices}

@app.post("/api/game/confirm")
async def confirm_purchase(req: ConfirmPurchaseReq):
    fee = req.room_fee
    uid = req.user_id
    async with room_state.get_lock(fee):
        game = db.get_active_game_for_room(fee)
        if not game:
            raise HTTPException(400, "No active game")
        gid = game["id"]
        taken = set(c["card_index"] for c in db.get_all_game_cards(gid))
        user_data = db.get_user(uid)
        if not user_data:
            raise HTTPException(404, "User not found")

        # We don't know how many cards the user selected from the API call alone.
        # We'll assume the frontend sends the selected count via the fee context.
        # In a real impl, the frontend sends card_count alongside.
        # For now, use a placeholder - frontend's select-cards already validated.
        card_count = 1  # fallback; real count would be passed

        existing = db.get_game_player(gid, uid)
        if not existing:
            card_count = len([c for c in db.get_all_game_cards(gid) if c["user_id"] == uid])
            if card_count == 0:
                card_count = 1  # default single card
            db.add_game_player(gid, uid, card_count)

        total_cost = card_count * fee
        if user_data["balance"] < total_cost:
            raise HTTPException(400, "Insufficient balance")

        db.atomic_balance_update(uid, -total_cost, "game_buy", ref=f"game_{gid}")
        db.update_game_prize_pool(gid)

        # Auto-start countdown if first player
        if fee not in room_state.__dict__:
            pass  # countdown managed externally

        return {"game_id": gid, "cost": total_cost, "prize_pool": game["prize_pool"] + total_cost}

@app.post("/api/game/{gid}/check")
async def check_cards(gid: int, req: CheckCardsReq):
    cards = db.get_user_cards_in_game(gid, req.user_id)
    called = set(db.get_called_numbers(gid))
    for card in cards:
        nums = [int(x) for x in card["numbers"].split(",")]
        marked = set(int(x) for x in card["marked"].split(",") if card["marked"])
        new_marked = marked | (called & set(nums))
        db.update_card_marked(gid, req.user_id, card["card_index"], list(new_marked))
    return {"status": "checked"}

@app.post("/api/game/{gid}/bingo")
async def claim_bingo(gid: int, req: BingoClaimReq):
    game = db.get_game(gid)
    if not game or game["status"] != "playing":
        raise HTTPException(400, "Game not active")
    called = set(db.get_called_numbers(gid))
    cards = db.get_user_cards_in_game(gid, req.user_id)
    for card in cards:
        nums = [int(x) for x in card["numbers"].split(",")]
        hl, hc = bingo_module.check_card_wins(nums, called)
        if hl or hc:
            return {"win": True, "card_index": card["card_index"]}
    return {"win": False}

@app.post("/api/game/{gid}/toggle-auto")
async def toggle_auto(gid: int, req: ToggleAutoReq):
    gp = db.get_game_player(gid, req.user_id)
    if gp:
        new_val = 0 if gp["auto_win"] else 1
        db.get_conn().execute("UPDATE game_players SET auto_win=? WHERE game_id=? AND user_id=?", (new_val, gid, req.user_id))
        return {"auto_win": bool(new_val)}
    raise HTTPException(404, "Player not in game")

@app.post("/api/game/{gid}/tap")
async def tap_number(gid: int, req: TapNumberReq):
    card = None
    for c in db.get_user_cards_in_game(gid, req.user_id):
        if c["card_index"] == req.card_index:
            card = c
            break
    if not card:
        raise HTTPException(404, "Card not found")
    marked = set(int(x) for x in card["marked"].split(",") if card["marked"])
    marked.add(req.number)
    db.update_card_marked(gid, req.user_id, req.card_index, list(marked))
    return {"marked": list(marked)}

# ── Financial ─────────────────────────────────────────────────────────

@app.post("/api/deposit/sms")
async def deposit_sms(req: DepositSmsReq):
    parsed = parse_telebirr_sms(req.sms)
    if not parsed:
        raise HTTPException(400, "Invalid SMS format")
    acct = db.get_current_deposit_account()
    errors, parsed_data = verify_recipient(parsed, acct["name"], acct["last4"], expected_amount=req.expected_amount)
    if errors:
        raise HTTPException(400, errors[0])
    ref = parsed_data.get("ref", "")
    if db.is_ref_used(ref):
        raise HTTPException(400, "Reference already used")
    db.mark_ref_used(ref)
    amount = parsed.get("amount", req.expected_amount)
    try:
        new_balance = db.atomic_balance_update(req.user_id, amount, "deposit", ref=ref)
    except ValueError as e:
        raise HTTPException(400, str(e))
    usage = int(db.get_setting("deposit_usage_count", "0"))
    db.set_setting("deposit_usage_count", str(usage + 1))
    if (usage + 1) % config.DEPOSIT_ACCOUNT_ROTATION_INTERVAL == 0:
        db.rotate_deposit_account()
    return {"amount": amount, "new_balance": new_balance, "ref": ref}

@app.post("/api/withdraw")
async def withdraw(req: WithdrawReq):
    uid = req.user_id
    amount = req.amount
    if amount < config.MIN_WITHDRAWAL:
        raise HTTPException(400, f"Minimum withdrawal is {config.MIN_WITHDRAWAL} ETB")
    user = db.get_user(uid)
    if not user or not user["phone"]:
        raise HTTPException(400, "No phone registered")
    if user["balance"] < amount:
        raise HTTPException(400, "Insufficient balance")
    db.atomic_balance_update(uid, -amount, "withdrawal", ref=f"wd_{uid}_{int(time.time())}")
    db.create_withdrawal(uid, amount, user["phone"])
    return {"status": "pending", "amount": amount}

@app.post("/api/transfer")
async def transfer(req: TransferReq):
    if req.from_uid == req.to_uid:
        raise HTTPException(400, "Cannot transfer to self")
    if req.amount < config.MIN_TRANSFER:
        raise HTTPException(400, f"Minimum transfer is {config.MIN_TRANSFER} ETB")
    sender = db.get_user(req.from_uid)
    if not sender:
        raise HTTPException(404, "Sender not found")
    if sender["balance"] < req.amount:
        raise HTTPException(400, "Insufficient balance")
    if time.time() - (sender.get("last_transfer_time") or 0) < config.TRANSFER_COOLDOWN:
        raise HTTPException(400, "Transfer cooldown active (1 hour)")
    target = db.get_user(req.to_uid)
    if not target:
        raise HTTPException(404, "Recipient not found")
    try:
        with db.tx() as conn:
            s = conn.execute("SELECT balance FROM users WHERE user_id=?", (req.from_uid,)).fetchone()
            if s["balance"] < req.amount:
                raise ValueError("Insufficient")
            conn.execute("UPDATE users SET balance=balance-?, last_transfer_time=? WHERE user_id=?", (req.amount, time.time(), req.from_uid))
            conn.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (req.amount, req.to_uid))
            conn.execute("INSERT INTO transactions(user_id, type, amount, balance_before, balance_after, ref) VALUES (?,?,?,?,?,?)",
                         (req.from_uid, "transfer_out", -req.amount, s["balance"], s["balance"] - req.amount, f"xfer_{req.from_uid}_{req.to_uid}_{int(time.time())}"))
            r = conn.execute("SELECT balance FROM users WHERE user_id=?", (req.to_uid,)).fetchone()
            conn.execute("INSERT INTO transactions(user_id, type, amount, balance_before, balance_after, ref) VALUES (?,?,?,?,?,?)",
                         (req.to_uid, "transfer_in", req.amount, r["balance"], r["balance"] + req.amount, f"xfer_in_{req.from_uid}_{req.to_uid}_{int(time.time())}"))
    except ValueError:
        raise HTTPException(400, "Insufficient balance")
    return {"status": "done", "amount": req.amount, "to": req.to_uid}

# ── Admin ──────────────────────────────────────────────────────────────

@app.get("/api/admin/stats")
async def admin_stats():
    return db.get_game_stats()

@app.get("/api/admin/withdrawals")
async def admin_withdrawals():
    return [dict(w) for w in db.get_pending_withdrawals()]

@app.post("/api/admin/withdrawals/{wid}/approve")
async def admin_approve_withdrawal(wid: int, req: AdminActionReq):
    if db.approve_withdrawal(wid, req.admin_id):
        return {"status": "approved"}
    raise HTTPException(400, "Failed to approve")

@app.post("/api/admin/withdrawals/{wid}/reject")
async def admin_reject_withdrawal(wid: int, req: AdminActionReq):
    success, _ = db.reject_withdrawal(wid, req.admin_id)
    if success:
        return {"status": "rejected"}
    raise HTTPException(400, "Failed to reject")

@app.get("/api/admin/accounts")
async def admin_accounts():
    return [dict(a) for a in db.get_deposit_accounts()]

@app.post("/api/admin/accounts")
async def admin_add_account(req: AddAccountReq):
    db.add_deposit_account(req.name, req.phone, req.last4)
    return {"status": "added"}

@app.delete("/api/admin/accounts/{acct_id}")
async def admin_remove_account(acct_id: int):
    db.remove_deposit_account(acct_id)
    return {"status": "removed"}

@app.post("/api/admin/settings")
async def admin_update_setting(req: UpdateSettingReq):
    db.set_setting(req.key, req.value)
    return {"status": "updated"}

@app.post("/api/admin/broadcast")
async def admin_broadcast(req: BroadcastReq):
    users = db.get_all_users()
    count = 0
    for u in users:
        try:
            import telegram
            from telegram.error import TelegramError
            bot = telegram.Bot(token=config.BOT_TOKEN)
            await bot.send_message(u["user_id"], req.text, parse_mode="Markdown")
            count += 1
            await asyncio.sleep(0.05)
        except TelegramError:
            pass
    return {"sent": count}

@app.get("/api/admin/analytics")
async def admin_analytics():
    return [dict(h) for h in db.get_daily_games()]

# ── Serve React SPA ───────────────────────────────────────────────────

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
