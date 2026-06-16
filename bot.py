import asyncio
import logging
import random
import re
import time
from typing import Optional

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    Message, WebAppInfo
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ConversationHandler, ContextTypes
)
from telegram.error import TelegramError

import config
import database as db
from locales import get_text
from sms_parser import parse_telebirr_sms, verify_recipient
import bingo

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

(PHONE, MAIN_MENU, DEPOSIT_AMOUNT, DEPOSIT_SMS, WITHDRAW_AMOUNT,
 TRANSFER_USER, TRANSFER_AMOUNT, TRANSFER_CONFIRM, ADMIN_ACTION,
 ADD_ACCOUNT, BROADCAST_MSG, SETTINGS_VALUE) = range(12)

active_rooms = {}
user_states = {}
game_locks = {fee: asyncio.Lock() for fee in config.ROOMS}
_bot_app = None


def get_user_lang(user_id: int) -> str:
    uid = user_states.get(user_id)
    if uid and "lang" in uid:
        return uid["lang"]
    u = db.get_user(user_id)
    return u["lang"] if u else "en"


def _(key: str, user_id: int, **kwargs) -> str:
    return get_text(key, get_user_lang(user_id), **kwargs)


def mask_username(name: str) -> str:
    return name if len(name) <= 3 else name[:2] + "***"


def format_amount(amount: float) -> str:
    return f"{amount:,.2f}"


async def safe_edit(msg: Message, **kwargs):
    try:
        await msg.edit_text(**kwargs)
    except TelegramError as e:
        if "not modified" not in str(e).lower() and "can't be edited" not in str(e).lower():
            logger.warning(f"Edit error: {e}")


async def safe_delete(msg: Message):
    try:
        await msg.delete()
    except TelegramError:
        pass


async def send_or_edit(query, context, uid, text, kb=None, parse_mode="Markdown"):
    if kb is None:
        markup = None
    elif isinstance(kb, InlineKeyboardMarkup):
        markup = kb
    else:
        markup = InlineKeyboardMarkup(kb)
    try:
        await safe_edit(query.message, text=text, reply_markup=markup, parse_mode=parse_mode)
    except TelegramError:
        await context.bot.send_message(uid, text, reply_markup=markup, parse_mode=parse_mode)


