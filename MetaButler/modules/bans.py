from MetaButler.modules.language import gs
import html
from typing import Optional

from telegram import Update, ParseMode
from telegram.error import BadRequest
from telegram.ext import Filters, CallbackContext
from telegram.utils.helpers import mention_html

from MetaButler import (
    DEV_USERS,
    SUDO_USERS,
    SUPPORT_USERS,
    OWNER_ID,
    WHITELIST_USERS,
    BAN_STICKER,
    log
)
from MetaButler.modules.helper_funcs.chat_status import (
    bot_admin,
    can_restrict,
    connection_status,
    is_user_admin,
    is_user_ban_protected,
    is_user_in_chat,
    can_delete,
)
from MetaButler.modules.helper_funcs.extraction import extract_user_and_text
from MetaButler.modules.helper_funcs.string_handling import extract_time
from MetaButler.modules.helper_funcs.misc import has_reply_to_message
from MetaButler.modules.log_channel import loggable, gloggable
from MetaButler.modules.helper_funcs.decorators import metacmd

from ..modules.helper_funcs.anonymous import user_admin, AdminPerms


@metacmd(command=['ban', 'dban', 'sban'], pass_args=True)
@connection_status
@bot_admin
@can_restrict
@user_admin(AdminPerms.CAN_RESTRICT_MEMBERS)
@loggable
# sourcery no-metrics
def ban(update: Update, context: CallbackContext) -> Optional[str]:
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    args = context.args
    bot = context.bot
    log_message = ""
    reason = ""
    if has_reply_to_message(message) and message.reply_to_message.sender_chat:
        r = bot.ban_chat_sender_chat(
            chat_id=chat.id, sender_chat_id=message.reply_to_message.sender_chat.id)
        if r:
            message.reply_text("Channel {} was banned successfully from {}".format(
                html.escape(message.reply_to_message.sender_chat.title),
                html.escape(chat.title)
            ),
                parse_mode="html"
            )
            return (
                f"<b>{html.escape(chat.title)}:</b>\n"
                f"#BANNED\n"
                f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
                f"<b>Channel:</b> {html.escape(message.reply_to_message.sender_chat.title)} ({message.reply_to_message.sender_chat.id})"
            )
        else:
            message.reply_text("Failed to ban channel")
        return

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("I doubt that's a user.")
        return log_message

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message != "User not found":
            raise

        message.reply_text("Can't seem to find this person.")
        return log_message
    if user_id == context.bot.id:
        message.reply_text("Oh yeah, ban myself, noob!")
        return log_message

    if is_user_ban_protected(update, user_id, member) and user not in DEV_USERS:
        if user_id == OWNER_ID:
            message.reply_text("I'd never ban my owner.")
        elif user_id in DEV_USERS:
            message.reply_text("I can't act against our own.")
        elif user_id in SUDO_USERS:
            message.reply_text("My sudos are ban immune")
        elif user_id in SUPPORT_USERS:
            message.reply_text("My support users are ban immune")
        elif user_id in WHITELIST_USERS:
            message.reply_text("WhiteListed users are ban immune!")
        else:
            message.reply_text("This user has immunity and cannot be banned.")
        return log_message
    if message.text.startswith("/s") or message.text.startswith("!s"):
        silent = True
        if not can_delete(chat, context.bot.id):
            return ""
    else:
        silent = False
    if message.text.startswith("/d") or message.text.startswith("!d"):
        delban = True
        if not can_delete(chat, context.bot.id):
            return ""
    else:
        delban = False
    log_message = (
        f"<b>{html.escape(chat.title)}:</b>\n"
        f"#BANNED\n"
        f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
        f"<b>User:</b> {mention_html(member.user.id, member.user.first_name)}"
    )
    if reason:
        log_message += "\n<b>Reason:</b> {}".format(reason)

    try:
        if silent:
            if has_reply_to_message(message):
                message.delete()
            return log_message
        else:
            if delban and has_reply_to_message(message):
                message.reply_to_message.delete()
            context.bot.send_sticker(chat.id, BAN_STICKER)
            if reason:
                context.bot.sendMessage(
                    chat.id,
                    "<b>Banned:</b> {} \n<b>Admin:</b> {}\n<b>Chat:</b> <b>{}</b>\n<b>Reason:</b> <code>{}</code>".format(
                        mention_html(member.user.id, member.user.first_name), mention_html(
                            user.id, user.first_name),
                        message.chat.title, reason
                    ),
                    parse_mode=ParseMode.HTML,
                )
            else:
                context.bot.sendMessage(
                    chat.id,
                    "<b>Banned:</b> {} \n<b>Admin:</b> {}\n<b>Chat:</b> <b>{}</b>".format(
                        mention_html(member.user.id, member.user.first_name), mention_html(
                            user.id, user.first_name),
                        message.chat.title
                    ),
                    parse_mode=ParseMode.HTML,
                )
            return log_message
    except BadRequest as excp:
        if excp.message == "Reply message not found":
            # Do not reply
            if silent:
                return log_message
            message.reply_text("Banned!", quote=False)
            return log_message
        else:
            log.warning(update)
            log.exception(
                "ERROR banning user %s in chat %s (%s) due to %s",
                user_id,
                chat.title,
                chat.id,
                excp.message,
            )
            message.reply_text("Well damn, I can't ban that user.")

    return log_message


