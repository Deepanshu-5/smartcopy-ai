import os
import json
import secrets
from datetime import date
from functools import wraps
from flask import (Flask, render_template, request, jsonify,
                   redirect, url_for, session)
from dotenv import load_dotenv
from groq import Groq
from supabase import create_client, Client

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except ImportError:
    Limiter = None
    get_remote_address = None

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = Flask(__name__)
# Use provided secret key in production; generate ephemeral key for local dev if missing
secret = os.environ.get("FLASK_SECRET_KEY")
if not secret:
    # generate a temporary secret for local development
    secret = os.urandom(24)
    print("Warning: FLASK_SECRET_KEY not set — using ephemeral secret for dev only.")
app.secret_key = secret
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") == "production",
    MAX_CONTENT_LENGTH=32 * 1024,
)

if Limiter:
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["300 per day", "80 per hour"],
        storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
    )
else:
    class _NoopLimiter:
        def limit(self, *_args, **_kwargs):
            def decorator(fn):
                return fn
            return decorator
    limiter = _NoopLimiter()

# ── Clients ────────────────────────────────────────
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.1-8b-instant"

supabase: Client = create_client(
    os.environ.get("SUPABASE_URL"),
    os.environ.get("SUPABASE_ANON_KEY")
)

DAILY_LIMIT = 5

def get_csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


@app.context_processor
def inject_csrf_token():
    return {"csrf_token": get_csrf_token}


@app.before_request
def validate_csrf_token():
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return None

    expected = session.get("_csrf_token")
    supplied = request.headers.get("X-CSRFToken") or request.form.get("_csrf_token")

    if not expected or not supplied or not secrets.compare_digest(expected, supplied):
        return jsonify({"success": False, "error": "Security token expired. Refresh and try again."}), 400

    return None

# ── Security Headers ──────────────────────────────
@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


@app.errorhandler(429)
def rate_limit_exceeded(_error):
    return jsonify({"success": False, "error": "Too many requests. Please wait and try again."}), 429

# ─────────────────────────────────────────
#  AUTH HELPERS
# ─────────────────────────────────────────

def login_required(f):
    """Decorator — redirects to login if not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    """Returns basic user info from session."""
    return {
        "id":    session.get("user_id"),
        "email": session.get("user_email"),
        "name":  session.get("user_name", ""),
        "plan":  session.get("user_plan", "free"),
    }


def get_or_create_profile(user_id, email):
    """Fetch profile from DB, create if first login."""
    try:
        res = supabase.table("profiles").select("*").eq("id", str(user_id)).execute()
        if res.data:
            return res.data[0]
        # First login — create profile
        new_profile = {
            "id":               str(user_id),
            "email":            email,
            "full_name":        "",  # Empty initially, user can update in settings
            "plan":             "free",
            "emails_today":     0,
            "last_reset_date":  str(date.today()),
        }
        supabase.table("profiles").insert(new_profile).execute()
        return new_profile
    except Exception as e:
        print("Profile error:", e)
        return None


def get_usage_today(user_id):
    """Get how many emails user generated today, resetting if new day."""
    try:
        res = supabase.table("profiles").select(
            "emails_today, last_reset_date"
        ).eq("id", user_id).execute()

        if not res.data:
            return 0

        profile = res.data[0]
        last_reset = profile.get("last_reset_date", "")

        # Reset counter if it's a new day
        if str(last_reset) != str(date.today()):
            supabase.table("profiles").update({
                "emails_today":    0,
                "last_reset_date": str(date.today())
            }).eq("id", user_id).execute()
            return 0

        return profile.get("emails_today", 0)
    except Exception as e:
        print("Usage error:", e)
        return 0


def increment_usage(user_id):
    """Increment user's daily email count."""
    try:
        current = get_usage_today(user_id)
        supabase.table("profiles").update({
            "emails_today": current + 1
        }).eq("id", user_id).execute()
    except Exception as e:
        print("Increment error:", e)


# ─────────────────────────────────────────
#  PROMPT ENGINEERING SYSTEM
# ─────────────────────────────────────────

