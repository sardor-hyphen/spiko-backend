# ==============================================================================
# Spiko - Main Flask Application (DEFINITIVE, SELF-SEEDING VERSION)
#
# This version includes a one-time database seeding mechanism to ensure that
# the application has sample data on its first run, guaranteeing that the
# progress page displays a fully populated dashboard immediately.
# ==============================================================================

import os
import json
import requests
import datetime
import jwt
from flask import Flask, request, jsonify, abort
from functools import wraps
from dotenv import load_dotenv
from flask_cors import CORS

from models import db, bcrypt, User, SessionUsage, FeedbackSummary
from auth import register_user, login_user, get_current_user, update_user_profile, update_user_password, delete_user_account
from analytics import log_session, get_user_analytics, get_platform_summary, get_popular_sessions
from geo_check import geo_bp

load_dotenv()
app = Flask(__name__)
# Allow all origins for development - more permissive CORS
CORS(app, resources={r"/*": {"origins": "*"}})

# Load API keys
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Register the geo check blueprint
app.register_blueprint(geo_bp)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///spiko.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'spiko-secret-key-for-jwt-tokens-2024')

db.init_app(app)
bcrypt.init_app(app)

# --- NEW: DATABASE SEEDING LOGIC ---
def seed_database():
    """
    Checks if the database is empty and, if so, populates it with
    a default user and a set of realistic, sample session data.
    This function runs only once.
    """
    print("Checking if database needs seeding...")
    if User.query.first() is None:
        print("Database is empty. Seeding with default data...")
        
        # 1. Create a default user
        default_user = User(username="SpikoUser", email="user@spiko.ai", password="password123")
        db.session.add(default_user)
        db.session.commit() # Commit to get the user ID
        
        # 2. Create sample session data
        today = datetime.datetime.utcnow()
        days_ago = lambda days: today - datetime.timedelta(days=days)
        
        mock_sessions_data = [
            {"session_id_str": "session_1", "date": days_ago(20), "scores": {"fluency_coherence": 6.0, "lexical_resource": 6.5, "grammatical_range_accuracy": 5.5, "pronunciation": 6.0}, "overall_score": 6.0},
            {"session_id_str": "session_2", "date": days_ago(15), "scores": {"fluency_coherence": 6.5, "lexical_resource": 6.0, "grammatical_range_accuracy": 6.0, "pronunciation": 6.5}, "overall_score": 6.5},
            {"session_id_str": "session_3", "date": days_ago(10), "scores": {"fluency_coherence": 7.0, "lexical_resource": 6.5, "grammatical_range_accuracy": 6.0, "pronunciation": 6.5}, "overall_score": 6.5},
            {"session_id_str": "session_4", "date": days_ago(5), "scores": {"fluency_coherence": 7.0, "lexical_resource": 7.0, "grammatical_range_accuracy": 6.5, "pronunciation": 7.0}, "overall_score": 7.0},
            {"session_id_str": "session_1", "date": days_ago(1), "scores": {"fluency_coherence": 7.5, "lexical_resource": 7.5, "grammatical_range_accuracy": 7.0, "pronunciation": 7.5}, "overall_score": 7.5}
        ]
        
        for data in mock_sessions_data:
            session_usage = SessionUsage(
                user_id=default_user.id,
                session_id_str=data["session_id_str"],
                duration=900,
                words_spoken=150,
                date=data["date"]
            )
            
            # Add overall score to the band_scores object for consistency
            band_scores_with_overall = data["scores"].copy()
            band_scores_with_overall['overall_band'] = {"score": data["overall_score"]}

            feedback = FeedbackSummary(
                session=session_usage,
                band_scores=json.dumps(band_scores_with_overall),
                feedback_text=json.dumps({"feedback_summary": [{"type": "good", "message": "Sample feedback."}]})
            )
            db.session.add(session_usage)
            db.session.add(feedback)
            
        db.session.commit()
        print("Database seeding complete.")
    else:
        print("Database already contains data. Skipping seed.")


# Create tables and run the seeder within the application context
with app.app_context():
    db.create_all()
    seed_database()


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY: raise ValueError("FATAL: OPENROUTER_API_KEY not found.")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
AI_MODEL = "mistralai/mistral-7b-instruct:free"
SESSION_DATA_PATH = os.path.join(os.path.dirname(__file__), 'session-data')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get the Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing or invalid authorization header"}), 401

        # Extract the token
        token = auth_header.split(' ')[1]

        try:
            # Decode the JWT token to get the user_id
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            user_id = payload.get('user_id')

            if not user_id:
                return jsonify({"error": "Invalid token payload"}), 401

            # Verify the user exists
            from models import User
            user = User.query.get(user_id)
            if not user:
                return jsonify({"error": "User not found"}), 401

            # Pass the actual user_id to the decorated function
            kwargs['user_id'] = user_id
            return f(*args, **kwargs)

        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        except Exception as e:
            print(f"Token validation error: {e}")
            return jsonify({"error": "Token validation failed"}), 401

    return decorated_function

