import os
import json
from datetime import date
from functools import wraps
from flask import (Flask, render_template, request, jsonify,
                   redirect, url_for, session)
from dotenv import load_dotenv
from groq import Groq
from supabase import create_client, Client

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

# ── Clients ────────────────────────────────────────
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.1-8b-instant"

supabase: Client = create_client(
    os.environ.get("SUPABASE_URL"),
    os.environ.get("SUPABASE_ANON_KEY")
)

DAILY_LIMIT = 5

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
        res = supabase.table("profiles").select("*").eq("id", user_id).execute()
        if res.data:
            return res.data[0]
        # First login — create profile
        new_profile = {
            "id":               user_id,
            "email":            email,
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

SYSTEM_PROMPT = """You are an elite cold email copywriter with 10+ years of experience writing 
emails that actually get replies. You write like a real human — confident, warm, and specific. 

RULES YOU NEVER BREAK:
- Never use "I hope this email finds you well" or any variation
- Never use "I wanted to reach out" — just reach out
- Never use "synergy", "leverage", "game-changer", "revolutionary", "cutting-edge"
- Never open with "My name is..." — the prospect can see that
- No fluff, no filler sentences
- Keep subject lines under 9 words — curiosity-driven, not clickbait
- First line must hook immediately — reference something real or ask a sharp question
- CTA must be ONE clear ask, not multiple options
- Sound like a smart human wrote this at 11am on a Tuesday, not a bot

OUTPUT FORMAT: You must return ONLY valid JSON, no markdown, no explanation. 
Exactly this structure:
{
  "cold_email": { "subject": "...", "body": "..." },
  "follow_up":  { "subject": "...", "body": "..." },
  "linkedin_dm": { "body": "..." }
}"""


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
def login():
    if request.method == "GET":
        if "user_id" in session:
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    # POST
    data     = request.get_json()
    email    = data.get("email", "").strip()
    password = data.get("password", "").strip()

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password required."}), 400

    try:
        res     = supabase.auth.sign_in_with_password({"email": email, "password": password})
        user    = res.user
        profile = get_or_create_profile(user.id, user.email)

        session["user_id"]    = user.id
        session["user_email"] = user.email
        session["user_name"]  = profile.get("full_name", "") if profile else ""
        session["user_plan"]  = profile.get("plan", "free") if profile else "free"

        return jsonify({"success": True, "redirect": "/dashboard"})

    except Exception as e:
        err = str(e)
        if "invalid" in err.lower() or "credentials" in err.lower():
            return jsonify({"success": False, "error": "Invalid email or password."}), 401
        return jsonify({"success": False, "error": "Login failed. Please try again."}), 500


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        if "user_id" in session:
            return redirect(url_for("dashboard"))
        return render_template("signup.html")

    # POST
    data     = request.get_json()
    email    = data.get("email", "").strip()
    password = data.get("password", "").strip()
    name     = data.get("name", "").strip()

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password required."}), 400
    if len(password) < 6:
        return jsonify({"success": False, "error": "Password must be at least 6 characters."}), 400

    try:
        res  = supabase.auth.sign_up({"email": email, "password": password})
        user = res.user

        if not user:
            return jsonify({"success": False,
                            "error": "Account created! Check your email to confirm."}), 200

        supabase.table("profiles").insert({
            "id":              user.id,
            "email":           email,
            "full_name":       name,
            "plan":            "free",
            "emails_today":    0,
            "last_reset_date": str(date.today()),
        }).execute()

        session["user_id"]    = user.id
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

        completion = groq_client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": build_user_prompt(data)},
            ],
            temperature=0.75,
            max_tokens=1200,
            top_p=0.9,
        )

        raw = completion.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw    = raw.strip()
        result = json.loads(raw)

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


# Placeholder routes
for route in ["/campaigns", "/analytics", "/templates", "/history", "/settings"]:
    def make_redirect(r):
        return lambda: redirect(url_for("dashboard"))
    app.add_url_rule(route, endpoint=route.strip("/"), view_func=make_redirect(route))


if __name__ == "__main__":
    app.run(debug=True)