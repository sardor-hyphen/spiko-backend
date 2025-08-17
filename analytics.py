# ==============================================================================
# Spiko - Analytics Module
#
# This file contains the logic for saving session data to the database
# and for querying analytics data to be served by the API.
# ==============================================================================

import json
from flask import jsonify
from sqlalchemy import func

# --- Import shared extensions and models ---
from models import db, User, SessionUsage, FeedbackSummary

# ==============================================================================
# --- Data Logging Logic ---
# ==============================================================================

def calculate_session_metrics(transcript, start_time=None, end_time=None):
    """
    Calculate session metrics from transcript and timing data.

    Args:
        transcript: The spoken text transcript
        start_time: Optional session start timestamp
        end_time: Optional session end timestamp

    Returns:
        dict: Dictionary containing calculated metrics
    """
    if not transcript:
        return {"words_spoken": 0, "duration": 0, "wpm": 0}

    words = transcript.split()
    words_spoken = len(words)

    # Calculate duration if timestamps provided
    duration = 0
    if start_time and end_time:
        try:
            from datetime import datetime
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            duration = (end_time - start_time).total_seconds()
        except Exception as e:
            print(f"Error calculating duration: {e}")
            duration = 0

    # Calculate words per minute
    wpm = 0
    if duration > 0:
        wpm = (words_spoken / duration) * 60

    return {
        "words_spoken": words_spoken,
        "duration": max(duration, 0),
        "wpm": round(wpm, 2)
    }


def validate_analysis_data(analysis_data):
    """
    Validates the structure of AI analysis data before saving to database.

    Args:
        analysis_data: Dictionary containing AI analysis results

    Returns:
        tuple: (is_valid, error_message)
    """
    if not isinstance(analysis_data, dict):
        return False, "Analysis data must be a dictionary"

    # Check for required fields
    required_fields = ['criteria_scores', 'overall_band', 'actionable_insights']
    for field in required_fields:
        if field not in analysis_data:
            return False, f"Missing required field: {field}"

    # Validate criteria scores
    criteria_scores = analysis_data.get('criteria_scores', {})
    expected_criteria = ['fluency_coherence', 'lexical_resource', 'grammatical_range_accuracy', 'pronunciation']
    for criterion in expected_criteria:
        if criterion not in criteria_scores:
            return False, f"Missing criterion score: {criterion}"

        score = criteria_scores[criterion]
        if not isinstance(score, (int, float)) or score < 0 or score > 9:
            return False, f"Invalid score for {criterion}: must be a number between 0 and 9"

    # Validate overall band
    overall_band = analysis_data.get('overall_band', {})
    if 'score' not in overall_band:
        return False, "Missing overall band score"

    overall_score = overall_band['score']
    if not isinstance(overall_score, (int, float)) or overall_score < 0 or overall_score > 9:
        return False, "Invalid overall band score: must be a number between 0 and 9"

    return True, None

def log_session(user_id, session_id_str, analysis_data, duration=None, transcript=None, start_time=None, end_time=None, questions_and_answers=None):
    """
    Creates SessionUsage and FeedbackSummary records from AI analysis
    and saves them to the database. This is the core data-saving function.

    Args:
        user_id: ID of the user who completed the session
        session_id_str: String identifier of the session (e.g., "session_1")
        analysis_data: Dictionary containing AI analysis results
        duration: Optional session duration in seconds
        transcript: Optional transcript text to calculate word count
        start_time: Optional session start timestamp
        end_time: Optional session end timestamp
        questions_and_answers: Optional list of questions with user answers
    """
    try:
        # Validate analysis data structure
        is_valid, error_message = validate_analysis_data(analysis_data)
        if not is_valid:
            print(f"ANALYTICS_ERROR: Invalid analysis data - {error_message}")
            return False

        # Calculate session metrics
        metrics = calculate_session_metrics(transcript, start_time, end_time)

        # Use calculated or provided duration, default to 15 minutes if none available
        session_duration = duration if duration is not None else metrics["duration"]
        if session_duration == 0:
            session_duration = 900  # Default 15 minutes

        words_spoken = metrics["words_spoken"]

        # Create the main session usage record
        new_session_usage = SessionUsage(
            user_id=user_id,
            session_id_str=session_id_str,
            duration=session_duration,
            words_spoken=words_spoken
        )

        # Prepare band scores data - include overall_band in the main scores
        criteria_scores = analysis_data.get('criteria_scores', {})
        overall_band = analysis_data.get('overall_band', {})

        # Combine criteria scores with overall band score
        complete_band_scores = criteria_scores.copy()
        complete_band_scores['overall_band'] = overall_band

        # Prepare comprehensive feedback data
        comprehensive_feedback = {
            'actionable_insights': analysis_data.get('actionable_insights', {}),
            'word_analysis': analysis_data.get('word_analysis', {}),
            'questions_and_answers': questions_and_answers or [],
            'original_transcript': transcript
        }

        # Create the corresponding feedback summary
        feedback_summary = FeedbackSummary(
            # The 'session' backref links this to new_session_usage automatically
            session=new_session_usage,
            # Use json.dumps to convert Python dicts into JSON strings for DB storage
            band_scores=json.dumps(complete_band_scores),
            feedback_text=json.dumps(comprehensive_feedback)
        )

        db.session.add(new_session_usage)
        db.session.add(feedback_summary)
        db.session.commit()

        print(f"ANALYTICS: Successfully logged session '{session_id_str}' for user '{user_id}'. "
              f"Duration: {session_duration}s, Words: {words_spoken}")
        print(f"ANALYTICS: Transcript length: {len(transcript) if transcript else 0} characters")
        print(f"ANALYTICS: Questions and answers count: {len(questions_and_answers) if questions_and_answers else 0}")
        print(f"ANALYTICS: Analysis data keys: {list(analysis_data.keys()) if analysis_data else 'None'}")
        return new_session_usage.id  # Return the session usage ID for reference

    except Exception as e:
        db.session.rollback()
        print(f"ANALYTICS_ERROR: Failed to log session. Rolled back transaction. Error: {e}")
        return False