# --- API Endpoints ---

@app.route('/api/register', methods=['POST'])
def handle_register(): return register_user()

@app.route('/api/login', methods=['POST'])
def handle_login(): return login_user()

@app.route('/api/me', methods=['GET'])
@login_required
def handle_me(user_id): return get_current_user(user_id)

@app.route('/api/me', methods=['PUT'])
@login_required
def handle_update_profile(user_id): return update_user_profile(user_id)

@app.route('/api/me/password', methods=['PUT'])
@login_required
def handle_update_password(user_id): return update_user_password(user_id)

@app.route('/api/me', methods=['DELETE'])
@login_required
def handle_delete_account(user_id): return delete_user_account(user_id)

@app.route('/api/sessions', methods=['GET'])
def get_all_sessions():
    sessions = []
    if not os.path.exists(SESSION_DATA_PATH): return jsonify({"error": "Server configuration error"}), 500
    try:
        for filename in os.listdir(SESSION_DATA_PATH):
            if filename.endswith('.json'):
                filepath = os.path.join(SESSION_DATA_PATH, filename)
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    sessions.append({ "id": data.get("session_id"), "title": data.get("title"), "keywords": data.get("keywords") })
    except Exception as e:
        print(f"ERROR reading session files: {e}")
        return jsonify({"error": "Server error"}), 500
    return jsonify(sessions)

@app.route('/api/sessions/<session_id>', methods=['GET'])
def get_single_session(session_id):
    filepath = os.path.join(SESSION_DATA_PATH, f"{session_id}.json")
    if not os.path.exists(filepath): return jsonify({"error": "Session not found"}), 404
    try:
        with open(filepath, 'r') as f: return jsonify(json.load(f))
    except Exception: return jsonify({"error": "Could not read session file"}), 500