# ── /start + PHONE COLLECTION ──────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.create_user(user.id)
    args = context.args
    if args:
        ref_match = re.match(r"ref_(\d+)", args[0])
        if ref_match:
            referrer_id = int(ref_match.group(1))
            if referrer_id != user.id:
                u = db.get_user(user.id)
                if u and not u["referred_by"]:
                    db.get_conn().execute(
                        "UPDATE users SET referred_by=? WHERE user_id=?",
                        (referrer_id, user.id),
                    )
                    db.get_conn().commit()
                    db.add_referral_bonus(referrer_id, config.REFERRAL_BONUS)
    u = db.get_user(user.id)
    if u and u["phone"]:
        await show_main_menu(update, context)
        return ConversationHandler.END
    text = _("start_share_phone", user.id)
    btn = KeyboardButton(_("share_phone_btn", user.id), request_contact=True)
    markup = ReplyKeyboardMarkup([[btn]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    return PHONE


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    user = update.effective_user
    if contact and contact.user_id == user.id:
        db.set_user_phone(user.id, contact.phone_number)
        db.create_user(user.id)
        await update.message.reply_text(_("phone_saved", user.id), reply_markup=ReplyKeyboardRemove())
        await show_main_menu(update, context)
        return ConversationHandler.END
    await update.message.reply_text(_("phone_error", user.id))
    return PHONE


# ── MAIN MENU ──────────────────────────────────────────────────────────

MAIN_BUTTONS = [
    [("play_games", "play_games"), ("deposit", "deposit")],
    [("withdraw", "withdraw"), ("transfer", "transfer")],
    [("balance", "balance"), ("profile", "profile")],
    [("transactions", "transactions"), ("refer_earn", "refer_earn")],
    [("join_group", "join_group"), ("contact_us", "contact_us")],
    [("lang_toggle_btn", "toggle_lang")],
]


def main_menu_kb(uid):
    kb = [
        [InlineKeyboardButton(_(key, uid), callback_data=val) for key, val in row]
        for row in MAIN_BUTTONS
    ]
    kb.append([InlineKeyboardButton("🎱 Open App", web_app=WebAppInfo(url=config.WEB_APP_URL))])
    return InlineKeyboardMarkup(kb)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.create_user(uid)
    text = _("main_menu", uid)
    markup = main_menu_kb(uid)
    if update.callback_query:
        await send_or_edit(update.callback_query, context, uid, text, markup)
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")


async def handle_main_menu(query, context, uid):
    action = query.data
    if action == "play_games":
        await show_games_menu(query, context, uid)
    elif action == "deposit":
        await show_deposit_amount(query, context, uid)
    elif action == "withdraw":
        await show_withdraw(query, context, uid)
    elif action == "transfer":
        await show_transfer_start(query, context, uid)
    elif action == "balance":
        await show_balance(query, context, uid)
    elif action == "profile":
        await show_profile(query, context, uid)
    elif action == "transactions":
        await show_transactions(query, context, uid)
    elif action == "join_group":
        await show_join_group(query, context, uid)
    elif action == "contact_us":
        await show_contact(query, context, uid)
    elif action == "refer_earn":
        await show_refer(query, context, uid)
    elif action == "toggle_lang":
        await toggle_language(query, context, uid)
    elif action == "back_main":
        await show_main_menu_from_query(query, context, uid)


async def show_main_menu_from_query(query, context, uid):
    text = _("main_menu", uid)
    markup = main_menu_kb(uid)
    await send_or_edit(query, context, uid, text, markup)


# ── GAMES MENU ─────────────────────────────────────────────────────────

async def show_games_menu(query, context, uid):
    text = _("games_menu", uid)
    bingo_players = sum(db.get_room_player_count(fee) for fee in config.ROOMS)
    kb = [
        [InlineKeyboardButton(f"🎱 {_('bingo', uid)} ({bingo_players})", callback_data="bingo_rooms")],
        [InlineKeyboardButton(f"🎲 {_('coming_soon', uid)}", callback_data="soon_0")],
        [InlineKeyboardButton(f"🎯 {_('coming_soon', uid)}", callback_data="soon_1")],
        [InlineKeyboardButton(f"🃏 {_('coming_soon', uid)}", callback_data="soon_2")],
        [InlineKeyboardButton(_("back_btn", uid), callback_data="back_main")],
    ]
    markup = InlineKeyboardMarkup(kb)
    await send_or_edit(query, context, uid, text, markup)


async def handle_games_menu(query, context, uid):
    action = query.data
    if action == "bingo_rooms":
        await show_room_selection(query, context, uid)
    elif action.startswith("soon_"):
        await query.answer(_("coming_soon", uid), show_alert=True)
    elif action == "back_main":
        await show_main_menu_from_query(query, context, uid)


# ── ROOM SELECTION ─────────────────────────────────────────────────────

async def show_room_selection(query, context, uid):
    text = _("room_select", uid)
    kb = []
    for fee, info in config.ROOMS.items():
        pool = db.get_room_card_count(fee) * fee
        players = db.get_room_player_count(fee)
        label = _("room_card_title", uid, fee=fee, pool=pool, players=players)
        kb.append([InlineKeyboardButton(label, callback_data=f"room_{fee}")])
    kb.append([InlineKeyboardButton(_("back_btn", uid), callback_data="play_games")])
    markup = InlineKeyboardMarkup(kb)
    await send_or_edit(query, context, uid, text, markup)


async def handle_room_selection(query, context, uid):
    fee = int(query.data.split("_")[1])
    await show_card_selection(query, context, uid, fee)


# ── CARD SELECTION ─────────────────────────────────────────────────────

async def show_card_selection(query, context, uid, fee: int):
    async with game_locks[fee]:
        game = db.get_active_game_for_room(fee)
        if not game:
            gid = db.create_game(fee)
            game = db.get_game(gid)
        gid = game["id"]
        taken = set(c["card_index"] for c in db.get_all_game_cards(gid))
        user_cards = set(c["card_index"] for c in db.get_all_game_cards(gid) if c["user_id"] == uid)

        user_states.setdefault(uid, {})
        user_states[uid]["room_fee"] = fee
        user_states[uid]["game_id"] = gid
        user_states[uid]["selected_cards"] = user_cards.copy()

    await refresh_card_grid(query, context, uid, fee)


async def refresh_card_grid(query, context, uid, fee):
    async with game_locks[fee]:
        game = db.get_active_game_for_room(fee)
        if not game:
            return
        gid = game["id"]
        taken = set(c["card_index"] for c in db.get_all_game_cards(gid))
        user_cards = user_states.get(uid, {}).get("selected_cards", set())

        grid_lines = []
        for r in range(10):
            cells = []
            for c in range(20):
                idx = r * 20 + c
                if idx in user_cards:
                    cells.append("🟢")
                elif idx in taken:
                    cells.append("⬛")
                else:
                    cells.append("⬜")
            grid_lines.append("".join(cells))
        grid_text = "\n".join(grid_lines)

        pool = db.get_room_card_count(fee) * fee
        timer = get_room_timer_text(fee)
        last_buyer = get_last_buyer(gid)
        user_data = db.get_user(uid)
        balance = user_data["balance"] if user_data else 0
        card_count = len(user_cards)

        text = _("card_selection", uid, fee=fee, pool_info=f"🏆 {pool} ETB",
                 timer=timer, last_buyer=last_buyer)
        balance_line = f"💳 Balance: {format_amount(balance)} ETB | Cards: {card_count}/5"

        kb = [
            [
                InlineKeyboardButton(f"🎲 +1", callback_data=f"rand_{fee}_1"),
                InlineKeyboardButton(f"🎲 +2", callback_data=f"rand_{fee}_2"),
            ],
            [InlineKeyboardButton(
                _("start_btn", uid, count=card_count, fee=fee, total=card_count * fee),
                callback_data=f"confirm_{fee}",
            )],
            [InlineKeyboardButton(_("back_btn", uid), callback_data="bingo_rooms")],
        ]
        markup = InlineKeyboardMarkup(kb)

    full = f"{text}\n\n{grid_text}\n\n{balance_line}"
    await send_or_edit(query, context, uid, full, kb)


def get_room_timer_text(fee: int) -> str:
    room = active_rooms.get(fee)
    return str(room["countdown"]) if room and "countdown" in room else "60"


def get_last_buyer(gid: int) -> str:
    players = db.get_game_players(gid)
    if not players:
        return "None"
    last = players[-1]
    u = db.get_user(last["user_id"])
    return f"@{mask_username(u.get('phone', 'User'))}" if u else "Unknown"


async def handle_card_selection(query, context, uid):
    data = query.data
    fee = int(data.split("_")[1])
    async with game_locks[fee]:
        game = db.get_active_game_for_room(fee)
        if not game:
            await query.answer(_("error_generic", uid), show_alert=True)
            return
        gid = game["id"]
        taken = set(c["card_index"] for c in db.get_all_game_cards(gid))
        user_cards = user_states.get(uid, {}).get("selected_cards", set())

        if data.startswith("rand_"):
            count = int(data.split("_")[2])
            available = [i for i in range(config.CARDS_PER_ROOM) if i not in taken and i not in user_cards]
            if not available:
                await query.answer(_("room_full", uid), show_alert=True)
                return
            to_pick = random.sample(available, min(count, len(available)))
            for idx in to_pick:
                if len(user_cards) < config.MAX_CARDS_PER_PLAYER:
                    user_cards.add(idx)
            user_states[uid]["selected_cards"] = user_cards
            await query.answer(f"Selected {len(to_pick)} card(s)")
            await refresh_card_grid(query, context, uid, fee)
            return

        if data.startswith("confirm_"):
            if not user_cards:
                await query.answer("Select at least 1 card!", show_alert=True)
                return
            user_data = db.get_user(uid)
            total_cost = len(user_cards) * fee
            if user_data["balance"] < total_cost:
                await query.answer(
                    _("not_enough_balance", uid, needed=total_cost, balance=user_data["balance"]),
                    show_alert=True,
                )
                return
            db.atomic_balance_update(uid, -total_cost, "game_buy", ref=f"game_{gid}")
            existing = db.get_game_player(gid, uid)
            if not existing:
                db.add_game_player(gid, uid, len(user_cards))
            new_cards = bingo.generate_cards(len(user_cards))
            for i, idx in enumerate(sorted(user_cards)):
                db.add_game_card(gid, uid, idx, new_cards[i])
            db.update_game_prize_pool(gid)
            pool = db.get_game(gid)["prize_pool"]
            if fee not in active_rooms:
                active_rooms[fee] = {"game_id": gid, "countdown": config.COUNTDOWN_SECONDS,
                                     "last_buyer": uid, "timer_task": None, "game_task": None}
                asyncio.create_task(game_countdown(fee, context.application.bot))
            else:
                active_rooms[fee]["countdown"] = config.COUNTDOWN_SECONDS
            active_rooms[fee]["last_buyer"] = uid
            await query.answer()
            await context.bot.send_message(
                uid, _("cards_purchased", uid, count=len(user_cards), fee=fee),
                parse_mode="Markdown",
            )
            user_states[uid]["in_game"] = True
            user_states[uid]["selected_cards"] = set()
            await context.bot.send_message(
                uid,
                _("game_waiting", uid, sold=db.get_room_card_count(fee),
                  max=config.CARDS_PER_ROOM, timer=get_room_timer_text(fee),
                  pool=format_amount(pool)),
                parse_mode="Markdown",
            )
            return


# ── GAME COUNTDOWN ─────────────────────────────────────────────────────

async def game_countdown(fee: int, bot):
    await asyncio.sleep(1)
    while fee in active_rooms:
        room = active_rooms[fee]
        if room["countdown"] <= 0:
            async with game_locks[fee]:
                gid = room["game_id"]
                sold = db.get_room_card_count(fee)
                if sold < 2:
                    await refund_room(fee, gid, bot)
                    room["countdown"] = config.COUNTDOWN_SECONDS
                    continue
                else:
                    await start_game(fee, gid, bot)
            return
        room["countdown"] -= 1
        await asyncio.sleep(1)


async def refund_room(fee: int, gid: int, bot):
    players = db.get_game_players(gid)
    for gp in players:
        cost = gp["card_count"] * fee
        db.atomic_balance_update(gp["user_id"], cost, "refund", ref=f"refund_{gid}")
    db.set_game_status(gid, "refunded")
    for gp in players:
        uid = gp["user_id"]
        try:
            await bot.send_message(uid, _("refund_notice", uid), parse_mode="Markdown")
        except TelegramError:
            pass
    if fee in active_rooms:
        del active_rooms[fee]


# ── GAME LOOP ──────────────────────────────────────────────────────────

async def start_game(fee: int, gid: int, bot):
    db.set_game_status(gid, "playing")
    game = db.get_game(gid)
    players = db.get_game_players(gid)
    for gp in players:
        uid = gp["user_id"]
        try:
            await bot.send_message(
                uid,
                _("game_started", uid, fee=fee, cards=db.get_room_card_count(fee),
                  pool=game["prize_pool"]),
                parse_mode="Markdown",
            )
        except TelegramError:
            pass

    number_pool = bingo.generate_number_pool()
    called_set = set()

    for call_idx, number in enumerate(number_pool):
        if call_idx >= config.MAX_NUMBERS:
            break
        game = db.get_game(gid)
        if game["status"] != "playing":
            break
        db.add_called_number(gid, number)
        called_set.add(number)
        await send_number_call(bot, fee, gid, number, called_set, call_idx + 1)
        winners = await check_for_winners(gid, called_set)
        if winners:
            await handle_game_winners(fee, gid, winners, called_set, bot)
            return
        await asyncio.sleep(int(db.get_setting("call_interval", str(config.CALL_INTERVAL))))

    await handle_no_winner(fee, gid, bot)


async def send_number_call(bot, fee, gid, number, called_set, call_count):
    grid_html = bingo.render_number_grid(called_set)
    progress = f"Call {call_count}/{config.MAX_NUMBERS}"
    players = db.get_game_players(gid)
    for gp in players:
        uid = gp["user_id"]
        try:
            await bot.send_message(uid, f"🎱 *{number}* — {progress}", parse_mode="Markdown")
            audio_path = config.AUDIO_DIR / f"{number}.ogg"
            if audio_path.exists():
                try:
                    with open(audio_path, "rb") as f:
                        await bot.send_voice(uid, f)
                except TelegramError:
                    pass
        except TelegramError:
            pass


async def check_for_winners(gid: int, called_set: set) -> list:
    all_cards = db.get_all_game_cards(gid)
    winners = []
    for card in all_cards:
        nums = [int(x) for x in card["numbers"].split(",")]
        hl, hc = bingo.check_card_wins(nums, called_set)
        if hl or hc:
            gp = db.get_game_player(gid, card["user_id"])
            if gp and gp["auto_win"]:
                winners.append((card["user_id"], card["card_index"], nums))
    return winners


async def handle_game_winners(fee: int, gid: int, winners: list, called_set: set, bot):
    game = db.get_game(gid)
    pool = game["prize_pool"]
    house_cut = pool * float(db.get_setting("house_commission", str(config.HOUSE_COMMISSION)))
    prize_pool = pool - house_cut
    unique_winners = list(set(w[0] for w in winners))
    prize_per_winner = prize_pool / len(unique_winners) if unique_winners else 0
    db.set_game_winners(gid, unique_winners)
    db.set_game_status(gid, "ended")
    for uid in unique_winners:
        db.atomic_balance_update(uid, prize_per_winner, "game_win", ref=f"win_{gid}")
        db.set_game_prize(gid, uid, prize_per_winner)
        db.get_conn().execute("UPDATE users SET total_games_played = total_games_played + 1 WHERE user_id=?", (uid,))
    players = db.get_game_players(gid)
    for gp in players:
        uid = gp["user_id"]
        try:
            if uid in unique_winners:
                winner_card = [w for w in winners if w[0] == uid]
                card_idx = winner_card[0][1] if winner_card else 0
                await bot.send_message(
                    uid, _("you_won", uid, amount=format_amount(prize_per_winner), card_idx=card_idx + 1),
                    parse_mode="Markdown",
                )
            else:
                wnames = []
                for wuid in unique_winners:
                    u = db.get_user(wuid)
                    name = mask_username(str(u.get("phone", wuid))) if u else str(wuid)
                    wnames.append(f"@{name}")
                await bot.send_message(
                    uid, _("game_over_win", uid, winners=", ".join(wnames)),
                    parse_mode="Markdown",
                )
            play_kb = InlineKeyboardMarkup([[InlineKeyboardButton(_("play_again", uid), callback_data="bingo_rooms")]])
            await bot.send_message(uid, _("play_again", uid), reply_markup=play_kb)
        except TelegramError:
            pass
    if fee in active_rooms:
        del active_rooms[fee]


async def handle_no_winner(fee: int, gid: int, bot):
    db.set_game_status(gid, "refunded")
    players = db.get_game_players(gid)
    for gp in players:
        uid = gp["user_id"]
        cost = gp["card_count"] * fee
        db.atomic_balance_update(uid, cost, "refund", ref=f"nobingo_{gid}")
        try:
            await bot.send_message(uid, _("no_winner", uid), parse_mode="Markdown")
            play_kb = InlineKeyboardMarkup([[InlineKeyboardButton(_("play_again", uid), callback_data="bingo_rooms")]])
            await bot.send_message(uid, _("play_again", uid), reply_markup=play_kb)
        except TelegramError:
            pass
    if fee in active_rooms:
        del active_rooms[fee]


# ── DEPOSIT ────────────────────────────────────────────────────────────

async def show_deposit_amount(query, context, uid):
    text = _("deposit_title", uid, min=config.MIN_DEPOSIT)
    amounts = [50, 100, 200, 500, 1000]
    kb = []
    row = []
    for a in amounts:
        row.append(InlineKeyboardButton(f"{a} ETB", callback_data=f"dep_amount_{a}"))
        if len(row) == 3:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton(_("custom_amount", uid), callback_data="dep_custom"),
               InlineKeyboardButton(_("back_btn", uid), callback_data="back_main")])
    markup = InlineKeyboardMarkup(kb)
    await send_or_edit(query, context, uid, text, kb)