SYSTEM_PROMPT = """You are a professional cold-email copywriter. Write concise, human-sounding
emails that get replies. Rules: no generic openings ("I hope this finds you well"), avoid
marketing buzzwords (synergy, leverage, game-changer), do not open with the sender's name,
no fluff. Subject lines < 9 words. First line must hook. Single clear CTA. Return ONLY valid JSON
with this structure: {"cold_email":{"subject":"...","body":"..."},"follow_up":{"subject":"...","body":"..."},"linkedin_dm":{"body":"..."}}"""


def build_personalization_context(data):
    level   = data.get("personalization", "Standard")
    prospect = data.get("prospect_name", "there")
    company  = data.get("prospect_company", "their company")
    if level == "Quick":
        return f"Target: {prospect} at {company}. Keep it brief and punchy."
    elif level == "Standard":
        return (f"Target: {prospect}, works at {company}. "
                f"Reference their company naturally — one specific, believable detail.")
    elif level == "Deep":
        return (f"Target: {prospect}, works at {company}. "
                f"Hyper-personalized outreach. Open with something that shows you "
                f"actually looked at {company}. Every sentence must earn its place.")
    return ""


def build_tone_instruction(tone):
    tones = {
        "Professional": "Tone: Professional and polished. Confident without being arrogant. No slang.",
        "Friendly":     "Tone: Warm and approachable. Respectful but not stiff. Light, human energy.",
        "Direct":       "Tone: Blunt and efficient. Get to the point in the first sentence.",
        "Casual":       "Tone: Conversational and relaxed. Write like a peer. Short punchy sentences.",
    }
    return tones.get(tone, tones["Professional"])


def build_goal_instruction(goal):
    goals = {
        "Book a Call":    "CTA: Ask for a specific 15-20 min call. One ask only.",
        "Get a Reply":    "CTA: End with a single easy yes/no question. Low friction.",
        "Demo Request":   "CTA: Ask if they'd like to see it in action. No pressure framing.",
        "Share Resource": "CTA: Offer to send a specific resource. Ask if relevant first.",
    }
    return goals.get(goal, goals["Get a Reply"])


def build_sender_context(data):
    name       = data.get("sender_name", "")
    company    = data.get("sender_company", "")
    offering   = data.get("offering", "")
    experience = data.get("experience", "Intermediate")
    portfolio  = data.get("portfolio", "")
    company_line   = f" at {company}" if company else ""
    portfolio_line = f"\nPortfolio/proof: {portfolio}" if portfolio else ""
    exp_map = {
        "Beginner":     "newer but hungry — let the offer speak",
        "Intermediate": "solid track record — reference results confidence",
        "Expert":       "seasoned pro — write with quiet authority",
    }
    return (f"Sender: {name}{company_line}\n"
            f"What they offer: {offering}\n"
            f"Experience framing: {exp_map.get(experience, '')}"
            f"{portfolio_line}")


def build_user_prompt(data):
    prompt = f"""
{build_sender_context(data)}

{build_personalization_context(data)}

{build_tone_instruction(data.get('tone', 'Professional'))}

{build_goal_instruction(data.get('goal', 'Get a Reply'))}

ADDITIONAL RULES:
- Cold email body: 80-130 words max
- Follow-up body: 50-80 words — reference emailing before, stay light
- LinkedIn DM: 40-60 words — casual, no subject line
- Sign off with just the sender's first name

Generate all three now. Return ONLY the JSON object.
"""
    return prompt.strip()


# ─────────────────────────────────────────
#  AUTH ROUTES
# ─────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if request.method == "GET":
        if "user_id" in session:
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    # POST
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data received."}), 400

    email    = data.get("email", "").strip()
    password = data.get("password", "").strip()

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password required."}), 400

    try:
        res     = supabase.auth.sign_in_with_password({"email": email, "password": password})
        user    = res.user
        profile = get_or_create_profile(str(user.id), user.email)

        session["user_id"]    = str(user.id)   # ← always string
        session["user_email"] = user.email
        session["user_name"]  = profile.get("full_name", "") if profile else ""
        session["user_plan"]  = profile.get("plan", "free") if profile else "free"

        return jsonify({"success": True, "redirect": "/dashboard"})

    except Exception as e:
        err = str(e)
        print("Login error:", err)
        if "invalid" in err.lower() or "credentials" in err.lower():
            return jsonify({"success": False, "error": "Invalid email or password."}), 401
        return jsonify({"success": False, "error": "Login failed. Please try again."}), 500