@metacmd(command='tban', pass_args=True)
@connection_status
@bot_admin
@can_restrict
@user_admin(AdminPerms.CAN_RESTRICT_MEMBERS)
@loggable
def temp_ban(update: Update, context: CallbackContext) -> str:
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    log_message = ""
    reason = ""
    bot, args = context.bot, context.args
    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("I doubt that's a user.")
        return log_message

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message != 'User not found':
            raise
        message.reply_text("I can't seem to find this user.")
        return log_message
    if user_id == bot.id:
        message.reply_text("I'm not gonna BAN myself, are you crazy?")
        return log_message

    if is_user_ban_protected(update, user_id, member):
        message.reply_text("I don't feel like it.")
        return log_message

    if not reason:
        message.reply_text(
            "You haven't specified a time to ban this user for!")
        return log_message

    split_reason = reason.split(None, 1)

    time_val = split_reason[0].lower()
    reason = split_reason[1] if len(split_reason) > 1 else ""
    bantime = extract_time(message, time_val)

    if not bantime:
        return log_message

    log_message = (
        f"<b>{html.escape(chat.title)}:</b>\n"
        "#TEMP BANNED\n"
        f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
        f"<b>User:</b> {mention_html(member.user.id, member.user.first_name)}\n"
        f"<b>Time:</b> {time_val}"
    )
    if reason:
        log_message += "\n<b>Reason:</b> {}".format(reason)

    try:
        chat.ban_member(user_id, until_date=bantime)
        # bot.send_sticker(chat.id, BAN_STICKER)  # banhammer marie sticker
        bot.sendMessage(
            chat.id,
            f"Banned! User {mention_html(member.user.id, member.user.first_name)} will be banned for {time_val}.\nReason: {reason}",
            parse_mode=ParseMode.HTML,
        )
        return log_message

    except BadRequest as excp:
        if excp.message == "Reply message not found":
            # Do not reply
            message.reply_text(
                f"Banned! User will be banned for {time_val}.", quote=False
            )
            return log_message
        else:
            log.warning(update)
            log.exception(
                "ERROR banning user %s in chat %s (%s) due to %s",
                user_id,
                chat.title,
                chat.id,
                excp.message,
            )
            message.reply_text("Well damn, I can't ban that user.")

    return log_message


@metacmd(command=['kick', 'dkick', 'skick'], pass_args=True)
@connection_status
@bot_admin
@can_restrict
@user_admin(AdminPerms.CAN_RESTRICT_MEMBERS)
@loggable
def kick(update: Update, context: CallbackContext) -> str:
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    log_message = ""
    bot, args = context.bot, context.args
    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("I doubt that's a user.")
        return log_message

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message != 'User not found':
            raise
        message.reply_text("I can't seem to find this user.")
        return log_message
    if user_id == bot.id:
        message.reply_text("Yeahhh I'm not gonna do that.")
        return log_message

    if is_user_ban_protected(update, user_id):
        message.reply_text("I really wish I could kick this user....")
        return log_message

    if message.text.startswith(('/s', '!s')):
        silent = True
        if not can_delete(chat, context.bot.id):
            message.reply_text('I cannot delete messages in this chat, please give me the necessary admin permission!', reply_to_message_id=message.message_id, allow_sending_without_reply=True)
            return
    else:
        silent = False
    
    if message.text.startswith(('/d', '!d')):
        delkick = True
        if not can_delete(chat, context.bot.id):
            message.reply_text('I cannot delete messages in this chat, please give me the necessary admin permission!', reply_to_message_id=message.message_id, allow_sending_without_reply=True)
            return
    else:
        delkick = False

    res = chat.unban_member(user_id)  # unban on current user = kick
    if res:
        if delkick:
            if has_reply_to_message(message):
                message.reply_to_message.delete()
        if not silent:
        # bot.send_sticker(chat.id, BAN_STICKER)  # banhammer marie sticker
            bot.sendMessage(
                chat.id,
                f"{mention_html(member.user.id, member.user.first_name)} was kicked by {mention_html(user.id, user.first_name)} in {message.chat.title}\n<b>Reason</b>: <code>{reason}</code>",
                parse_mode=ParseMode.HTML,
            )
        else:
            if message:
                message.delete()
        log_message = (
            f"<b>{html.escape(chat.title)}:</b>\n"
            f"#KICKED\n"
            f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
            f"<b>User:</b> {mention_html(member.user.id, member.user.first_name)}"
        )
        if reason:
            log_message += f"\n<b>Reason:</b> {reason}"

        return log_message

    else:
        message.reply_text("Well damn, I can't kick that user.")

    return log_message