async def handle_deposit_amount(query, context, uid):
    data = query.data
    if data.startswith("dep_amount_"):
        amount = float(data.split("_")[2])
        context.user_data["dep_amount"] = amount
        context.user_data["dep_step"] = "awaiting_sms"
        await show_deposit_instructions(query, context, uid, amount)
        return DEPOSIT_SMS
    elif data == "dep_custom":
        context.user_data["dep_step"] = "awaiting_amount"
        text = _("deposit_title", uid, min=config.MIN_DEPOSIT) + "\n\nEnter amount (min 20 ETB):"
        kb = [[InlineKeyboardButton(_("cancel_btn", uid), callback_data="back_main")]]
        await send_or_edit(query, context, uid, text, kb)
        return DEPOSIT_AMOUNT
    return ConversationHandler.END


async def show_deposit_instructions(query, context, uid, amount):
    acct = db.get_current_deposit_account()
    text = _("deposit_instructions", uid, name=acct["name"], phone=acct["phone"], amount=format_amount(amount))
    kb = [[InlineKeyboardButton(_("cancel_btn", uid), callback_data="back_main")]]
    await send_or_edit(query, context, uid, text, kb)


async def handle_deposit_sms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    sms_text = update.message.text.strip()
    expected_amount = context.user_data.get("dep_amount")
    if not expected_amount:
        await update.message.reply_text(_("error_generic", uid))
        return ConversationHandler.END
    parsed = parse_telebirr_sms(sms_text)
    if not parsed:
        await update.message.reply_text(_("invalid_sms", uid))
        return DEPOSIT_SMS
    acct = db.get_current_deposit_account()
    errors, parsed_data = verify_recipient(parsed, acct["name"], acct["last4"], expected_amount=expected_amount)
    if errors:
        for err in errors:
            if err == "amount_mismatch":
                msg = _("amount_mismatch", uid, sent=parsed.get("amount", 0), needed=expected_amount)
            elif err == "recipient_mismatch":
                msg = _("recipient_mismatch", uid)
            else:
                msg = _("deposit_fail", uid, reason=err)
            await update.message.reply_text(msg, parse_mode="Markdown")
        return DEPOSIT_SMS
    ref = parsed_data.get("ref", "")
    if db.is_ref_used(ref):
        await update.message.reply_text(_("ref_used", uid))
        return DEPOSIT_SMS
    db.mark_ref_used(ref)
    amount = parsed.get("amount", expected_amount)
    try:
        new_balance = db.atomic_balance_update(uid, amount, "deposit", ref=ref)
    except ValueError:
        await update.message.reply_text(_("error_generic", uid))
        return ConversationHandler.END
    usage = int(db.get_setting("deposit_usage_count", "0"))
    db.set_setting("deposit_usage_count", str(usage + 1))
    if (usage + 1) % config.DEPOSIT_ACCOUNT_ROTATION_INTERVAL == 0:
        db.rotate_deposit_account()
    await update.message.reply_text(
        _("deposit_success", uid, amount=format_amount(amount), ref=ref, balance=format_amount(new_balance)),
        parse_mode="Markdown",
    )
    await show_main_menu(update, context)
    return ConversationHandler.END


