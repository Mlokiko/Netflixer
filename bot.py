from __future__ import annotations

import os
import re
import time
import asyncio
import logging
import imaplib
from email.header import decode_header
from email.message import Message
from email.parser import BytesParser
from datetime import datetime, timedelta, timezone
from typing import Literal

import discord
from discord.ext import commands
from dotenv import load_dotenv

# ── Configuration ──────────────────────────────────────────────
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
POST_DESTINATION = os.getenv("POST_DESTINATION", "channel").lower()  # "channel" or "interaction"
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")

NETFLIX_URL_PATTERN = re.compile(
    r"https://www\.netflix\.com/account/travel/verify\?nftoken=[^\s\"]+"
)

EMAIL_SUBJECT_CODE = os.getenv(
    "EMAIL_SUBJECT_CODE",
    "Twój kod tymczasowego dostępu do serwisu Netflix",
).lower()
NETFLINK_EXPIRY_MINUTES = int(os.getenv("NETFLINK_EXPIRY_MINUTES", "15"))
KOD_COOLDOWN_SECONDS = int(os.getenv("KOD_COOLDOWN_SECONDS", "10"))
IMAP_MAX_RETRIES = 3
IMAP_BASE_DELAY = 1  # seconds

# ── Logging ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# Suppress discord.py warnings (voice not used by this bot)
logging.getLogger("discord").setLevel(logging.ERROR)
logging.getLogger("discord.gateway").setLevel(logging.ERROR)

# ── Discord Bot (slash commands) ───────────────────────────────
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="", intents=intents)

# ── Rate limiting ──────────────────────────────────────────────
_kod_cooldowns: dict[int, float] = {}
_synced = False


def _check_kod_cooldown(user_id: int) -> bool:
    """Return True if the user is on cooldown."""
    now = time.time()
    last_used = _kod_cooldowns.get(user_id, 0)
    if now - last_used < KOD_COOLDOWN_SECONDS:
        return True
    _kod_cooldowns[user_id] = now
    return False


# ── Helpers ────────────────────────────────────────────────────
def decode_mime_header(header_value: str | None) -> str:
    if not header_value:
        return ""
    parts = decode_header(header_value)
    decoded: list[str] = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def extract_body_text(msg: Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(charset, errors="replace")
    else:
        charset = msg.get_content_charset() or "utf-8"
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode(charset, errors="replace")
    return ""


def extract_netflix_url(body: str) -> str | None:
    match = NETFLIX_URL_PATTERN.search(body)
    return match.group(0) if match else None


def parse_email_date(date_str: str) -> datetime:
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str)
    except Exception:
        log.warning(f"Could not parse date: {date_str}, using now")
        return datetime.now(timezone.utc)


def format_remaining_time(email_date: datetime) -> str:
    now = datetime.now(email_date.tzinfo) if email_date.tzinfo else datetime.now(timezone.utc)
    elapsed = now - email_date
    remaining = timedelta(minutes=NETFLINK_EXPIRY_MINUTES) - elapsed
    if remaining.total_seconds() <= 0:
        return "Wygasł"
    total_seconds = int(remaining.total_seconds())
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"Pozostało {minutes}:{seconds:02d} min"


def format_expiry_timestamp(email_date: datetime) -> str:
    expiry = email_date + timedelta(minutes=NETFLINK_EXPIRY_MINUTES)
    return expiry.strftime("%d.%m.%Y %H:%M")


# ── Email Fetching ─────────────────────────────────────────────
def _do_imap_fetch() -> tuple[str | None, datetime | None] | tuple[Literal["no_url"], None]:
    """Perform a single IMAP fetch attempt. Raises on transient errors."""
    mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    try:
        mail.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        mail.select("INBOX")

        search_date = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%d-%b-%Y")
        status, data = mail.search(None, f'SINCE {search_date}')

        if status != "OK" or not data[0]:
            log.info("No emails found in last 24h")
            return None, None

        msg_ids = data[0].split()
        for msg_id in reversed(msg_ids):
            status, msg_data = mail.fetch(msg_id, "(RFC822)")
            if status != "OK" or not msg_data:
                continue

            parser = BytesParser()
            msg = parser.parsebytes(msg_data[0][1])

            raw_subject = msg.get("Subject", "")
            subject = decode_mime_header(raw_subject)
            subject_lower = subject.lower()

            if EMAIL_SUBJECT_CODE in subject_lower:
                log.info(f"Found Netflix email: {subject}")
                body = extract_body_text(msg)
                url = extract_netflix_url(body)

                if url:
                    date_str = msg.get("Date", "")
                    email_date = parse_email_date(date_str)
                    log.info(f"Found Netflix URL, email sent at {email_date}")
                    return url, email_date
                else:
                    log.warning("Netflix email found but no URL in body")
                    return "no_url", None

        log.info("No matching Netflix email found")
        return None, None
    finally:
        mail.logout()


