
# -*- coding: utf-8 -*-
"""WeatherGPT authentication using SQLite sessions and Brevo email OTP.

Email OTP:
    Register -> verify email -> account created -> login.
    Login -> receive OTP -> verify -> login.

Phone OTP:
    Twilio SMS or PHONE_OTP_DEV=1 for local testing.

Social login:
    Google and Facebook OAuth 2.0.
"""

import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import requests
from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

bp = Blueprint("auth", __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "weathergpt.db")

EMAIL_RE = re.compile(
    r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"
)
PHONE_RE = re.compile(r"^\+[1-9]\d{9,14}$")

OTP_TTL = 600
OTP_MAX_TRIES = 5
OTP_RESEND_GAP = 30

# Pending OTPs are held in memory for this running process.
_pending = {}


# ---------------------------------------------------------------------------
# Secret key and database
# ---------------------------------------------------------------------------

def load_secret_key():
    """Load SECRET_KEY or persist a random local-development key."""
    env_key = os.getenv("SECRET_KEY", "").strip()
    if env_key:
        return env_key

    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, "secret.key")

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            value = f.read().strip()
            if value:
                return value

    value = secrets.token_hex(32)
    with open(path, "w", encoding="utf-8") as f:
        f.write(value)

    return value


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)

    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login TEXT
            )
        """)

        cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(users)")
        }

        if "phone" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN phone TEXT")

        if "provider" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN provider TEXT")

        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone
            ON users(phone)
            WHERE phone IS NOT NULL
        """)


def init_auth(app):
    app.secret_key = load_secret_key()

    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_NAME="weathergpt_session",
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    )

    # HTTPS-only cookies should be enabled when deployed over HTTPS.
    if os.getenv("COOKIE_SECURE", "").strip() == "1":
        app.config["SESSION_COOKIE_SECURE"] = True

    init_db()
    app.register_blueprint(bp)

    
    @app.before_request
    def require_login():
        endpoint = request.endpoint or ""

        # Allow Google Search Console verification without login.
        if request.path == "/google825a0e9664b14fbc.html":
            return None

        # Allow static files and authentication routes.
        if endpoint == "static" or endpoint.startswith("auth."):
            return None

        # Allow users who are already logged in.
        if current_user():
            return None

        # Redirect unauthenticated visitors from the home page to login.
        if request.path == "/":
            return redirect(url_for("auth.login_page"))

        # Keep all other protected routes secure.
        return jsonify({
            "error": "Please log in to continue.",
            "login_required": True,
        }), 401


    @app.after_request
    def no_cache_for_private(resp):
        if (
            request.endpoint
            and not request.path.startswith("/static")
            and request.method == "GET"
        ):
            resp.headers.setdefault("Cache-Control", "no-cache")
        return resp


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None

    with db() as conn:
        row = conn.execute(
            "SELECT id, name, email FROM users WHERE id = ?",
            (uid,),
        ).fetchone()

    if not row:
        session.clear()
        return None

    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
    }


def start_session(user_id, remember=True):
    session.clear()
    session["user_id"] = user_id
    session.permanent = bool(remember)


def clean_email(value):
    return str(value or "").strip().lower()


def valid_email(email):
    return bool(EMAIL_RE.fullmatch(email)) and len(email) <= 120


def clean_name(value):
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_phone(value):
    """Normalize a phone number to E.164 format."""
    raw = str(value or "").strip()
    digits = re.sub(r"\D", "", raw)

    if not digits:
        return None

    if raw.startswith("+"):
        number = "+" + digits
    elif len(digits) == 10:
        country = os.getenv("PHONE_DEFAULT_COUNTRY", "+91").strip()
        number = country + digits
    elif raw.startswith("00"):
        number = "+" + digits[2:]
    else:
        number = "+" + digits

    return number if PHONE_RE.fullmatch(number) else None


# ---------------------------------------------------------------------------
# OTP generation and verification
# ---------------------------------------------------------------------------

def make_code(key, name, mode):
    otp = "%06d" % secrets.randbelow(1_000_000)

    _pending[key] = {
        "mode": mode,
        "name": name,
        "otp_hash": generate_password_hash(otp),
        "expires": time.time() + OTP_TTL,
        "tries": 0,
        "sent_at": time.time(),
    }

    return otp


def too_soon(key):
    pending = _pending.get(key)
    return (
        bool(pending)
        and time.time() - pending["sent_at"] < OTP_RESEND_GAP
    )