async def handle_deposit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if context.user_data.get("dep_step") == "awaiting_amount":
        try:
            amount = float(update.message.text.strip())
            if amount < config.MIN_DEPOSIT:
                await update.message.reply_text(_("deposit_title", uid, min=config.MIN_DEPOSIT) + "\n\nAmount too low. Min is {} ETB.".format(config.MIN_DEPOSIT))
                return DEPOSIT_AMOUNT
            context.user_data["dep_amount"] = amount
            context.user_data["dep_step"] = "awaiting_sms"
            acct = db.get_current_deposit_account()
            text = _("deposit_instructions", uid, name=acct["name"], phone=acct["phone"], amount=format_amount(amount))
            kb = [[InlineKeyboardButton(_("cancel_btn", uid), callback_data="back_main")]]
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
            return DEPOSIT_SMS
        except ValueError:
            await update.message.reply_text(_("error_invalid_input", uid))
            return DEPOSIT_AMOUNT
    return ConversationHandler.END


# ── WITHDRAW ───────────────────────────────────────────────────────────

async def show_withdraw(query, context, uid):
    user = db.get_user(uid)
    if not user or not user["phone"]:
        await query.answer(_("withdraw_no_phone", uid), show_alert=True)
        await show_main_menu_from_query(query, context, uid)
        return ConversationHandler.END
    text = _("withdraw_title", uid, balance=format_amount(user["balance"]),
             phone=user["phone"], min=config.MIN_WITHDRAWAL)
    await send_or_edit(query, context, uid, text)
    return WITHDRAW_AMOUNT


