import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here-change-in-production'
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'pdf', 'docx'}
    SQLALCHEMY_DATABASE_URI = 'sqlite:///job_matching.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False