def check_code(key, code):
    """Return (pending, None) if valid, or (None, error_response)."""
    pending = _pending.get(key)

    if not pending:
        return None, (
            jsonify({
                "error": "No code requested. Please request a new one."
            }),
            400,
        )

    if time.time() > pending["expires"]:
        _pending.pop(key, None)
        return None, (
            jsonify({
                "error": "Code expired. Please request a new one."
            }),
            400,
        )

    if pending["tries"] >= OTP_MAX_TRIES:
        _pending.pop(key, None)
        return None, (
            jsonify({
                "error": "Too many wrong attempts. Please request a new code."
            }),
            429,
        )

    if not check_password_hash(pending["otp_hash"], code):
        pending["tries"] += 1
        return None, (jsonify({"error": "Incorrect code."}), 400)

    return pending, None


# ---------------------------------------------------------------------------
# Email OTP using the Brevo transactional email API
# ---------------------------------------------------------------------------

def send_otp_email(to_email, name, otp):
    api_key = os.getenv("BREVO_API_KEY", "").strip()
    sender_email = os.getenv("BREVO_SENDER_EMAIL", "").strip()
    sender_name = os.getenv("BREVO_SENDER_NAME", "WeatherGPT").strip()

    if not api_key:
        raise RuntimeError("BREVO_API_KEY is missing from .env.")

    if not sender_email:
        raise RuntimeError("BREVO_SENDER_EMAIL is missing from .env.")

    payload = {
        "sender": {
            "name": sender_name,
            "email": sender_email,
        },
        "to": [
            {
                "email": to_email,
                "name": name or to_email,
            }
        ],
        "subject": "Your WeatherGPT verification code",
        "textContent": (
            "Hi %s,\n\n"
            "Your WeatherGPT verification code is: %s\n\n"
            "This code expires in 10 minutes. "
            "If you did not request it, please ignore this email."
        ) % (name or "there", otp),
    }

    response = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
        },
        json=payload,
        timeout=15,
    )

    if not response.ok:
        # Do not expose the API key or the full provider response to users.
        raise RuntimeError(
            "Brevo email request failed with HTTP %s."
            % response.status_code
        )


def issue_otp(email, name, mode):
    otp = make_code(email, name, mode)

    try:
        send_otp_email(email, name, otp)
    except Exception:
        _pending.pop(email, None)
        raise


def otp_sent_response(email):
    return jsonify({
        "ok": True,
        "otp_required": True,
        "email": email,
        "message": "We sent a 6-digit code to your email.",
    })


# ---------------------------------------------------------------------------
# Phone OTP through Twilio
# ---------------------------------------------------------------------------

class SmsNotConfigured(RuntimeError):
    pass


def send_sms(to_number, body):
    sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    sender = os.getenv("TWILIO_FROM", "").strip()
    service = os.getenv("TWILIO_MESSAGING_SERVICE_SID", "").strip()

    if sid and token and (sender or service):
        data = {"To": to_number, "Body": body}

        if service:
            data["MessagingServiceSid"] = service
        else:
            data["From"] = sender

        response = requests.post(
            "https://api.twilio.com/2010-04-01/Accounts/%s/Messages.json"
            % sid,
            data=data,
            auth=(sid, token),
            timeout=15,
        )
        response.raise_for_status()
        return

    if os.getenv("PHONE_OTP_DEV", "").strip() == "1":
        print("[WeatherGPT DEV SMS] to %s: %s" % (to_number, body))
        return

    raise SmsNotConfigured()


def issue_phone_otp(phone, name, mode):
    key = "tel:" + phone
    otp = make_code(key, name, mode)

    try:
        send_sms(
            phone,
            "Your WeatherGPT code is %s. It expires in 10 minutes." % otp,
        )
    except Exception:
        _pending.pop(key, None)
        raise


# ---------------------------------------------------------------------------
# Authentication pages
# ---------------------------------------------------------------------------

@bp.route("/login")
def login_page():
    if current_user():
        return redirect("/")
    return render_template("auth.html", mode="login")


@bp.route("/register")
def register_page():
    if current_user():
        return redirect("/")
    return render_template("auth.html", mode="register")


@bp.route("/logout")
def logout_page():
    session.clear()
    return redirect(url_for("auth.login_page"))


# ---------------------------------------------------------------------------
# Email registration
# ---------------------------------------------------------------------------