@app.route("/signup", methods=["GET", "POST"])
@limiter.limit("6 per minute", methods=["POST"])
def signup():
    if request.method == "GET":
        if "user_id" in session:
            return redirect(url_for("dashboard"))
        return render_template("signup.html")

    # POST
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data received."}), 400

    email    = data.get("email", "").strip()
    password = data.get("password", "").strip()
    name     = data.get("name", "").strip()

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password required."}), 400
    if len(password) < 8:
        return jsonify({"success": False, "error": "Password must be at least 8 characters."}), 400
    if not any(c.isupper() for c in password) or not any(c.isdigit() for c in password):
        return jsonify({"success": False, "error": "Password must contain uppercase letter and number."}), 400
    if len(email) > 254:
        return jsonify({"success": False, "error": "Email too long."}), 400
    if len(name) > 100:
        return jsonify({"success": False, "error": "Name too long."}), 400

    try:
        res  = supabase.auth.sign_up({"email": email, "password": password})
        user = res.user

        if not user:
            return jsonify({"success": False,
                            "error": "Account created! Check your email to confirm."}), 200

        supabase.table("profiles").insert({
            "id":              str(user.id),   # ← always string
            "email":           email,
            "full_name":       name,
            "plan":            "free",
            "emails_today":    0,
            "last_reset_date": str(date.today()),
        }).execute()

        session["user_id"]    = str(user.id)   # ← always string
        session["user_email"] = email
        session["user_name"]  = name
        session["user_plan"]  = "free"

        return jsonify({"success": True, "redirect": "/dashboard"})

    except Exception as e:
        err = str(e)
        if "already" in err.lower() or "registered" in err.lower():
            return jsonify({"success": False,
                            "error": "Email already registered. Try logging in."}), 409
        print("Signup error:", err)
        return jsonify({"success": False, "error": "Signup failed. Please try again."}), 500

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ─────────────────────────────────────────
#  MAIN ROUTES (protected)
# ─────────────────────────────────────────

@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
@login_required
def dashboard():
    user  = get_current_user()
    usage = get_usage_today(user["id"])
    return render_template("dashboard.html", user=user, usage=usage,
                           daily_limit=DAILY_LIMIT)


@app.route("/generate", methods=["GET"])
@login_required
def generate_page():
    user  = get_current_user()
    usage = get_usage_today(user["id"])
    return render_template("index.html", user=user, usage=usage,
                           daily_limit=DAILY_LIMIT)


@app.route("/generate", methods=["POST"])
@login_required
@limiter.limit("8 per minute")
def generate():
    try:
        user    = get_current_user()
        user_id = user["id"]
        usage   = get_usage_today(user_id)

        if usage >= DAILY_LIMIT:
            return jsonify({"success": False,
                            "error": "Daily limit reached. Upgrade to Pro."}), 429

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data received"}), 400

        required = ["sender_name", "offering", "prospect_name", "prospect_company"]
        missing  = [f for f in required if not data.get(f, "").strip()]
        if missing:
            return jsonify({"success": False,
                            "error": f"Missing: {', '.join(missing)}"}), 400
        
        # Validate input lengths to prevent abuse
        for field in required:
            val = data.get(field, "").strip()
            if len(val) > 500:
                return jsonify({"success": False, "error": f"{field} too long."}), 400

        completion = groq_client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": build_user_prompt(data)},
            ],
            temperature=0.6,
            max_tokens=800,
            top_p=0.9,
        )

        raw = completion.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw    = raw.strip()
        result = json.loads(raw)
        
        # Validate response structure
        if not isinstance(result, dict):
            raise ValueError("Invalid response format")
        if not result.get("cold_email") or not result.get("follow_up") or not result.get("linkedin_dm"):
            raise ValueError("Missing required email sections")
        if not result["cold_email"].get("subject") or not result["cold_email"].get("body"):
            raise ValueError("Invalid cold email structure")

        # Save to Supabase
        supabase.table("emails").insert({
            "user_id":          user_id,
            "prospect_name":    data.get("prospect_name"),
            "prospect_company": data.get("prospect_company"),
            "subject":          result["cold_email"]["subject"],
            "body":             result["cold_email"]["body"],
            "followup_subject": result["follow_up"]["subject"],
            "followup_body":    result["follow_up"]["body"],
            "linkedin_body":    result["linkedin_dm"]["body"],
            "tone":             data.get("tone"),
            "goal":             data.get("goal"),
            "personalization":  data.get("personalization"),
        }).execute()

        increment_usage(user_id)

        return jsonify({
            "success":          True,
            "subject":          result["cold_email"]["subject"],
            "body":             result["cold_email"]["body"],
            "followup_subject": result["follow_up"]["subject"],
            "followup_body":    result["follow_up"]["body"],
            "linkedin_body":    result["linkedin_dm"]["body"],
            "tone":             data.get("tone", "Professional"),
            "goal":             data.get("goal", "Get a Reply"),
            "personalization":  data.get("personalization", "Standard"),
            "prospect_name":    data.get("prospect_name", ""),
            "prospect_company": data.get("prospect_company", ""),
            "usage":            usage + 1,
            "daily_limit":      DAILY_LIMIT,
        })

    except json.JSONDecodeError:
        return jsonify({"success": False,
                        "error": "AI returned malformed output. Try again."}), 500
    except Exception as e:
        err = str(e)
        print("Generate error:", err)
        if "rate_limit" in err.lower():
            return jsonify({"success": False,
                            "error": "Rate limit reached. Please wait."}), 429
        return jsonify({"success": False,
                        "error": "Something went wrong. Please try again."}), 500


