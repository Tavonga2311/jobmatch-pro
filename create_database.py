# create_database.py
import os
import sys
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///job_matching.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models (same as in your app.py)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    user_type = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class JobPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    job_title = db.Column(db.String(200), nullable=False)
    company_name = db.Column(db.String(200), nullable=False)
    job_description = db.Column(db.Text, nullable=False)
    required_skills = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(100))
    salary_range = db.Column(db.String(100))
    job_type = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    user = db.relationship('User', backref=db.backref('job_posts', lazy=True))

class JobSeekerProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    resume_text = db.Column(db.Text)
    skills = db.Column(db.Text)
    desired_position = db.Column(db.String(200))
    desired_location = db.Column(db.String(100))
    desired_salary = db.Column(db.String(100))
    experience_level = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('profile', uselist=False))

class JobApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_post_id = db.Column(db.Integer, db.ForeignKey('job_post.id'), nullable=False)
    job_seeker_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    match_score = db.Column(db.Float)
    status = db.Column(db.String(50), default='pending')
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    job_post = db.relationship('JobPost', backref=db.backref('applications', lazy=True))
    job_seeker = db.relationship('User', foreign_keys=[job_seeker_id])

def create_database():
    """Create the database and sample data"""
    with app.app_context():
        # Create all tables
        db.create_all()
        print("✅ Database tables created successfully!")
        
        # Create sample users
        sample_recruiter = User(
            email="recruiter@company.com",
            password_hash=generate_password_hash("password123"),
            user_type="recruiter",
            name="John Recruiter"
        )
        
        sample_job_seeker = User(
            email="jobseeker@email.com",
            password_hash=generate_password_hash("password123"),
            user_type="job_seeker",
            name="Jane Candidate"
        )
        
        # Add users to database
        db.session.add(sample_recruiter)
        db.session.add(sample_job_seeker)
        db.session.commit()
        print("✅ Sample users created!")
        
        # Create sample job posts
        sample_job = JobPost(
            user_id=sample_recruiter.id,
            job_title="Senior Python Developer",
            company_name="Tech Solutions Inc.",
            job_description="We are looking for an experienced Python developer to join our team. You will be responsible for developing and maintaining web applications, working with databases, and collaborating with our front-end developers.",
            required_skills="Python, Django, Flask, PostgreSQL, REST APIs, Git",
            location="New York, NY",
            salary_range="$100,000 - $130,000",
            job_type="Full-time"
        )
        
        sample_job2 = JobPost(
            user_id=sample_recruiter.id,
            job_title="Frontend React Developer",
            company_name="Digital Innovations LLC",
            job_description="Join our frontend team to build amazing user interfaces. You'll work with React, TypeScript, and modern CSS frameworks to create responsive web applications.",
            required_skills="JavaScript, React, TypeScript, HTML, CSS, Git",
            location="Remote",
            salary_range="$90,000 - $120,000",
            job_type="Full-time"
        )
        
        sample_job3 = JobPost(
            user_id=sample_recruiter.id,
            job_title="Data Scientist",
            company_name="Data Analytics Corp",
            job_description="We need a data scientist to analyze complex datasets and build machine learning models. Experience with Python data stack and statistical analysis required.",
            required_skills="Python, Pandas, NumPy, Scikit-learn, SQL, Machine Learning",
            location="Boston, MA",
            salary_range="$110,000 - $140,000",
            job_type="Full-time"
        )
        
        db.session.add(sample_job)
        db.session.add(sample_job2)
        db.session.add(sample_job3)
        db.session.commit()
        print("✅ Sample job posts created!")
        
        # Create sample job seeker profile
        sample_profile = JobSeekerProfile(
            user_id=sample_job_seeker.id,
            full_name="Jane Candidate",
            skills="Python, JavaScript, React, SQL, Git, Docker, AWS",
            desired_position="Full Stack Developer",
            desired_location="New York, NY or Remote",
            desired_salary="$100,000 - $130,000",
            experience_level="Mid",
            resume_text="Experienced software developer with 5 years in web development. Strong skills in Python, JavaScript, and cloud technologies. Proven track record of delivering high-quality applications."
        )
        
        db.session.add(sample_profile)
        db.session.commit()
        print("✅ Sample job seeker profile created!")
        
        # Create sample application
        sample_application = JobApplication(
            job_post_id=sample_job.id,
            job_seeker_id=sample_job_seeker.id,
            match_score=85.5,
            status="pending"
        )
        
        db.session.add(sample_application)
        db.session.commit()
        print("✅ Sample job application created!")
        
        print("\n🎉 Database setup completed successfully!")
        print("\n📋 Sample Login Credentials:")
        print("   Recruiter:  email: recruiter@company.com  password: password123")
        print("   Job Seeker: email: jobseeker@email.com    password: password123")
        print("\n📍 Database file created: job_matching.db")

if __name__ == '__main__':
    create_database()