@bp.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    name = clean_name(data.get("name"))
    email = clean_email(data.get("email"))

    errors = {}

    if not 2 <= len(name) <= 50:
        errors["name"] = "Enter your name (2–50 characters)."

    if not valid_email(email):
        errors["email"] = "Enter a valid email address."

    if errors:
        return jsonify({
            "error": next(iter(errors.values())),
            "fields": errors,
        }), 400

    with db() as conn:
        exists = conn.execute(
            "SELECT 1 FROM users WHERE email = ?",
            (email,),
        ).fetchone()

    if exists:
        return jsonify({
            "error": "That email is already registered. Log in instead.",
            "fields": {"email": "That email is already registered."},
        }), 409

    if too_soon(email):
        return jsonify({
            "error": "Please wait a few seconds before requesting another code."
        }), 429

    try:
        issue_otp(email, name, "register")
    except Exception:
        app_logger_error("Failed to send registration OTP.")
        return jsonify({
            "error": "Could not send the verification email. Check server configuration and try again."
        }), 502

    return otp_sent_response(email)


# ---------------------------------------------------------------------------
# Email login
# ---------------------------------------------------------------------------

@bp.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = clean_email(data.get("email"))

    if not email:
        return jsonify({"error": "Enter your email."}), 400

    if not valid_email(email):
        return jsonify({"error": "Enter a valid email address."}), 400

    with db() as conn:
        row = conn.execute(
            "SELECT name FROM users WHERE email = ?",
            (email,),
        ).fetchone()

    if not row:
        return jsonify({
            "error": "No account found for that email. Please register first."
        }), 404

    if too_soon(email):
        return jsonify({
            "error": "Please wait a few seconds before requesting another code."
        }), 429

    try:
        issue_otp(email, row["name"], "login")
    except Exception:
        app_logger_error("Failed to send login OTP.")
        return jsonify({
            "error": "Could not send the verification email. Check server configuration and try again."
        }), 502

    return otp_sent_response(email)


# ---------------------------------------------------------------------------
# Email OTP verification
# ---------------------------------------------------------------------------