@app.route("/api/history")
@login_required
def api_history():
    """Returns user's email history as JSON for dashboard."""
    try:
        user_id = session["user_id"]
        res = supabase.table("emails").select("*").eq(
            "user_id", user_id
        ).order("created_at", desc=True).limit(50).execute()
        return jsonify({"success": True, "emails": res.data})
    except Exception as e:
        print("History error:", e)
        return jsonify({"success": False, "emails": []}), 500


@app.route("/api/usage")
@login_required
def api_usage():
    """Returns today's usage count."""
    usage = get_usage_today(session["user_id"])
    return jsonify({"usage": usage, "daily_limit": DAILY_LIMIT})


@app.route("/.well-known/appspecific/com.chrome.devtools.json")
def chrome_devtools():
    return jsonify({}), 200

# ── Google OAuth ───────────────────────────────────
@app.route("/auth/google")
@limiter.limit("20 per minute")
def auth_google():
    try:
        redirect_url = os.environ.get("OAUTH_REDIRECT_URL", "http://127.0.0.1:5000/auth/callback")
        res = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": redirect_url
            }
        })
        return redirect(res.url)
    except Exception as e:
        print("Google auth error:", e)
        return redirect('/login?error=google_failed')

@app.route("/auth/callback")
@limiter.limit("20 per minute")
def auth_callback():
    code = request.args.get("code")
    
    if not code:
        return redirect("/login?error=no_token")

    try:
        res  = supabase.auth.exchange_code_for_session({"auth_code": code})
        user = res.user

        if not user:
            return redirect("/login?error=auth_failed")

        profile = get_or_create_profile(str(user.id), user.email)

        # Get name from Google metadata
        google_name = ""
        if hasattr(user, 'user_metadata') and user.user_metadata:
            google_name = (user.user_metadata.get("full_name") or
                          user.user_metadata.get("name") or "")

        session["user_id"]    = str(user.id)
        session["user_email"] = user.email
        session["user_name"]  = (profile.get("full_name", "") if profile else "") or google_name
        session["user_plan"]  = profile.get("plan", "free") if profile else "free"

        # Save Google name to profile if missing
        if profile and not profile.get("full_name") and google_name:
            supabase.table("profiles").update({
                "full_name": google_name
            }).eq("id", str(user.id)).execute()
            session["user_name"] = google_name

        return redirect("/dashboard")

    except Exception as e:
        print("OAuth callback error:", e)
        return redirect("/login?error=auth_failed")