async def handle_withdraw_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    try:
        amount = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(_("error_invalid_input", uid))
        return WITHDRAW_AMOUNT
    if amount < config.MIN_WITHDRAWAL:
        await update.message.reply_text(_("withdraw_min", uid, min=config.MIN_WITHDRAWAL))
        return WITHDRAW_AMOUNT
    user = db.get_user(uid)
    if user["balance"] < amount:
        await update.message.reply_text(_("error_generic", uid))
        return WITHDRAW_AMOUNT
    db.atomic_balance_update(uid, -amount, "withdrawal", ref=f"wd_{uid}_{int(time.time())}")
    db.create_withdrawal(uid, amount, user["phone"])
    await update.message.reply_text(_("withdraw_success", uid, amount=format_amount(amount)), parse_mode="Markdown")
    for admin_id in config.ADMIN_IDS:
        try:
            wd = db.get_conn().execute(
                "SELECT id FROM withdrawals WHERE user_id=? ORDER BY id DESC LIMIT 1", (uid,)
            ).fetchone()
            wd_id = wd["id"]
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Approve", callback_data=f"wd_approve_{wd_id}"),
                 InlineKeyboardButton("❌ Reject", callback_data=f"wd_reject_{wd_id}")]
            ])
            await context.bot.send_message(
                admin_id,
                f"💸 *New Withdrawal Request*\nUser: `{uid}`\nPhone: {user['phone']}\nAmount: {format_amount(amount)} ETB",
                reply_markup=kb, parse_mode="Markdown",
            )
        except TelegramError:
            pass
    await show_main_menu(update, context)
    return ConversationHandler.END


# ── TRANSFER ───────────────────────────────────────────────────────────

async def show_transfer_start(query, context, uid):
    user = db.get_user(uid)
    text = _("transfer_title", uid, balance=format_amount(user["balance"]), min=config.MIN_TRANSFER)
    kb = [[InlineKeyboardButton(_("cancel_btn", uid), callback_data="back_main")]]
    await send_or_edit(query, context, uid, text, kb)
    return TRANSFER_USER


async def handle_transfer_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    try:
        target_uid = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(_("error_invalid_input", uid))
        return TRANSFER_USER
    if target_uid == uid:
        await update.message.reply_text(_("transfer_self", uid))
        return TRANSFER_USER
    target = db.get_user(target_uid)
    if not target:
        await update.message.reply_text(_("error_invalid_input", uid))
        return TRANSFER_USER
    context.user_data["transfer_target"] = target_uid
    await update.message.reply_text(_("transfer_amount", uid))
    return TRANSFER_AMOUNT


async def handle_transfer_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    try:
        amount = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(_("error_invalid_input", uid))
        return TRANSFER_AMOUNT
    if amount < config.MIN_TRANSFER:
        await update.message.reply_text(f"Min transfer is {config.MIN_TRANSFER} ETB")
        return TRANSFER_AMOUNT
    user = db.get_user(uid)
    if user["balance"] < amount:
        await update.message.reply_text(_("error_generic", uid))
        return TRANSFER_AMOUNT
    if time.time() - (user.get("last_transfer_time") or 0) < config.TRANSFER_COOLDOWN:
        await update.message.reply_text(_("transfer_cooldown", uid))
        return TRANSFER_AMOUNT
    context.user_data["transfer_amount"] = amount
    target_uid = context.user_data["transfer_target"]
    text = _("transfer_confirm", uid, amount=format_amount(amount), uid=target_uid)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(_("confirm_btn", uid), callback_data="xfer_yes"),
         InlineKeyboardButton(_("cancel_btn", uid), callback_data="xfer_no")]
    ])
    await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    return TRANSFER_CONFIRM