@app.route('/api/analyze', methods=['POST'])
@login_required
def analyze_speech(user_id):
    data = request.get_json()
    print(f"ANALYZE_SPEECH: Received data keys: {list(data.keys()) if data else 'None'}")

    if not data or 'transcript' not in data: return jsonify({"error": "Missing transcript"}), 400

    transcript = data.get('transcript')
    session_id_str = data.get('session_id', 'unknown_session')
    questions_and_answers = data.get('questions_and_answers', [])

    print(f"ANALYZE_SPEECH: Transcript length: {len(transcript)} characters")
    print(f"ANALYZE_SPEECH: Session ID: {session_id_str}")
    print(f"ANALYZE_SPEECH: Questions and answers count: {len(questions_and_answers)}")
    print(f"ANALYZE_SPEECH: Transcript preview: {transcript[:200]}...")

    if not transcript.strip(): return jsonify({"error": "Transcript cannot be empty."}), 400

    prompt = f"""
    You are an expert, impartial, and highly-trained IELTS Speaking examiner. Your task is to evaluate the given transcript of a candidate's spoken response in an IELTS Speaking test.

    Your evaluation should cover: fluency and coherence, lexical resource, grammatical range and accuracy, and pronunciation.

    For each criterion, assign a band score from 0 to 9 with one decimal place precision.

    CRITICAL INSTRUCTIONS FOR DIVERSE, CONTEXTUAL FEEDBACK:
    1. Analyze the transcript word by word and identify specific grammar mistakes and vocabulary improvements
    2. For each issue found, provide the exact word position (counting from 0) in the transcript
    3. MOST IMPORTANT: Each correction must be UNIQUE and CONTEXTUAL. Never repeat the same correction or reason
    4. For similar mistakes, provide DIFFERENT explanations, alternative corrections, and varied reasoning
    5. Consider the specific context, surrounding words, intended meaning, and sentence structure for each error
    6. Provide diverse vocabulary suggestions that fit the specific context and register
    7. Vary your explanations - use different grammatical terminology, examples, and teaching approaches
    8. If you find the same type of error multiple times, address each instance differently with unique solutions

    EXAMPLE OF DIVERSE CORRECTIONS FOR REPEATED MISTAKES:
    - First "I want" → "I'd like" (Reason: "Use contractions for more natural, conversational flow")
    - Second "I want" → "I would prefer" (Reason: "Vary your expressions to show lexical range")
    - Third "I want" → "I'm hoping to" (Reason: "Softer phrasing sounds more polite and sophisticated")

    Split the transcript into words using spaces, then identify issues by their position number.

    Example: For transcript "I am enjoying my work very much"
    Word positions: 0=I, 1=am, 2=enjoying, 3=my, 4=work, 5=very, 6=much

    Format your response as a JSON object:

    {{
        "criteria_scores": {{
            "fluency_coherence": 6.5,
            "lexical_resource": 6.0,
            "grammatical_range_accuracy": 6.0,
            "pronunciation": 6.5
        }},
        "overall_band": {{
            "score": 6.2,
            "summary": "The candidate demonstrates good overall speaking ability with room for improvement in specific areas."
        }},
        "word_analysis": {{
            "2": {{
                "type": "grammar",
                "original": "enjoying",
                "correction": "enjoy",
                "reason": "After 'am' use base form, not -ing form when expressing general preference"
            }},
            "4": {{
                "type": "vocabulary",
                "original": "work",
                "suggestion": "job",
                "reason": "More natural word choice in this context"
            }},
            "8": {{
                "type": "grammar",
                "original": "enjoying",
                "correction": "fond of",
                "reason": "Alternative structure: 'I am fond of' shows variety in expression patterns"
            }},
            "12": {{
                "type": "vocabulary",
                "original": "work",
                "suggestion": "profession",
                "reason": "Elevates register and demonstrates sophisticated vocabulary range"
            }}
        }},
        "actionable_insights": {{
            "feedback_summary": [
                {{
                    "type": "good",
                    "message": "You spoke clearly and maintained good fluency throughout the response."
                }},
                {{
                    "type": "warn",
                    "message": "Pay attention to verb forms after auxiliary verbs."
                }},
                {{
                    "type": "critique",
                    "message": "Try to use more varied and sophisticated vocabulary to improve your lexical resource score."
                }}
            ]
        }}
    }}

    Transcript to analyze (length: {len(transcript)} characters):
    \"\"\"{transcript}\"\"\"

    FINAL REMINDER: Provide DIVERSE, UNIQUE corrections for each error. Never repeat the same correction or reasoning. Each mistake should receive individual, contextual attention with varied explanations and different solution approaches. Focus on finding at least 2-3 grammar or vocabulary improvements if the text is longer than 20 words.
    """
    
    try:
        response = requests.post(
            url=OPENROUTER_API_URL,
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={"model": AI_MODEL, "messages": [{"role": "user", "content": prompt}]},
            timeout=90
        )
        response.raise_for_status()
        
        raw_response_text = response.json()['choices'][0]['message']['content']
        print(f"AI_RESPONSE: Raw response length: {len(raw_response_text)} characters")
        print(f"AI_RESPONSE: Response preview: {raw_response_text[:300]}...")

        try:
            start_index = raw_response_text.find('{')
            end_index = raw_response_text.rfind('}')
            if start_index == -1 or end_index == -1:
                raise json.JSONDecodeError("Could not find JSON object in AI response", raw_response_text, 0)

            json_str = raw_response_text[start_index:end_index+1]
            analysis_result = json.loads(json_str)

            print(f"AI_RESPONSE: Successfully parsed JSON with keys: {list(analysis_result.keys())}")
            if 'word_analysis' in analysis_result:
                word_analysis = analysis_result['word_analysis']
                print(f"AI_RESPONSE: Word analysis items: {len(word_analysis)}")
                for pos, analysis in word_analysis.items():
                    print(f"AI_RESPONSE: Position {pos}: {analysis['type']} - {analysis['original']}")

        except json.JSONDecodeError as e:
            print("="*50, "\nFATAL: FAILED TO PARSE AI JSON RESPONSE\n", f"Error: {e}\n", "--- RAW AI RESPONSE ---\n", raw_response_text, "\n", "="*50)
            raise

        session_usage_id = log_session(user_id=user_id, session_id_str=session_id_str, analysis_data=analysis_result, transcript=transcript, questions_and_answers=questions_and_answers)

        # Add session_usage_id to the response for frontend reference
        if session_usage_id:
            analysis_result['session_usage_id'] = session_usage_id
        
        return jsonify(analysis_result), 200

    except requests.exceptions.RequestException as e:
        print(f"ERROR: API request failed: {e}")
        return jsonify({"error": "Failed to connect to the AI analysis service."}), 503
    except Exception as e:
        print(f"ERROR: An unknown error occurred during analysis: {e}")
        return jsonify({"error": "An unexpected server error occurred during analysis."}), 500

@app.route('/api/analytics/user/<int:user_id>', methods=['GET'])
@login_required
def handle_user_analytics(user_id): return get_user_analytics(user_id)

@app.route('/api/analytics/session/<int:session_usage_id>', methods=['GET'])
@login_required
def handle_session_analytics(user_id, session_usage_id):
    from analytics import get_session_analytics
    return get_session_analytics(session_usage_id)

