# ==============================================================================
# Spiko - Database Models
#
# This file defines the SQLAlchemy database models for the entire application,
# including users, session usage, and feedback summaries.
# This is the single source of truth for our database schema.
# ==============================================================================

import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt

# --- Initialize Extensions ---
# Define the extension objects here, but they will be initialized
# in flask_app.py to connect them with the app instance.
db = SQLAlchemy()
bcrypt = Bcrypt()

# ==============================================================================
# --- Model Definitions ---
# ==============================================================================

class User(db.Model):
    """
    User model for authentication and tracking.
    """
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # --- Relationships ---
    # A user can have many session usage records.
    # 'backref' creates a simple way to access the User from a SessionUsage object.
    # 'lazy=True' means the sessions are loaded from the DB as needed.
    sessions = db.relationship('SessionUsage', backref='user', lazy=True, cascade="all, delete-orphan")

    def __init__(self, username, email, password):
        self.username = username
        self.email = email
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        """Checks if the provided password matches the stored hash."""
        return bcrypt.check_password_hash(self.password_hash, password)

    def to_json(self):
        """Returns a JSON-safe representation of the user."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created_at": self.created_at.isoformat()
        }


class SessionUsage(db.Model):
    """
    Tracks each time a user completes a speaking session.
    """
    __tablename__ = 'session_usage'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_id_str = db.Column(db.String(100), nullable=False) # e.g., "session_3"
    duration = db.Column(db.Integer, nullable=False) # Duration in seconds
    date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    words_spoken = db.Column(db.Integer)

    # --- Relationships ---
    # Each session usage has one corresponding feedback summary.
    feedback = db.relationship('FeedbackSummary', backref='session', uselist=False, cascade="all, delete-orphan")


class FeedbackSummary(db.Model):
    """
    Stores the detailed AI feedback for a specific session usage.
    """
    __tablename__ = 'feedback_summary'

    id = db.Column(db.Integer, primary_key=True)
    session_usage_id = db.Column(db.Integer, db.ForeignKey('session_usage.id'), nullable=False)
    
    # Store complex data like band scores as JSON strings in the database.
    band_scores = db.Column(db.Text, nullable=False) # Stores JSON string of scores
    feedback_text = db.Column(db.Text) # Stores JSON string of actionable insights
    date = db.Column(db.DateTime, default=datetime.datetime.utcnow)