# ── Forgot Password ────────────────────────────────
@app.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("forgot_password.html")

    # POST
    data  = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Email is required."}), 400
    email = data.get("email", "").strip()

    if not email:
        return jsonify({"success": False, "error": "Email is required."}), 400

    try:
        supabase.auth.reset_password_for_email(
            email,
            options={"redirect_to": request.host_url.rstrip('/') + '/reset-password'}
        )
        # Always return success — don't reveal if email exists
        return jsonify({"success": True})
    except Exception as e:
        print("Forgot password error:", e)
        return jsonify({"success": True})  # Still return success for security


@app.route("/reset-password", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def reset_password():
    if request.method == "GET":
        code = request.args.get("code")
        if code:
            try:
                res = supabase.auth.exchange_code_for_session({"auth_code": code})
                session_obj = getattr(res, "session", None)
                if session_obj:
                    session["reset_access_token"] = getattr(session_obj, "access_token", "")
                    session["reset_refresh_token"] = getattr(session_obj, "refresh_token", "")
            except Exception as e:
                print("Password reset session error:", e)
                return render_template("reset_password.html", reset_ready=False)
        return render_template("reset_password.html", reset_ready=bool(session.get("reset_access_token")))

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data received."}), 400

    new_password = data.get("password", "").strip()
    if len(new_password) < 8:
        return jsonify({"success": False, "error": "Password must be at least 8 characters."}), 400
    if not any(c.isupper() for c in new_password) or not any(c.isdigit() for c in new_password):
        return jsonify({"success": False, "error": "Password must contain uppercase letter and number."}), 400

    access_token = session.get("reset_access_token")
    refresh_token = session.get("reset_refresh_token")
    if not access_token or not refresh_token:
        return jsonify({"success": False, "error": "Reset link expired. Request a new link."}), 400

    try:
        supabase.auth.set_session(access_token, refresh_token)
        supabase.auth.update_user({"password": new_password})
        session.pop("reset_access_token", None)
        session.pop("reset_refresh_token", None)
        return jsonify({"success": True, "redirect": "/login"})
    except Exception as e:
        print("Password reset error:", e)
        return jsonify({"success": False, "error": "Password reset failed. Request a new link."}), 500

# Placeholder routes
@app.route("/history")
@login_required
def history():
    user  = get_current_user()
    usage = get_usage_today(user["id"])
    return render_template("history.html", user=user, usage=usage, daily_limit=DAILY_LIMIT)


@app.route("/templates")
@login_required
def templates():
    user  = get_current_user()
    usage = get_usage_today(user["id"])
    return render_template("templates.html", user=user, usage=usage, daily_limit=DAILY_LIMIT)


@app.route("/settings")
@login_required
def settings():
    user  = get_current_user()
    usage = get_usage_today(user["id"])
    return render_template("settings.html", user=user, usage=usage, daily_limit=DAILY_LIMIT)


@app.route("/api/profile", methods=["POST"])
@login_required
@limiter.limit("12 per minute")
def update_profile():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data received."}), 400
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"success": False, "error": "Name is required."}), 400
    try:
        supabase.table("profiles").update({
            "full_name": name
        }).eq("id", session["user_id"]).execute()
        session["user_name"] = name
        return jsonify({"success": True})
    except Exception as e:
        print("Profile update error:", e)
        return jsonify({"success": False, "error": "Update failed."}), 500


@app.route("/api/change-password", methods=["POST"])
@login_required
@limiter.limit("5 per minute")
def change_password():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data received."}), 400
    new_password = data.get("password", "").strip()
    if len(new_password) < 8:
        return jsonify({"success": False, "error": "Password must be at least 8 characters."}), 400
    if not any(c.isupper() for c in new_password) or not any(c.isdigit() for c in new_password):
        return jsonify({"success": False, "error": "Password must contain uppercase letter and number."}), 400
    try:
        supabase.auth.update_user({"password": new_password})
        return jsonify({"success": True})
    except Exception as e:
        print("Password change error:", e)
        return jsonify({"success": False, "error": "Password change failed."}), 500
    
@app.route("/pricing")
@login_required
def pricing():
    user  = get_current_user()
    usage = get_usage_today(user["id"])
    return render_template("pricing.html", user=user, usage=usage, daily_limit=DAILY_LIMIT)

if __name__ == "__main__":
    app.run(debug=True)
