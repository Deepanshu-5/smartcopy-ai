from flask import Flask, render_template, request, jsonify, redirect
from dotenv import load_dotenv
import os

load_dotenv()
app = Flask(__name__)

# ── Page routes ───────────────────────────────────────
@app.route('/')
def home():
    return redirect('/dashboard')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/generate', methods=['GET', 'POST'])
def generate():
    if request.method == 'GET':
        return render_template('index.html')

    # POST — email generation (Phase 3: replace with Groq/Claude)
    try:
        data             = request.get_json()
        sender_name      = data.get('sender_name', '')
        sender_company   = data.get('sender_company', '')
        prospect_name    = data.get('prospect_name', '')
        prospect_co      = data.get('prospect_company', '')
        offering         = data.get('offering', '')
        tone             = data.get('tone', 'Professional')
        goal             = data.get('goal', 'Book a Call')
        personalization  = data.get('personalization', 'Quick')

        subject = f"Quick question about {prospect_co}'s growth"
        body = (
            f"Hi {prospect_name},\n\n"
            f"I came across {prospect_co} and was genuinely impressed by what you're building.\n\n"
            f"At {sender_company or 'my company'}, I specialise in {offering}. "
            f"I believe there's a real opportunity to help your team get better results without extra overhead.\n\n"
            f"Would you be open to a quick 15-minute call this week to explore if it's a fit?\n\n"
            f"Best,\n{sender_name}"
        )

        return jsonify({
            'success': True,
            'subject': subject,
            'body': body,
            'tone': tone,
            'goal': goal,
            'personalization': personalization,
            'prospect_name': prospect_name,
            'prospect_company': prospect_co,
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Placeholder routes for future pages ──────────────
@app.route('/campaigns')
def campaigns():
    return render_template('dashboard.html')   # temp until built

@app.route('/analytics')
def analytics():
    return render_template('dashboard.html')   # temp until built

@app.route('/templates')
def templates():
    return render_template('dashboard.html')   # temp until built

@app.route('/history')
def history():
    return render_template('dashboard.html')   # temp until built

@app.route('/settings')
def settings():
    return render_template('dashboard.html')   # temp until built


if __name__ == '__main__':
    app.run(debug=True, port=5000)