@app.route('/api/chat/session/<int:session_usage_id>', methods=['POST'])
@login_required
def chat_with_session_data(user_id, session_usage_id):
    """
    AI chatbot endpoint that provides contextual advice based on session analytics data
    """
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({"error": "Missing message"}), 400

    user_message = data.get('message')

    # Get the session analytics data for context
    from analytics import get_session_analytics_data
    session_data = get_session_analytics_data(session_usage_id)

    if not session_data:
        return jsonify({"error": "Session not found"}), 404

    # Create contextual prompt for the AI
    context_prompt = f"""
    You are an expert IELTS Speaking tutor. Provide helpful, encouraging advice based on this student's actual performance data.

    STUDENT'S PERFORMANCE:
    - Overall Band Score: {session_data.get('overall_band', {}).get('score', 'N/A')}
    - Fluency & Coherence: {session_data.get('criteria_scores', {}).get('fluency_coherence', 'N/A')}
    - Lexical Resource: {session_data.get('criteria_scores', {}).get('lexical_resource', 'N/A')}
    - Grammar & Accuracy: {session_data.get('criteria_scores', {}).get('grammatical_range_accuracy', 'N/A')}
    - Pronunciation: {session_data.get('criteria_scores', {}).get('pronunciation', 'N/A')}

    SPECIFIC CORRECTIONS MADE:
    {chr(10).join([f"- {analysis.get('original', '')} → {analysis.get('correction', analysis.get('suggestion', ''))}: {analysis.get('reason', '')}" for analysis in session_data.get('word_analysis', {}).values()])}

    GUIDELINES:
    - Be encouraging but honest about areas for improvement
    - Reference specific examples from their performance when possible
    - Provide actionable, practical advice
    - Keep responses concise (2-3 paragraphs max)
    - Use a friendly, professional tone

    Student's question: "{user_message}"

    Response:"""

    try:
        # Call OpenRouter API (same as analysis endpoint)
        response = requests.post(
            url=OPENROUTER_API_URL,
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": AI_MODEL,
                "messages": [{"role": "user", "content": context_prompt}],
                "max_tokens": 500,
                "temperature": 0.7
            },
            timeout=30
        )

        if not response.ok:
            print(f"CHAT_ERROR: OpenRouter API error: {response.status_code} - {response.text}")
            return jsonify({"error": "Failed to get AI response"}), 500

        ai_response = response.json()['choices'][0]['message']['content']

        return jsonify({
            "response": ai_response,
            "session_id": session_usage_id
        })

    except Exception as e:
        print(f"CHAT_ERROR: {str(e)}")
        return jsonify({"error": "Failed to process chat request"}), 500

@app.route('/api/analytics/summary', methods=['GET'])
def handle_platform_summary(): return get_platform_summary()

@app.route('/api/analytics/popular', methods=['GET'])
def handle_popular_sessions(): return get_popular_sessions()

import os
import requests
from flask import abort

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_USERNAME = os.getenv("TELEGRAM_CHANNEL_USERNAME")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_USERNAME:
    print("WARNING: Telegram bot token or channel username not set in environment variables.")

# Remove duplicate route definition to fix AssertionError
# The function check_telegram_subscription_endpoint is already defined above

# If there is a duplicate definition below, remove or comment it out

# @app.route('/api/check_telegram_subscription', methods=['GET'])
# @login_required
# def check_telegram_subscription_endpoint(user_id):
#     # duplicate function removed to avoid conflict

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_USERNAME = os.getenv("TELEGRAM_CHANNEL_USERNAME")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_USERNAME:
    print("WARNING: Telegram bot token or channel username not set in environment variables.")

@app.route('/api/check_telegram_subscription', methods=['GET'])
@login_required
def check_telegram_subscription_endpoint(user_id):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_USERNAME:
        return {"error": "Telegram bot token or channel username not configured."}, 500

    # Get Telegram user ID from query parameter or user profile (for demo, assume user_id maps to telegram_user_id)
    telegram_user_id = request.args.get('telegram_user_id')
    if not telegram_user_id:
        return {"error": "Missing telegram_user_id parameter."}, 400

    # Telegram API endpoint to get chat member status
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getChatMember"
    params = {
        "chat_id": TELEGRAM_CHANNEL_USERNAME,
        "user_id": telegram_user_id
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data.get("ok"):
            return {"subscribed": False}

        status = data.get("result", {}).get("status", "")
        # Consider these statuses as subscribed
        subscribed_statuses = ["member", "creator", "administrator"]
        is_subscribed = status in subscribed_statuses

        return {"subscribed": is_subscribed}

    except requests.RequestException as e:
        print(f"Error checking Telegram subscription: {e}")
        return {"error": "Failed to check subscription status."}, 500

# Add health check endpoint for Railway
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "service": "spiko-backend"}), 200

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)