@bp.route("/auth/verify", methods=["POST"])
def verify_otp():
    data = request.get_json(silent=True) or {}

    email = clean_email(data.get("email"))
    code = str(data.get("otp", "")).strip()
    remember = bool(data.get("remember", True))

    if not valid_email(email):
        return jsonify({"error": "Enter a valid email address."}), 400

    if not re.fullmatch(r"\d{6}", code):
        return jsonify({"error": "Enter the 6-digit verification code."}), 400

    pending, error = check_code(email, code)

    if error:
        return error

    now = datetime.now(timezone.utc).isoformat()

    try:
        with db() as conn:
            row = conn.execute(
                "SELECT id, name FROM users WHERE email = ?",
                (email,),
            ).fetchone()

            if pending["mode"] == "register":
                if row:
                    _pending.pop(email, None)
                    return jsonify({
                        "error": "That email is already registered. Log in instead."
                    }), 409

                conn.execute(
                    """
                    INSERT INTO users
                    (name, email, password_hash, created_at, last_login, provider)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pending["name"],
                        email,
                        "!otp-only",
                        now,
                        None,
                        "email",
                    ),
                )

                _pending.pop(email, None)

                return jsonify({
                    "ok": True,
                    "registered": True,
                    "user": {
                        "name": pending["name"],
                        "email": email,
                    },
                    "redirect": None,
                }), 201

            if not row:
                _pending.pop(email, None)
                return jsonify({
                    "error": "No account found for that email. Please register first."
                }), 404

            user_id = row["id"]
            name = row["name"]

            conn.execute(
                "UPDATE users SET last_login = ? WHERE id = ?",
                (now, user_id),
            )

    except sqlite3.IntegrityError:
        _pending.pop(email, None)
        return jsonify({
            "error": "That email is already registered. Log in instead."
        }), 409

    _pending.pop(email, None)
    start_session(user_id, remember)

    return jsonify({
        "ok": True,
        "user": {"name": name, "email": email},
        "redirect": "/",
    })


# ---------------------------------------------------------------------------
# Resend email OTP
# ---------------------------------------------------------------------------

@bp.route("/auth/resend", methods=["POST"])
def resend_otp():
    data = request.get_json(silent=True) or {}
    email = clean_email(data.get("email"))

    pending = _pending.get(email)

    if not pending:
        return jsonify({
            "error": "No code requested for this email. Please start again."
        }), 400

    if too_soon(email):
        return jsonify({
            "error": "Please wait a few seconds before requesting another code."
        }), 429

    try:
        issue_otp(email, pending["name"], pending["mode"])
    except Exception:
        app_logger_error("Failed to resend email OTP.")
        return jsonify({
            "error": "Could not send the verification email. Try again."
        }), 502

    return jsonify({"ok": True, "message": "A new code was sent."})


# ---------------------------------------------------------------------------
# Phone OTP endpoints
# ---------------------------------------------------------------------------

@bp.route("/auth/phone/send", methods=["POST"])
def phone_send():
    data = request.get_json(silent=True) or {}

    phone = normalize_phone(data.get("phone"))
    name = clean_name(data.get("name"))

    if not phone:
        return jsonify({
            "error": "Enter a valid phone number with country code if needed.",
            "fields": {"phone": "Enter a valid phone number."},
        }), 400

    if name and not 2 <= len(name) <= 50:
        return jsonify({
            "error": "Name must be 2–50 characters.",
            "fields": {"name": "Name must be 2–50 characters."},
        }), 400

    key = "tel:" + phone

    if too_soon(key):
        return jsonify({
            "error": "Please wait a few seconds before requesting another code."
        }), 429

    try:
        issue_phone_otp(phone, name, "phone")
    except SmsNotConfigured:
        return jsonify({
            "error": "Phone login is not configured. Set TWILIO_* keys in .env "
                     "or use PHONE_OTP_DEV=1 for local testing."
        }), 503
    except Exception:
        app_logger_error("Failed to send phone OTP.")
        return jsonify({
            "error": "Could not send the SMS. Check the number and try again."
        }), 502

    return jsonify({
        "ok": True,
        "otp_required": True,
        "phone": phone,
        "message": "We sent a 6-digit code by SMS.",
    })


@bp.route("/auth/phone/verify", methods=["POST"])
def phone_verify():
    data = request.get_json(silent=True) or {}

    phone = normalize_phone(data.get("phone"))
    code = str(data.get("otp", "")).strip()
    remember = bool(data.get("remember", True))

    if not phone:
        return jsonify({"error": "Enter a valid phone number."}), 400

    if not re.fullmatch(r"\d{6}", code):
        return jsonify({"error": "Enter the 6-digit verification code."}), 400

    key = "tel:" + phone
    pending, error = check_code(key, code)

    if error:
        return error

    now = datetime.now(timezone.utc).isoformat()

    try:
        with db() as conn:
            row = conn.execute(
                "SELECT id, name, email FROM users WHERE phone = ?",
                (phone,),
            ).fetchone()

            if row:
                user_id = row["id"]
                name = row["name"]
                email = row["email"]

                conn.execute(
                    "UPDATE users SET last_login = ? WHERE id = ?",
                    (now, user_id),
                )
            else:
                name = pending["name"] or ("User " + phone[-4:])
                email = "%s@phone.weathergpt.local" % phone.lstrip("+")

                cur = conn.execute(
                    """
                    INSERT INTO users
                    (name, email, password_hash, created_at, last_login, phone, provider)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        email,
                        "!phone-otp",
                        now,
                        now,
                        phone,
                        "phone",
                    ),
                )

                user_id = cur.lastrowid

    except sqlite3.IntegrityError:
        _pending.pop(key, None)
        return jsonify({
            "error": "That number is already registered. Please try again."
        }), 409

    _pending.pop(key, None)
    start_session(user_id, remember)

    return jsonify({
        "ok": True,
        "user": {"name": name, "email": email},
        "redirect": "/",
    })


# ---------------------------------------------------------------------------
# Google and Facebook OAuth helpers
# ---------------------------------------------------------------------------

def _providers():
    return {
        "google": {
            "label": "Google",
            "id": os.getenv("GOOGLE_CLIENT_ID", "").strip(),
            "secret": os.getenv("GOOGLE_CLIENT_SECRET", "").strip(),
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "scope": "openid email profile",
            "extra": {"prompt": "select_account"},
        },
        "facebook": {
            "label": "Facebook",
            "id": os.getenv("FACEBOOK_APP_ID", "").strip(),
            "secret": os.getenv("FACEBOOK_APP_SECRET", "").strip(),
            "auth_url": "https://www.facebook.com/v19.0/dialog/oauth",
            "scope": "email,public_profile",
            "extra": {},
        },
    }