async def handle_transfer_confirm(query, context, uid):
    await query.answer()
    if query.data == "xfer_yes":
        target_uid = context.user_data["transfer_target"]
        amount = context.user_data["transfer_amount"]
        try:
            with db.tx() as conn:
                sender = conn.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
                if sender["balance"] < amount:
                    raise ValueError("Insufficient")
                conn.execute("UPDATE users SET balance=balance-?, last_transfer_time=? WHERE user_id=?", (amount, time.time(), uid))
                conn.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, target_uid))
                conn.execute("INSERT INTO transactions(user_id, type, amount, balance_before, balance_after, ref) VALUES (?,?,?,?,?,?)",
                             (uid, "transfer_out", -amount, sender["balance"], sender["balance"] - amount,
                              f"xfer_{uid}_{target_uid}_{int(time.time())}"))
                recv = conn.execute("SELECT balance FROM users WHERE user_id=?", (target_uid,)).fetchone()
                conn.execute("INSERT INTO transactions(user_id, type, amount, balance_before, balance_after, ref) VALUES (?,?,?,?,?,?)",
                             (target_uid, "transfer_in", amount, recv["balance"], recv["balance"] + amount,
                              f"xfer_in_{uid}_{target_uid}_{int(time.time())}"))
            new_bal = db.get_user(uid)["balance"]
            await safe_edit(query.message, text=_("transfer_done", uid, amount=format_amount(amount), uid=target_uid, balance=format_amount(new_bal)), parse_mode="Markdown")
        except (ValueError, Exception) as e:
            await safe_edit(query.message, text=_("error_generic", uid))
    else:
        await safe_edit(query.message, text=_("cancel_btn", uid))
    await show_main_menu_from_query(query, context, uid)
    return ConversationHandler.END


# ── BALANCE, PROFILE, TRANSACTIONS, ETC ────────────────────────────────

async def show_balance(query, context, uid):
    user = db.get_user(uid)
    if not user:
        await query.answer(_("error_generic", uid))
        return
    text = _("balance_msg", uid, balance=format_amount(user["balance"]),
             deposited=format_amount(user["total_deposited"]), withdrawn=format_amount(user["total_withdrawn"]))
    kb = [[InlineKeyboardButton(_("back_btn", uid), callback_data="back_main")]]
    await send_or_edit(query, context, uid, text, kb)


async def show_profile(query, context, uid):
    user = db.get_user(uid)
    if not user:
        await query.answer(_("error_generic", uid))
        return
    lang_name = "English" if user["lang"] == "en" else "አማርኛ"
    text = _("profile_msg", uid, user_id=uid, phone=user.get("phone", "N/A"),
             balance=format_amount(user["balance"]), played=user["total_games_played"],
             won=user["total_games_won"], ref_code=user["referral_code"],
             ref_count=user["referral_count"], lang=lang_name)
    kb = [[InlineKeyboardButton(_("back_btn", uid), callback_data="back_main")]]
    await send_or_edit(query, context, uid, text, kb)


async def show_transactions(query, context, uid):
    txns = db.get_transactions(uid)
    if not txns:
        text = _("transactions_title", uid, entries=_("trans_empty", uid))
    else:
        entries = []
        for t in txns:
            entries.append(_("trans_entry", uid, type=t["type"], amount=format_amount(abs(t["amount"])),
                             status=t["status"], date=t["created_at"][:19]))
        text = _("transactions_title", uid, entries="\n\n".join(entries))
    kb = [[InlineKeyboardButton(_("back_btn", uid), callback_data="back_main")]]
    await send_or_edit(query, context, uid, text, kb)


async def show_join_group(query, context, uid):
    text = _("join_group_msg", uid)
    kb = [[InlineKeyboardButton(_("back_btn", uid), callback_data="back_main")]]
    await send_or_edit(query, context, uid, text, kb)


async def show_contact(query, context, uid):
    text = _("contact_msg", uid)
    kb = [[InlineKeyboardButton(_("back_btn", uid), callback_data="back_main")]]
    await send_or_edit(query, context, uid, text, kb)


async def show_refer(query, context, uid):
    user = db.get_user(uid)
    text = _("refer_title", uid, bonus=config.REFERRAL_BONUS, code=user["referral_code"], count=user["referral_count"])
    kb = [[InlineKeyboardButton(_("back_btn", uid), callback_data="back_main")]]
    await send_or_edit(query, context, uid, text, kb)


# ── LANGUAGE TOGGLE ────────────────────────────────────────────────────

async def toggle_language(query, context, uid):
    user = db.get_user(uid)
    new_lang = "am" if user["lang"] == "en" else "en"
    db.set_user_lang(uid, new_lang)
    user_states.setdefault(uid, {})["lang"] = new_lang
    await query.answer()
    await show_main_menu_from_query(query, context, uid)


# ── ADMIN PANEL ────────────────────────────────────────────────────────

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in config.ADMIN_IDS:
        await update.message.reply_text("Unauthorized.")
        return
    text = _("admin_menu", uid)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Dashboard", callback_data="admin_dash"),
         InlineKeyboardButton("💸 Withdrawals", callback_data="admin_wd")],
        [InlineKeyboardButton("🏦 Accounts", callback_data="admin_accts"),
         InlineKeyboardButton("📢 Broadcast", callback_data="admin_bc")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="admin_set"),
         InlineKeyboardButton("📊 Analytics", callback_data="admin_analytics")],
        [InlineKeyboardButton(_("back_btn", uid), callback_data="back_main")],
    ])
    await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def handle_admin(query, context, uid):
    action = query.data
    if action == "admin_dash":
        await show_admin_dashboard(query, context, uid)
    elif action == "admin_wd":
        await show_admin_withdrawals(query, context, uid)
    elif action == "admin_accts":
        await show_admin_accounts(query, context, uid)
    elif action == "admin_bc":
        await show_admin_broadcast(query, context, uid)
    elif action == "admin_set":
        await show_admin_settings(query, context, uid)
    elif action == "admin_analytics":
        await show_admin_analytics(query, context, uid)
    elif action.startswith("wd_approve_"):
        await handle_admin_wd_approve(query, context, uid)
    elif action.startswith("wd_reject_"):
        await handle_admin_wd_reject(query, context, uid)
    elif action == "admin_add_acct":
        await show_admin_add_account(query, context, uid)
    elif action.startswith("admin_rm_acct_"):
        await handle_admin_remove_account(query, context, uid)
    elif action in ("admin_set_comm", "admin_set_interval"):
        context.user_data["admin_setting"] = action
        await send_or_edit(query, context, uid, "Enter new value:")
        return SETTINGS_VALUE