def _fetch_latest_netflix_email() -> tuple[str | None, datetime | None] | tuple[Literal["no_url"], None]:
    """Fetch with retry logic for transient IMAP errors."""
    for attempt in range(1, IMAP_MAX_RETRIES + 1):
        try:
            result = _do_imap_fetch()
            return result
        except (imaplib.IMAP4.error, OSError, TimeoutError) as e:
            log.warning(f"IMAP attempt {attempt}/{IMAP_MAX_RETRIES} failed: {e}")
            if attempt < IMAP_MAX_RETRIES:
                time.sleep(IMAP_BASE_DELAY * (2 ** (attempt - 1)))
            else:
                log.error(f"IMAP failed after {IMAP_MAX_RETRIES} attempts")
                return None, None
        except Exception as e:
            log.error(f"IMAP error (not retrying): {e}")
            return None, None


async def fetch_latest_netflix_url() -> tuple[str | None, datetime | None] | tuple[Literal["no_url"], None]:
    return await asyncio.to_thread(_fetch_latest_netflix_email)


def _resolve_channel() -> discord.abc.Messageable | None:
    """Resolve the target channel. Returns None if nothing found."""
    if DISCORD_CHANNEL_ID:
        try:
            channel = bot.get_channel(int(DISCORD_CHANNEL_ID))
            if channel:
                return channel
        except ValueError:
            log.warning(f"Invalid DISCORD_CHANNEL_ID: {DISCORD_CHANNEL_ID!r}")
    channel = next(
        (ch for guild in bot.guilds for ch in guild.text_channels
         if ch.permissions_for(guild.me).send_messages),
        None,
    )
    return channel


async def send_url_to_discord(url: str, email_date: datetime, channel: discord.abc.Messageable | None = None) -> bool:
    """Send the Netflix URL embed to a channel.
    
    Args:
        url: The Netflix verification URL.
        email_date: datetime of the email (for expiry calculation).
        channel: Optional channel to send to. If None, uses _resolve_channel().
    """
    try:
        if channel is None:
            channel = _resolve_channel()
        if not channel:
            log.error("No suitable channel found to send the URL")
            return False

        remaining = format_remaining_time(email_date)
        is_expired = remaining == "Wygasł"

        if is_expired:
            expiry_ts = format_expiry_timestamp(email_date)
            embed = discord.Embed(
                title="",
                description=f"Kod wygasł\n\nWygasł: {expiry_ts}",
                color=discord.Color.red(),
            )
        else:
            embed = discord.Embed(
                title="",
                description=f"[**Uzyskaj kod**]({url})\n\nStatus: {remaining}",
                color=discord.Color.green(),
            )

        await channel.send(embed=embed)
        log.info("Sent Netflix URL to Discord")
        return True

    except Exception as e:
        log.error(f"Discord send error: {e}")
        return False


# ── Slash Commands ─────────────────────────────────────────────
@bot.tree.command(name="kod", description="Link do uzyskania kodu jednorazowego do Netflix'a")
async def kod(interaction: discord.Interaction):
    if _check_kod_cooldown(interaction.user.id):
        remaining = KOD_COOLDOWN_SECONDS - int(
            asyncio.get_running_loop().time() - _kod_cooldowns[interaction.user.id]
        )
        await interaction.response.send_message(
            f"⏳ Poczekaj jeszcze {remaining}s przed kolejnym użyciem komendy.",
            ephemeral=True,
        )
        return

    await interaction.response.defer()
    url, email_date = await fetch_latest_netflix_url()
    if url == "no_url":
        await interaction.followup.send("❌ Znaleziono email od Netflix'a, ale nie znaleziono linku do kodu")
    elif url:
        target_channel = interaction.channel if POST_DESTINATION == "interaction" else None
        sent = await send_url_to_discord(url, email_date, channel=target_channel)
        if not sent:
            await interaction.followup.send("❌ Nie udało się wysłać kodu — sprawdź uprawnienia bota")
        else:
            await interaction.delete_original_response()
    else:
        await interaction.followup.send("❌ Nie znaleziono nowego emaila od Netflix'a")
    

@bot.tree.command(name="zmien-gospodarstwo", description="Zmienia gospodarstwo domowe (często spotykane przy logowaniu na TV/Konsoli)")
async def zmien_gospodarstwo(interaction: discord.Interaction):
    await interaction.response.send_message("TODO")


@bot.tree.command(name="ping", description="Sprawdza, czy bot jest online")
async def ping(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Pong! 🏓",
        description="Bot działa!",
        color=discord.Color.blue(),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="pomoc", description="Wyświetla listę wszystkich komend bota")
async def pomoc(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Dostępne komendy",
        description="Lista wszystkich komend Netflixera:",
        color=discord.Color.blue(),
    )
    embed.add_field(name="/kod", value="Link do uzyskania kodu jednorazowego do Netflix'a", inline=False)
    embed.add_field(name="/zmien-gospodarstwo", value="Zmienia gospodarstwo domowe (często spotykane przy logowaniu na TV/Konsoli)", inline=False)
    embed.add_field(name="/ping", value="Sprawdza, czy bot jest online", inline=False)
    embed.add_field(name="/pomoc", value="Wyświetla listę wszystkich komend bota", inline=False)
    embed.set_footer(text="Użyj komendy, wpisując / w czacie")
    await interaction.response.send_message(embed=embed)