def _redirect_uri(provider):
    base = os.getenv("OAUTH_REDIRECT_BASE", "").strip().rstrip("/")
    path = url_for("auth.social_callback", provider=provider)

    if base:
        return base + path

    return url_for(
        "auth.social_callback",
        provider=provider,
        _external=True,
    )


def _login_error(code):
    return redirect(
        url_for("auth.login_page", social_error=code)
    )


def _fetch_profile(provider, cfg, code):
    """Exchange OAuth authorization code and return name, email, verified."""
    redirect_uri = _redirect_uri(provider)

    if provider == "google":
        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": cfg["id"],
                "client_secret": cfg["secret"],
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
        token_response.raise_for_status()
        access = token_response.json()["access_token"]

        info = requests.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": "Bearer " + access},
            timeout=15,
        )
        info.raise_for_status()

        data = info.json()

        return (
            clean_name(data.get("name") or data.get("given_name") or ""),
            clean_email(data.get("email")),
            bool(data.get("email_verified")),
        )

    token_response = requests.get(
        "https://graph.facebook.com/v19.0/oauth/access_token",
        params={
            "client_id": cfg["id"],
            "client_secret": cfg["secret"],
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=15,
    )
    token_response.raise_for_status()
    access = token_response.json()["access_token"]

    info = requests.get(
        "https://graph.facebook.com/me",
        params={
            "fields": "id,name,email",
            "access_token": access,
        },
        timeout=15,
    )
    info.raise_for_status()

    data = info.json()
    email = clean_email(data.get("email"))

    if not email:
        email = "fb%s@facebook.weathergpt.local" % data.get("id", "user")

    return clean_name(data.get("name") or ""), email, True


@bp.route("/auth/social/<provider>")
def social_start(provider):
    cfg = _providers().get(provider)

    if not cfg:
        return _login_error("unknown_provider")

    if not (cfg["id"] and cfg["secret"]):
        return _login_error(provider + "_not_configured")

    state = secrets.token_urlsafe(24)
    session["oauth_state"] = state

    params = {
        "client_id": cfg["id"],
        "redirect_uri": _redirect_uri(provider),
        "response_type": "code",
        "scope": cfg["scope"],
        "state": state,
    }
    params.update(cfg["extra"])

    return redirect(
        cfg["auth_url"] + "?" + requests.compat.urlencode(params)
    )


@bp.route("/auth/social/<provider>/callback")
def social_callback(provider):
    cfg = _providers().get(provider)

    if not cfg or not (cfg["id"] and cfg["secret"]):
        return _login_error(
            (provider if cfg else "unknown") + "_not_configured"
        )

    if request.args.get("error"):
        return _login_error("denied")

    expected = session.pop("oauth_state", None)

    if (
        not expected
        or not secrets.compare_digest(
            expected, request.args.get("state", "")
        )
    ):
        return _login_error("failed")

    code = request.args.get("code", "")

    if not code:
        return _login_error("failed")

    try:
        name, email, verified = _fetch_profile(provider, cfg, code)
    except Exception:
        app_logger_error("Social login profile retrieval failed.")
        return _login_error("failed")

    if not valid_email(email) and not email.endswith(".weathergpt.local"):
        return _login_error("failed")

    if not verified:
        return _login_error("unverified")

    now = datetime.now(timezone.utc).isoformat()

    with db() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,),
        ).fetchone()

        if row:
            user_id = row["id"]

            conn.execute(
                "UPDATE users SET last_login = ? WHERE id = ?",
                (now, user_id),
            )
        else:
            display = (
                name
                if 2 <= len(name) <= 50
                else email.split("@")[0][:50] or "User"
            )

            cur = conn.execute(
                """
                INSERT INTO users
                (name, email, password_hash, created_at, last_login, provider)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    display,
                    email,
                    "!oauth",
                    now,
                    now,
                    provider,
                ),
            )

            user_id = cur.lastrowid

    start_session(user_id, True)
    return redirect("/")


# ---------------------------------------------------------------------------
# Logout and current-session endpoints
# ---------------------------------------------------------------------------

@bp.route("/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True, "redirect": "/login"})


@bp.route("/auth/me")
def me():
    user = current_user()

    if not user:
        return jsonify({"authenticated": False}), 401

    return jsonify({
        "authenticated": True,
        "user": user,
    })


# ---------------------------------------------------------------------------
# Minimal server-side logging
# ---------------------------------------------------------------------------

def app_logger_error(message):
    # Do not log OTP values, API keys, or message contents.
    print("[WeatherGPT auth] " + message) 