async def show_admin_dashboard(query, context, uid):
    stats = db.get_game_stats()
    text = _("admin_dashboard", uid, total_games=stats["total_games"],
             total_collected=format_amount(stats["total_collected"]),
             total_profit=format_amount(stats["total_profit"]),
             total_players=stats["total_players"])
    kb = [[InlineKeyboardButton(_("back_btn", uid), callback_data="admin_menu")]]
    await send_or_edit(query, context, uid, text, kb)


async def show_admin_withdrawals(query, context, uid):
    pending = db.get_pending_withdrawals()
    if not pending:
        text = _("no_pending", uid)
    else:
        entries = []
        for w in pending:
            entries.append(_("withdrawal_entry", uid, id=w["id"], uid=w["user_id"],
                             phone=w["phone"], amount=format_amount(w["amount"]), date=w["created_at"][:19]))
        text = _("withdrawal_pending", uid, list="\n\n".join(entries))
    kb = [[InlineKeyboardButton(_("back_btn", uid), callback_data="admin_menu")]]
    await send_or_edit(query, context, uid, text, kb)


async def handle_admin_wd_approve(query, context, uid):
    wid = int(query.data.split("_")[2])
    if db.approve_withdrawal(wid, uid):
        await query.answer("Approved!")
        await safe_edit(query.message, text=_("withdrawal_approved", uid, id=wid), parse_mode="Markdown")
    else:
        await query.answer("Failed")


async def handle_admin_wd_reject(query, context, uid):
    wid = int(query.data.split("_")[2])
    if db.reject_withdrawal(wid, uid):
        await query.answer("Rejected & Refunded!")
        await safe_edit(query.message, text=_("withdrawal_rejected", uid, id=wid), parse_mode="Markdown")
    else:
        await query.answer("Failed")


async def show_admin_accounts(query, context, uid):
    accounts = db.get_deposit_accounts()
    lines = [f"#{a['id']} {a['name']} - {a['phone']} ({a['last4']})" for a in accounts]
    text = _("deposit_accounts_list", uid, list="\n".join(lines) if lines else "No accounts")
    kb = [[InlineKeyboardButton("➕ Add", callback_data="admin_add_acct")]]
    for a in accounts:
        kb.append([InlineKeyboardButton(f"❌ Remove #{a['id']} {a['name']}", callback_data=f"admin_rm_acct_{a['id']}")])
    kb.append([InlineKeyboardButton(_("back_btn", uid), callback_data="admin_menu")])
    await send_or_edit(query, context, uid, text, kb)


async def show_admin_add_account(query, context, uid):
    await send_or_edit(query, context, uid, _("add_account_instruction", uid))
    return ADD_ACCOUNT


async def handle_add_account_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in config.ADMIN_IDS:
        return ConversationHandler.END
    parts = [p.strip() for p in update.message.text.split(",")]
    if len(parts) >= 3:
        db.add_deposit_account(parts[0], parts[1], parts[2])
        await update.message.reply_text(_("account_added", uid))
    else:
        await update.message.reply_text(_("error_invalid_input", uid))
    await show_main_menu(update, context)
    return ConversationHandler.END


async def handle_admin_remove_account(query, context, uid):
    acct_id = int(query.data.split("_")[3])
    db.remove_deposit_account(acct_id)
    await query.answer(_("account_removed", uid))
    await show_admin_accounts(query, context, uid)


async def show_admin_broadcast(query, context, uid):
    text = _("broadcast_instruction", uid)
    kb = [[InlineKeyboardButton(_("cancel_btn", uid), callback_data="admin_menu")]]
    await send_or_edit(query, context, uid, text, kb)
    return BROADCAST_MSG


async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in config.ADMIN_IDS:
        return ConversationHandler.END
    users = db.get_all_users()
    count = 0
    for u in users:
        try:
            if update.message.text:
                await context.bot.send_message(u["user_id"], update.message.text, parse_mode="Markdown")
            elif update.message.photo:
                await context.bot.send_photo(u["user_id"], update.message.photo[-1].file_id, caption=update.message.caption)
            count += 1
            await asyncio.sleep(0.05)
        except TelegramError:
            pass
    await update.message.reply_text(_("broadcast_sent", uid, count=count), parse_mode="Markdown")
    return ConversationHandler.END


async def show_admin_settings(query, context, uid):
    commission = float(db.get_setting("house_commission", "0.20")) * 100
    interval = db.get_setting("call_interval", "2")
    text = _("settings_title", uid, commission=int(commission), interval=interval)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Commission ({int(commission)}%)", callback_data="admin_set_comm"),
         InlineKeyboardButton(f"Interval ({interval}s)", callback_data="admin_set_interval")],
        [InlineKeyboardButton(_("back_btn", uid), callback_data="admin_menu")],
    ])
    await send_or_edit(query, context, uid, text, kb)


async def handle_settings_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in config.ADMIN_IDS:
        return ConversationHandler.END
    setting = context.user_data.get("admin_setting")
    value = update.message.text.strip()
    if setting == "admin_set_comm":
        try:
            v = float(value) / 100
            if 0 <= v <= 1:
                db.set_setting("house_commission", str(v))
                await update.message.reply_text(f"Commission set to {float(value)}%")
        except ValueError:
            await update.message.reply_text("Invalid")
    elif setting == "admin_set_interval":
        try:
            v = int(value)
            if v >= 1:
                db.set_setting("call_interval", str(v))
                await update.message.reply_text(f"Call interval set to {v}s")
        except ValueError:
            await update.message.reply_text("Invalid")
    await show_main_menu(update, context)
    return ConversationHandler.END


async def show_admin_analytics(query, context, uid):
    hours_data = db.get_daily_games()
    hours_text = "\n".join(f"  {h['hour']}:00 - {h['cnt']} games" for h in hours_data) if hours_data else "No data"
    text = _("analytics_title", uid, hours=hours_text)
    kb = [[InlineKeyboardButton(_("back_btn", uid), callback_data="admin_menu")]]
    await send_or_edit(query, context, uid, text, kb)


# ── BINGO PLAYER ACTIONS DURING GAME ───────────────────────────────────

