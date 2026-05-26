import os
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

app = Flask(__name__)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.1-8b-instant"

# ─────────────────────────────────────────
#  PROMPT ENGINEERING SYSTEM (SECRET SAUCE)
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
  "cold_email": {
    "subject": "...",
    "body": "..."
  },
  "follow_up": {
    "subject": "...",
    "body": "..."
  },
  "linkedin_dm": {
    "body": "..."
  }
}"""


def build_personalization_context(data):
    """Build context block based on personalization depth."""
    level = data.get("personalization", "Standard")
    prospect = data.get("prospect_name", "there")
    company = data.get("prospect_company", "their company")

    if level == "Quick":
        return f"Target: {prospect} at {company}. Keep it brief and punchy."

    elif level == "Standard":
        return (
            f"Target: {prospect}, works at {company}. "
            f"Reference their company naturally — one specific, believable detail. "
            f"Don't make up specifics you don't know. Keep it focused."
        )

    elif level == "Deep":
        return (
            f"Target: {prospect}, works at {company}. "
            f"This is a hyper-personalized outreach. Open with something that shows you "
            f"actually looked at {company} — reference their likely growth stage, industry "
            f"challenge, or a reasonable assumption about their business. "
            f"Make {prospect} feel like this was written only for them. "
            f"Every sentence must earn its place."
        )

    return ""


def build_tone_instruction(tone):
    """Map tone pill to writing style instruction."""
    tones = {
        "Professional": (
            "Tone: Professional and polished. Confident without being arrogant. "
            "No slang. Sentences are clean and purposeful."
        ),
        "Friendly": (
            "Tone: Warm and approachable. Write like you're emailing someone you "
            "admire — respectful but not stiff. Light, human energy."
        ),
        "Direct": (
            "Tone: Blunt and efficient. No pleasantries. Get to the point in the "
            "first sentence. Respect their time aggressively."
        ),
        "Casual": (
            "Tone: Conversational and relaxed. Write like a peer, not a vendor. "
            "Contractions are fine. Short punchy sentences."
        ),
    }
    return tones.get(tone, tones["Professional"])


def build_goal_instruction(goal):
    """Map goal to a specific CTA instruction."""
    goals = {
        "Book a Call": (
            "CTA: Ask for a specific short call (15–20 min). Suggest they pick a time "
            "or reply with availability. One ask only."
        ),
        "Get a Reply": (
            "CTA: End with a single, easy yes/no or one-word question that makes "
            "replying feel effortless. Low friction."
        ),
        "Demo Request": (
            "CTA: Ask if they'd like to see it in action. Frame the demo as a "
            "quick, no-pressure look — not a sales call."
        ),
        "Share Resource": (
            "CTA: Offer to send a specific resource (case study, audit, guide). "
            "Ask if it's relevant before dumping a link."
        ),
    }
    return goals.get(goal, goals["Get a Reply"])


def build_sender_context(data):
    """Build sender identity block."""
    name = data.get("sender_name", "")
    company = data.get("sender_company", "")
    offering = data.get("offering", "")
    experience = data.get("experience", "Intermediate")
    portfolio = data.get("portfolio", "")

    company_line = f" at {company}" if company else ""
    portfolio_line = f"\nPortfolio/proof: {portfolio}" if portfolio else ""
    exp_map = {
        "Beginner": "newer but hungry — don't oversell experience, let the offer speak",
        "Intermediate": "solid track record — reference results or process confidence",
        "Expert": "seasoned pro — write with quiet authority, results speak",
    }
    exp_note = exp_map.get(experience, "")

    return (
        f"Sender: {name}{company_line}\n"
        f"What they offer: {offering}\n"
        f"Experience framing: {exp_note}"
        f"{portfolio_line}"
    )


def build_user_prompt(data):
    """Assemble the full user prompt from form data."""
    sender_ctx = build_sender_context(data)
    person_ctx = build_personalization_context(data)
    tone_instr = build_tone_instruction(data.get("tone", "Professional"))
    goal_instr = build_goal_instruction(data.get("goal", "Get a Reply"))

    prompt = f"""
{sender_ctx}

{person_ctx}

{tone_instr}

{goal_instr}

ADDITIONAL RULES:
- Cold email body: 80–130 words max
- Follow-up body: 50–80 words — reference that you emailed before, stay light
- LinkedIn DM: 40–60 words — even more casual, no subject line needed
- All three must feel like they come from the same person but suit their medium
- Sign off with just the sender's first name (no "Best regards", no "Sincerely")

Generate all three now. Return ONLY the JSON object.
"""
    return prompt.strip()


# ─────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────

@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/generate", methods=["GET"])
def generate_page():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    print("--- /generate hit ---")
    try:
        data = request.get_json()
        print("DATA RECEIVED:", data)

        if not data:
            return jsonify({"success": False, "error": "No data received"}), 400

        required = ["sender_name", "offering", "prospect_name", "prospect_company"]
        missing = [f for f in required if not data.get(f, "").strip()]
        if missing:
            return jsonify({
                "success": False,
                "error": f"Missing required fields: {', '.join(missing)}"
            }), 400

        print("API KEY LOADED:", bool(os.environ.get("GROQ_API_KEY")))

        user_prompt = build_user_prompt(data)
        print("PROMPT BUILT OK")

        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.75,
            max_tokens=1200,
            top_p=0.9,
        )
        print("GROQ RESPONSE OK")

        raw = completion.choices[0].message.content.strip()
        print("RAW:", raw[:200])

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)
        print("JSON PARSED OK")

        return jsonify({
            "success": True,
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
        })

    except json.JSONDecodeError:
        print("JSON DECODE ERROR — RAW WAS:", raw)
        return jsonify({"success": False, "error": "AI returned malformed output. Please try again."}), 500

    except Exception as e:
        import traceback
        traceback.print_exc()          # prints full stack trace
        print("EXCEPTION:", str(e))
        err = str(e)
        if "rate_limit" in err.lower():
            return jsonify({"success": False, "error": "Rate limit reached. Please wait and try again."}), 429
        return jsonify({"success": False, "error": "Something went wrong. Please try again."}), 500


# Placeholder routes — redirect to dashboard for now
for route in ["/campaigns", "/analytics", "/templates", "/history", "/settings"]:
    def make_redirect(r):
        return lambda: redirect(url_for("dashboard"))
    
    app.add_url_rule(
        route,
        endpoint=route.strip("/"),
        view_func=make_redirect(route)
    )

if __name__ == "__main__":
    app.run(debug=True)