# ── Message Handling ───────────────────────────────────────────
# Only slash commands — ignore all text messages entirely
@bot.event
async def on_message(message: discord.Message):
    # Slash commands are handled by bot.tree, not process_commands
    pass


# ── Startup ────────────────────────────────────────────────────
@bot.event
async def on_ready():
    global _synced
    if not _synced:
        await bot.tree.sync()
        _synced = True
        log.info("Synced slash commands")

    log.info(f"Logged in as {bot.user}")
    log.info(f"Bot is connected to {len(bot.guilds)} guild(s)")

    # ── Warn if configured channel can't be resolved ──
    if DISCORD_CHANNEL_ID and POST_DESTINATION == "channel":
        try:
            channel = bot.get_channel(int(DISCORD_CHANNEL_ID))
            if channel:
                log.info(f"Target channel resolved: #{channel.name} (ID: {channel.id})")
            else:
                log.warning(
                    f"DISCORD_CHANNEL_ID={DISCORD_CHANNEL_ID} could not be resolved. "
                    "The bot may not have access to this channel, or it doesn't exist. "
                    "Codes will fall back to the first writable channel."
                )
        except ValueError:
            log.warning(f"Invalid DISCORD_CHANNEL_ID: {DISCORD_CHANNEL_ID!r}")


# ── Validation ─────────────────────────────────────────────────
def _validate_discord_token() -> None:
    """Validate Discord token format. Raises ValueError on failure."""
    if not DISCORD_TOKEN:
        raise ValueError("DISCORD_BOT_TOKEN is not set")
    # Discord tokens have the format: <base64_id>.<base64_timestamp>.<signature>
    parts = DISCORD_TOKEN.split(".")
    if len(parts) != 3:
        raise ValueError(
            f"DISCORD_BOT_TOKEN has invalid format (expected 3 parts separated by '.'): {DISCORD_TOKEN!r}"
        )
    for i, part in enumerate(parts):
        if not part:
            raise ValueError(f"DISCORD_BOT_TOKEN part {i + 1} is empty")


def _validate_imap_credentials() -> None:
    """Test IMAP login with the configured credentials. Raises ValueError on failure."""
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        mail.logout()
        log.info("IMAP credentials validated successfully")
    except imaplib.IMAP4.authentication_errors:
        raise ValueError(
            "IMAP login failed — check EMAIL_ADDRESS and EMAIL_APP_PASSWORD. "
            "Ensure App Passwords are enabled in your Google account."
        )
    except imaplib.IMAP4.error as e:
        raise ValueError(f"IMAP error during validation: {e}")
    except OSError as e:
        raise ValueError(f"Cannot reach imap.gmail.com: {e}")


def validate_config() -> None:
    errors: list[str] = []

    # ── Discord token ──
    try:
        _validate_discord_token()
    except ValueError as e:
        errors.append(str(e))

    # ── Email credentials ──
    if not EMAIL_ADDRESS:
        errors.append("EMAIL_ADDRESS is not set")
    elif "@" not in EMAIL_ADDRESS:
        errors.append(f"EMAIL_ADDRESS does not look like a valid email: {EMAIL_ADDRESS!r}")

    if not EMAIL_APP_PASSWORD:
        errors.append("EMAIL_APP_PASSWORD is not set")

    if EMAIL_ADDRESS and EMAIL_APP_PASSWORD:
        try:
            _validate_imap_credentials()
        except ValueError as e:
            errors.append(str(e))

    # ── Channel ID format ──
    if DISCORD_CHANNEL_ID:
        try:
            int(DISCORD_CHANNEL_ID)
        except ValueError:
            errors.append(f"DISCORD_CHANNEL_ID must be a numeric value, got: {DISCORD_CHANNEL_ID!r}")

    if POST_DESTINATION not in ("channel", "interaction"):
        errors.append(f"POST_DESTINATION must be 'channel' or 'interaction', got: {POST_DESTINATION!r}")

    try:
        expiry = int(os.getenv("NETFLINK_EXPIRY_MINUTES", "15"))
        if expiry <= 0:
            errors.append(f"NETFLINK_EXPIRY_MINUTES must be > 0, got: {expiry}")
    except ValueError:
        errors.append(f"NETFLINK_EXPIRY_MINUTES must be a valid integer, got: {os.getenv('NETFLINK_EXPIRY_MINUTES')!r}")

    if errors:
        for e in errors:
            log.error(e)
        exit(1)


# ── Start ──────────────────────────────────────────────────────
if __name__ == "__main__":
    validate_config()
    bot.run(DISCORD_TOKEN)