async def handle_bingo_action(query, context, uid):
    data = query.data
    if data == "check_all":
        await handle_check_all(query, context, uid)
    elif data == "bingo_claim":
        await handle_bingo_claim(query, context, uid)
    elif data == "toggle_auto":
        await handle_toggle_auto(query, context, uid)


async def handle_check_all(query, context, uid):
    gid = user_states.get(uid, {}).get("game_id")
    if not gid:
        await query.answer(_("error_generic", uid))
        return
    cards = db.get_user_cards_in_game(gid, uid)
    called = set(db.get_called_numbers(gid))
    for card in cards:
        nums = [int(x) for x in card["numbers"].split(",")]
        marked = set(int(x) for x in card["marked"].split(",") if card["marked"])
        new_marked = marked | (called & set(nums))
        db.update_card_marked(gid, uid, card["card_index"], list(new_marked))
    await query.answer("Cards checked! ✅")


async def handle_bingo_claim(query, context, uid):
    gid = user_states.get(uid, {}).get("game_id")
    if not gid:
        await query.answer(_("error_generic", uid))
        return
    game = db.get_game(gid)
    if not game or game["status"] != "playing":
        await query.answer("Game is not active!")
        return
    called = set(db.get_called_numbers(gid))
    cards = db.get_user_cards_in_game(gid, uid)
    for card in cards:
        nums = [int(x) for x in card["numbers"].split(",")]
        hl, hc = bingo.check_card_wins(nums, called)
        if hl or hc:
            await query.answer("BINGO! 🎉")
            await handle_game_winners(
                user_states[uid]["room_fee"], gid,
                [(uid, card["card_index"], nums)], called,
                context.application.bot,
            )
            return
    await query.answer("No winning pattern found. Keep playing!")


async def handle_toggle_auto(query, context, uid):
    gid = user_states.get(uid, {}).get("game_id")
    if not gid:
        return
    gp = db.get_game_player(gid, uid)
    if gp:
        new_val = 0 if gp["auto_win"] else 1
        db.get_conn().execute("UPDATE game_players SET auto_win=? WHERE game_id=? AND user_id=?", (new_val, gid, uid))
        status = _("auto_on", uid) if new_val else _("auto_off", uid)
        await query.answer(f"Auto Win: {status}")


# ── CALLBACK ROUTER ────────────────────────────────────────────────────

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data
    if data == "back_main":
        await show_main_menu_from_query(query, context, uid)
    elif data.startswith("admin_"):
        await handle_admin(query, context, uid)
    elif data in ("check_all", "bingo_claim", "toggle_auto"):
        await handle_bingo_action(query, context, uid)
    elif data.startswith("wd_approve_") or data.startswith("wd_reject_"):
        await handle_admin(query, context, uid)
    elif data.startswith("dep_amount_") or data == "dep_custom":
        await handle_deposit_amount(query, context, uid)
    elif data in ("xfer_yes", "xfer_no"):
        await handle_transfer_confirm(query, context, uid)
    elif data in ("play_games", "deposit", "withdraw", "transfer", "balance",
                  "profile", "transactions", "join_group", "contact_us",
                  "refer_earn", "toggle_lang"):
        await handle_main_menu(query, context, uid)
    elif data.startswith("room_"):
        await handle_room_selection(query, context, uid)
    elif data == "bingo_rooms" or data.startswith("soon_"):
        await handle_games_menu(query, context, uid)
    elif data.startswith("rand_") or data.startswith("confirm_"):
        await handle_card_selection(query, context, uid)


async def handle_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if context.user_data.get("dep_step") == "awaiting_sms":
        await handle_deposit_sms(update, context)
        return
    await show_main_menu(update, context)


# ── POST INIT ──────────────────────────────────────────────────────────

async def post_init(application: Application):
    global _bot_app
    _bot_app = application
    db.init_db()
    logger.info("Database initialized")
    for fee in config.ROOMS:
        game = db.get_active_game_for_room(fee)
        if game:
            db.set_game_status(game["id"], "refunded")
            logger.info(f"Reset stuck game {game['id']} in room {fee}")


# ── MAIN ───────────────────────────────────────────────────────────────

def main():
    application = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()

    conv_start = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={PHONE: [MessageHandler(filters.CONTACT, handle_contact)]},
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    conv_deposit = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_deposit_amount, pattern=r"^(dep_amount_|dep_custom)$")],
        states={
            DEPOSIT_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_deposit_text),
                CallbackQueryHandler(handle_deposit_amount, pattern=r"^(dep_amount_|dep_custom)$"),
            ],
            DEPOSIT_SMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_deposit_sms)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    conv_withdraw = ConversationHandler(
        entry_points=[CallbackQueryHandler(show_withdraw, pattern="^withdraw$")],
        states={WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_text)]},
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    conv_transfer = ConversationHandler(
        entry_points=[CallbackQueryHandler(show_transfer_start, pattern="^transfer$")],
        states={
            TRANSFER_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_transfer_user)],
            TRANSFER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_transfer_amount)],
            TRANSFER_CONFIRM: [CallbackQueryHandler(handle_transfer_confirm, pattern=r"^xfer_")],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    conv_broadcast = ConversationHandler(
        entry_points=[CallbackQueryHandler(show_admin_broadcast, pattern="^admin_bc$")],
        states={BROADCAST_MSG: [MessageHandler(filters.TEXT | filters.PHOTO, handle_broadcast)]},
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    conv_add_acct = ConversationHandler(
        entry_points=[CallbackQueryHandler(show_admin_add_account, pattern="^admin_add_acct$")],
        states={ADD_ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_account_text)]},
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    conv_settings = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_admin, pattern=r"^admin_set_")],
        states={SETTINGS_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_settings_value)]},
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    application.add_handler(conv_start)
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(conv_deposit)
    application.add_handler(conv_withdraw)
    application.add_handler(conv_transfer)
    application.add_handler(conv_broadcast)
    application.add_handler(conv_add_acct)
    application.add_handler(conv_settings)
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_fallback))

    logger.info("Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
