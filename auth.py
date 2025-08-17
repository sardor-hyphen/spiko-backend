# ==============================================================================
# Spiko - Authentication Module (Refactored)
#
# This file handles user logic. It IMPORTS the database models and extensions
# from the central models.py file.
# ==============================================================================

import datetime
import jwt
from flask import request, jsonify, current_app

# --- Import shared extensions and models ---
# This is the key change: we no longer define User or db here.
from models import db, bcrypt, User

# ==============================================================================
# --- Authentication Routes ---
# The logic within these functions remains exactly the same.
# ==============================================================================

def register_user():
    """
    Handles the logic for the /api/register endpoint.
    Creates a new user if validation passes.
    """
    data = request.get_json()
    if not data or not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({"error": "Missing username, email, or password"}), 400

    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if User.query.filter_by(username=username).first() is not None:
        return jsonify({"error": "Username already exists"}), 409
    if User.query.filter_by(email=email).first() is not None:
        return jsonify({"error": "Email address already registered"}), 409

    new_user = User(username=username, email=email, password=password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User registered successfully!", "user": new_user.to_json()}), 201


def login_user():
    """
    Handles the logic for the /api/login endpoint.
    Authenticates a user and would typically return an access token.
    """
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"error": "Missing email or password"}), 400

    email = data.get('email')
    password = data.get('password')
    
    user = User.query.filter_by(email=email).first()

    if user and user.check_password(password):
        user.last_login = datetime.datetime.utcnow()
        db.session.commit()

        # Create a proper JWT token
        from flask import current_app
        payload = {
            'user_id': user.id,
            'email': user.email,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)  # Token expires in 7 days
        }
        token = jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')

        return jsonify({
            "message": "Login successful!",
            "token": token,
            "user": user.to_json()
        }), 200
    
    return jsonify({"error": "Invalid credentials"}), 401


def get_current_user(user_id):
    """
    Handles the logic for the /api/me endpoint.
    Fetches the current user's data.
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify(user.to_json()), 200


def update_user_profile(user_id):
    """
    Handles the logic for the PUT /api/me endpoint.
    Updates the current user's profile information.
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Update username if provided
    if 'username' in data:
        new_username = data['username'].strip()
        if not new_username:
            return jsonify({"error": "Username cannot be empty"}), 400

        # Check if username is already taken by another user
        existing_user = User.query.filter_by(username=new_username).first()
        if existing_user and existing_user.id != user_id:
            return jsonify({"error": "Username already exists"}), 409

        user.username = new_username

    # Update email if provided
    if 'email' in data:
        new_email = data['email'].strip()
        if not new_email:
            return jsonify({"error": "Email cannot be empty"}), 400

        # Check if email is already taken by another user
        existing_user = User.query.filter_by(email=new_email).first()
        if existing_user and existing_user.id != user_id:
            return jsonify({"error": "Email already exists"}), 409

        user.email = new_email

    try:
        db.session.commit()
        return jsonify({"message": "Profile updated successfully", "user": user.to_json()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to update profile"}), 500


def update_user_password(user_id):
    """
    Handles the logic for the PUT /api/me/password endpoint.
    Updates the current user's password.
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    if not data or 'current_password' not in data or 'new_password' not in data:
        return jsonify({"error": "Missing current_password or new_password"}), 400

    current_password = data['current_password']
    new_password = data['new_password']

    # Verify current password
    if not user.check_password(current_password):
        return jsonify({"error": "Current password is incorrect"}), 401

    # Validate new password
    if len(new_password) < 6:
        return jsonify({"error": "New password must be at least 6 characters long"}), 400

    # Update password
    user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')

    try:
        db.session.commit()
        return jsonify({"message": "Password updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to update password"}), 500


def delete_user_account(user_id):
    """
    Handles the logic for the DELETE /api/me endpoint.
    Deletes the current user's account and all associated data.
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        # Delete all user's session data
        from models import SessionUsage, FeedbackSummary

        # Get all user's sessions
        user_sessions = SessionUsage.query.filter_by(user_id=user_id).all()

        # Delete feedback summaries for user's sessions
        for session in user_sessions:
            feedback = FeedbackSummary.query.filter_by(session_usage_id=session.id).first()
            if feedback:
                db.session.delete(feedback)

        # Delete user's sessions
        SessionUsage.query.filter_by(user_id=user_id).delete()

        # Delete the user
        db.session.delete(user)
        db.session.commit()

        return jsonify({"message": "Account deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to delete account"}), 500