# ==============================================================================
# --- Analytics API Logic ---
# ==============================================================================

def get_user_analytics(user_id):
    """
    Fetches all session history and progress data for a specific user.
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Query all sessions for the user, ordered by date
    sessions = SessionUsage.query.filter_by(user_id=user_id).order_by(SessionUsage.date.asc()).all()
    
    # Format the data for the frontend
    progress_data = []
    for session in sessions:
        feedback = session.feedback
        band_scores = json.loads(feedback.band_scores) if feedback else {}
        
        progress_data.append({
            "session_usage_id": session.id,
            "session_id_str": session.session_id_str,
            "date": session.date.isoformat(),
            "overall_score": band_scores.get('overall_band', {}).get('score'), # Example of drilling down
            "scores": band_scores
        })

    # Calculate summary stats
    total_sessions = len(sessions)
    total_practice_time = sum(s.duration for s in sessions) # in seconds

    return jsonify({
        "user_id": user.id,
        "username": user.username,
        "total_sessions": total_sessions,
        "total_practice_time_seconds": total_practice_time,
        "progress_over_time": progress_data
    })


def get_platform_summary():
    """
    Calculates and returns platform-wide statistics.
    """
    total_users = db.session.query(func.count(User.id)).scalar()
    total_sessions_run = db.session.query(func.count(SessionUsage.id)).scalar()
    total_hours_practiced = db.session.query(func.sum(SessionUsage.duration)).scalar() or 0
    total_hours_practiced /= 3600 # Convert seconds to hours

    return jsonify({
        "total_users": total_users,
        "total_sessions_run": total_sessions_run,
        "total_hours_practiced": round(total_hours_practiced, 2)
    })

def get_popular_sessions():
    """
    Finds and returns the most frequently practiced sessions.
    """
    popular_sessions_query = db.session.query(
        SessionUsage.session_id_str,
        func.count(SessionUsage.session_id_str).label('count')
    ).group_by(SessionUsage.session_id_str).order_by(func.count(SessionUsage.session_id_str).desc()).limit(5).all()

    popular_sessions = [
        {"session_id": session_id, "times_practiced": count}
        for session_id, count in popular_sessions_query
    ]

    return jsonify(popular_sessions)


def get_session_analytics_data(session_usage_id):
    """
    Helper function to get session analytics data as a Python dict (for internal use)
    """
    session_usage = SessionUsage.query.get(session_usage_id)
    if not session_usage:
        return None

    feedback = session_usage.feedback
    if not feedback:
        return None

    try:
        band_scores = json.loads(feedback.band_scores)
        feedback_data = json.loads(feedback.feedback_text)

        # Extract data with fallbacks for older records
        actionable_insights = feedback_data.get('actionable_insights', feedback_data) if isinstance(feedback_data, dict) else {}
        word_analysis = feedback_data.get('word_analysis', {})
        questions_and_answers = feedback_data.get('questions_and_answers', [])
        original_transcript = feedback_data.get('original_transcript', '')

        return {
            "session_usage_id": session_usage.id,
            "session_id_str": session_usage.session_id_str,
            "date": session_usage.date.isoformat(),
            "duration": session_usage.duration,
            "words_spoken": session_usage.words_spoken,
            "criteria_scores": {
                "fluency_coherence": band_scores.get('fluency_coherence', 0),
                "lexical_resource": band_scores.get('lexical_resource', 0),
                "grammatical_range_accuracy": band_scores.get('grammatical_range_accuracy', 0),
                "pronunciation": band_scores.get('pronunciation', 0)
            },
            "overall_band": band_scores.get('overall_band', {"score": 0, "summary": "No summary available"}),
            "actionable_insights": actionable_insights,
            "word_analysis": word_analysis,
            "questions_and_answers": questions_and_answers,
            "original_transcript": original_transcript
        }
    except (json.JSONDecodeError, Exception) as e:
        print(f"Error getting session analytics data: {e}")
        return None

def get_session_analytics(session_usage_id):
    """
    Fetches detailed analytics for a specific session usage record.
    """
    data = get_session_analytics_data(session_usage_id)
    if not data:
        return jsonify({"error": "Session not found or no feedback data available"}), 404

    return jsonify(data)