@metacmd(command='kickme', pass_args=True, filters=Filters.chat_type.groups)
@bot_admin
@can_restrict
def kickme(update: Update, context: CallbackContext):
    user_id = update.effective_message.from_user.id
    if is_user_admin(update, user_id):
        update.effective_message.reply_text(
            "I wish I could... but you're an admin.")
        return

    res = update.effective_chat.unban_member(
        user_id)  # unban on current user = kick
    if res:
        update.effective_message.reply_text("*kicks you out of the group*")
    else:
        update.effective_message.reply_text("Huh? I can't :/")


@metacmd(command='unban', pass_args=True)
@connection_status
@bot_admin
@can_restrict
@user_admin(AdminPerms.CAN_RESTRICT_MEMBERS)
@loggable
def unban(update: Update, context: CallbackContext) -> Optional[str]:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    log_message = ""
    bot, args = context.bot, context.args
    if has_reply_to_message(message) and message.reply_to_message.sender_chat:
        r = bot.unban_chat_sender_chat(
            chat_id=chat.id, sender_chat_id=message.reply_to_message.sender_chat.id)
        if r:
            message.reply_text("Channel {} was unbanned successfully from {}".format(
                html.escape(message.reply_to_message.sender_chat.title),
                html.escape(chat.title)
            ),
                parse_mode="html"
            )
            return (
                f"<b>{html.escape(chat.title)}:</b>\n"
                f"#UNBANNED\n"
                f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
                f"<b>Channel:</b> {html.escape(message.reply_to_message.sender_chat.title)} ({message.reply_to_message.sender_chat.id})"
            )
        else:
            message.reply_text("Failed to unban channel")
        return
    user_id, reason = extract_user_and_text(message, args)
    if not user_id:
        message.reply_text("I doubt that's a user.")
        return log_message

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message != 'User not found':
            raise
        message.reply_text("I can't seem to find this user.")
        return log_message
    if user_id == bot.id:
        message.reply_text("How would I unban myself if I wasn't here...?")
        return log_message

    if is_user_in_chat(chat, user_id):
        message.reply_text("Isn't this person already here??")
        return log_message

    chat.unban_member(user_id)
    if reason:
        bot.sendMessage(
            chat.id,
            "<b>UnBanned:</b> {} \n<b>Admin:</b> {}\n<b>Chat:</b> <b>{}</b>\n<b>Reason:</b> <code>{}</code>".format(
                mention_html(member.user.id, member.user.first_name), mention_html(
                    user.id, user.first_name),
                message.chat.title, reason
            ),
            parse_mode=ParseMode.HTML,
        )
    else:
        bot.sendMessage(
            chat.id,
            "<b>UnBanned:</b> {} \n<b>Admin:</b> {}\n<b>Chat:</b> <b>{}</b>".format(
                mention_html(member.user.id, member.user.first_name), mention_html(
                    user.id, user.first_name),
                message.chat.title
            ),
            parse_mode=ParseMode.HTML,
        )

    log_message = (
        f"<b>{html.escape(chat.title)}:</b>\n"
        f"#UNBANNED\n"
        f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
        f"<b>User:</b> {mention_html(member.user.id, member.user.first_name)}"
    )
    if reason:
        log_message += f"\n<b>Reason:</b> {reason}"

    return log_message


@metacmd(command='selfunban', pass_args=True)
@connection_status
@bot_admin
@can_restrict
@gloggable
def selfunban(context: CallbackContext, update: Update) -> Optional[str]:
    message = update.effective_message
    user = update.effective_user
    bot, args = context.bot, context.args
    if user.id not in SUDO_USERS:
        return

    try:
        chat_id = int(args[0])
    except:
        message.reply_text("Give a valid chat ID.")
        return

    chat = bot.getChat(chat_id)

    try:
        member = chat.get_member(user.id)
    except BadRequest as excp:
        if excp.message == "User not found":
            message.reply_text("I can't seem to find this user.")
            return
        else:
            raise

    if is_user_in_chat(chat, user.id):
        message.reply_text("Aren't you already in the chat??")
        return

    chat.unban_member(user.id)
    message.reply_text("Yep, I have unbanned you.")

    log_message = (
        f"<b>{html.escape(chat.title)}:</b>\n"
        f"#UNBANNED\n"
        f"<b>User:</b> {mention_html(member.user.id, member.user.first_name)}"
    )

    return log_message


def get_help(chat):
    return gs(chat, "bans_help")


__mod_name__ = "Bans"
