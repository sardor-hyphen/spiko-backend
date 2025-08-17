#!/usr/bin/env python3

import sys
import os
sys.path.append('.')

from models import db, SessionUsage, FeedbackSummary, User
from flask import Flask

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/spiko.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    print("=== Database Check ===")
    
    # Check users
    users = User.query.all()
    print(f"Total Users: {len(users)}")
    for user in users:
        print(f"  User ID: {user.id}, Username: {user.username}, Email: {user.email}")
    
    print()
    
    # Check session usage records
    sessions = SessionUsage.query.all()
    print(f"Total SessionUsage records: {len(sessions)}")
    for session in sessions:
        feedback_status = "Yes" if session.feedback else "No"
        print(f"  ID: {session.id}, Session: {session.session_id_str}, User: {session.user_id}, Date: {session.date}, Has Feedback: {feedback_status}")
    
    print()
    
    # Check feedback summaries
    feedbacks = FeedbackSummary.query.all()
    print(f"Total FeedbackSummary records: {len(feedbacks)}")
    for feedback in feedbacks:
        print(f"  ID: {feedback.id}, Session Usage ID: {feedback.session_usage_id}")
