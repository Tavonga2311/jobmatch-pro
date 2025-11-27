import os
import sys
import traceback
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, MultipleFileField, BooleanField, SelectField, PasswordField
from wtforms.validators import DataRequired, Email, Length
import pdfminer.high_level
from docx import Document
import magic
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize Flask app
app = Flask(__name__)
app.config.from_object('config.Config')

db = SQLAlchemy(app)

# Ensure upload folder exists
try:
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
except Exception as e:
    print(f"Error creating upload folder: {str(e)}")
    sys.exit(1)

# Database Models
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

# Helper Functions
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_text_from_pdf(pdf_path):
    try:
        return pdfminer.high_level.extract_text(pdf_path)
    except Exception as e:
        raise Exception(f"Failed to extract PDF text: {str(e)}")

def extract_text_from_docx(docx_path):
    try:
        doc = Document(docx_path)
        return "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        raise Exception(f"Failed to extract DOCX text: {str(e)}")

def extract_text_from_file(file_path):
    try:
        mime = magic.Magic(mime=True)
        file_type = mime.from_file(file_path)
        
        if file_type == 'application/pdf':
            return extract_text_from_pdf(file_path)
        elif file_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
            return extract_text_from_docx(file_path)
        else:
            # Try extension-based fallback
            ext = file_path.rsplit('.', 1)[1].lower()
            if ext == 'pdf':
                return extract_text_from_pdf(file_path)
            elif ext == 'docx':
                return extract_text_from_docx(file_path)
        raise ValueError(f"Unsupported file type: {file_type}")
    except Exception as e:
        raise Exception(f"File processing error: {str(e)}")

def normalize_skill(skill):
    try:
        skill = re.sub(r'[^\w\s-]', '', skill.lower())
        return re.sub(r'\s+', ' ', skill).strip()
    except Exception as e:
        raise Exception(f"Skill normalization error: {str(e)}")

def calculate_match(cv_text, job_description, required_skills):
    try:
        if not cv_text:
            cv_text = ""
        if not job_description:
            job_description = ""
            
        cv_clean = re.sub(r'[^\w\s]', ' ', cv_text.lower())
        jd_clean = re.sub(r'[^\w\s]', ' ', job_description.lower())
        
        skills_list = [normalize_skill(skill.strip()) for skill in required_skills.split(',') if skill.strip()]
        
        # JD Match (40% weight)
        jd_match = 0
        if jd_clean.strip() and cv_clean.strip():
            try:
                vectorizer = TfidfVectorizer(stop_words='english', min_df=1)
                tfidf_matrix = vectorizer.fit_transform([jd_clean, cv_clean])
                jd_match = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            except Exception as e:
                print(f"JD match calculation warning: {str(e)}")
                jd_match = 0
        
        # Skills Match (60% weight)
        found_skills = []
        if skills_list and cv_clean:
            for skill in skills_list:
                if re.search(rf'\b{re.escape(skill)}\b', cv_clean):
                    found_skills.append(skill)
        
        skills_match = len(found_skills) / len(skills_list) if skills_list else 0
        
        total_score = (skills_match * 0.6 + jd_match * 0.4) * 100
        
        return {
            'total_score': round(total_score, 2),
            'jd_match': round(jd_match * 100, 2),
            'skills_match': round(skills_match * 100, 2),
            'missing_skills': ', '.join(list(set(skills_list) - set(found_skills))),
            'found_skills': ', '.join(found_skills)
        }
    except Exception as e:
        print(f"Match calculation error: {str(e)}")
        return {
            'total_score': 0,
            'jd_match': 0,
            'skills_match': 0,
            'missing_skills': '',
            'found_skills': ''
        }

# Form Classes
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    user_type = SelectField('I am a', choices=[('job_seeker', 'Job Seeker'), ('recruiter', 'Recruiter')], validators=[DataRequired()])
    submit = SubmitField('Login / Register')

class JobPostForm(FlaskForm):
    job_title = StringField('Job Title', validators=[DataRequired()])
    company_name = StringField('Company Name', validators=[DataRequired()])
    job_description = TextAreaField('Job Description', validators=[DataRequired()])
    required_skills = TextAreaField('Required Skills (comma separated)', validators=[DataRequired()])
    location = StringField('Location')
    salary_range = StringField('Salary Range')
    job_type = SelectField('Job Type', choices=[('', 'Select Job Type'), ('Full-time', 'Full-time'), ('Part-time', 'Part-time'), ('Contract', 'Contract'), ('Remote', 'Remote'), ('Hybrid', 'Hybrid')])
    submit = SubmitField('Post Job')

class JobSeekerProfileForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired()])
    skills = TextAreaField('Your Skills (comma separated)', validators=[DataRequired()])
    desired_position = StringField('Desired Position')
    desired_location = StringField('Desired Location')
    desired_salary = StringField('Desired Salary')
    experience_level = SelectField('Experience Level', choices=[('', 'Select Experience'), ('Entry', 'Entry Level'), ('Mid', 'Mid Level'), ('Senior', 'Senior Level')])
    resume_file = MultipleFileField('Upload Resume (PDF/DOCX)')
    submit = SubmitField('Save Profile')

# Routes
@app.route('/', methods=['GET', 'POST'])
def index():
    if 'user_id' in session:
        if session['user_type'] == 'recruiter':
            return redirect(url_for('recruiter_dashboard'))
        else:
            return redirect(url_for('job_seeker_dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user:
            if check_password_hash(user.password_hash, form.password.data) and user.user_type == form.user_type.data:
                session['user_id'] = user.id
                session['user_type'] = user.user_type
                session['user_name'] = user.name
                flash(f'Welcome back, {user.name}!', 'success')
                
                if user.user_type == 'recruiter':
                    return redirect(url_for('recruiter_dashboard'))
                else:
                    return redirect(url_for('job_seeker_dashboard'))
            else:
                flash('Invalid credentials or user type mismatch', 'error')
        else:
            # Auto-register new user
            hashed_password = generate_password_hash(form.password.data)
            new_user = User(
                email=form.email.data,
                password_hash=hashed_password,
                user_type=form.user_type.data,
                name=form.email.data.split('@')[0]
            )
            db.session.add(new_user)
            db.session.commit()
            
            session['user_id'] = new_user.id
            session['user_type'] = new_user.user_type
            session['user_name'] = new_user.name
            
            flash('Account created successfully! Please complete your profile.', 'success')
            
            if new_user.user_type == 'recruiter':
                return redirect(url_for('recruiter_dashboard'))
            else:
                return redirect(url_for('job_seeker_profile'))
    
    return render_template('index.html', form=form)

@app.route('/recruiter/dashboard')
def recruiter_dashboard():
    if 'user_id' not in session or session['user_type'] != 'recruiter':
        return redirect(url_for('index'))
    
    job_posts = JobPost.query.filter_by(user_id=session['user_id']).order_by(JobPost.created_at.desc()).all()
    return render_template('recruiter_dashboard.html', job_posts=job_posts)

@app.route('/recruiter/post-job', methods=['GET', 'POST'])
def post_job():
    if 'user_id' not in session or session['user_type'] != 'recruiter':
        return redirect(url_for('index'))
    
    form = JobPostForm()
    if form.validate_on_submit():
        job_post = JobPost(
            user_id=session['user_id'],
            job_title=form.job_title.data,
            company_name=form.company_name.data,
            job_description=form.job_description.data,
            required_skills=form.required_skills.data,
            location=form.location.data,
            salary_range=form.salary_range.data,
            job_type=form.job_type.data
        )
        db.session.add(job_post)
        db.session.commit()
        
        flash('Job posted successfully!', 'success')
        return redirect(url_for('recruiter_dashboard'))
    
    return render_template('post_job.html', form=form)

@app.route('/recruiter/analyze-cvs/<int:job_id>', methods=['GET', 'POST'])
def analyze_cvs(job_id):
    if 'user_id' not in session or session['user_type'] != 'recruiter':
        return redirect(url_for('index'))
    
    job_post = JobPost.query.get_or_404(job_id)
    
    if request.method == 'POST':
        files = request.files.getlist('cv_files')
        candidates = []
        
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                try:
                    file.save(filepath)
                    cv_text = extract_text_from_file(filepath)
                    analysis = calculate_match(cv_text, job_post.job_description, job_post.required_skills)
                    
                    candidates.append({
                        'filename': filename,
                        'analysis': analysis,
                        'cv_preview': cv_text[:200] + ("..." if len(cv_text) > 200 else "")
                    })
                    
                except Exception as e:
                    flash(f"Error processing {file.filename}: {str(e)}", 'error')
                finally:
                    if os.path.exists(filepath):
                        try:
                            os.remove(filepath)
                        except:
                            pass
        
        if candidates:
            candidates.sort(key=lambda x: x['analysis']['total_score'], reverse=True)
            return render_template('analysis_results.html',
                                job_post=job_post,
                                candidates=candidates,
                                best_candidate=candidates[0] if candidates else None)
        else:
            flash('No valid CVs processed. Please upload PDF or DOCX files.', 'error')
    
    return render_template('analyze_cvs.html', job_post=job_post)

@app.route('/job-seeker/dashboard')
def job_seeker_dashboard():
    if 'user_id' not in session or session['user_type'] != 'job_seeker':
        return redirect(url_for('index'))
    
    profile = JobSeekerProfile.query.filter_by(user_id=session['user_id']).first()
    job_posts = []
    
    # Get all active job posts
    all_job_posts = JobPost.query.filter_by(is_active=True).order_by(JobPost.created_at.desc()).all()
    
    for job in all_job_posts:
        # Check if already applied
        applied = JobApplication.query.filter_by(
            job_post_id=job.id, 
            job_seeker_id=session['user_id']
        ).first()
        
        if profile and profile.skills:
            match_result = calculate_match(
                profile.resume_text or profile.skills,
                job.job_description,
                job.required_skills
            )
        else:
            match_result = {'total_score': 0}
        
        job_posts.append({
            'job': job,
            'match_score': match_result['total_score'],
            'applied': applied is not None,
            'application_status': applied.status if applied else None
        })
    
    # Sort by match score
    job_posts.sort(key=lambda x: x['match_score'], reverse=True)
    
    return render_template('job_seeker_dashboard.html', job_posts=job_posts, profile=profile)

@app.route('/job-seeker/profile', methods=['GET', 'POST'])
def job_seeker_profile():
    if 'user_id' not in session or session['user_type'] != 'job_seeker':
        return redirect(url_for('index'))
    
    profile = JobSeekerProfile.query.filter_by(user_id=session['user_id']).first()
    form = JobSeekerProfileForm()
    
    if form.validate_on_submit():
        resume_text = ""
        
        # Process resume file if uploaded
        files = request.files.getlist('resume_file')
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                try:
                    file.save(filepath)
                    resume_text = extract_text_from_file(filepath)
                    break  # Use first valid file
                except Exception as e:
                    flash(f"Error processing resume: {str(e)}", 'error')
                finally:
                    if os.path.exists(filepath):
                        try:
                            os.remove(filepath)
                        except:
                            pass
        
        if profile:
            # Update existing profile
            profile.full_name = form.full_name.data
            profile.skills = form.skills.data
            profile.desired_position = form.desired_position.data
            profile.desired_location = form.desired_location.data
            profile.desired_salary = form.desired_salary.data
            profile.experience_level = form.experience_level.data
            if resume_text:
                profile.resume_text = resume_text
        else:
            # Create new profile
            profile = JobSeekerProfile(
                user_id=session['user_id'],
                full_name=form.full_name.data,
                skills=form.skills.data,
                desired_position=form.desired_position.data,
                desired_location=form.desired_location.data,
                desired_salary=form.desired_salary.data,
                experience_level=form.experience_level.data,
                resume_text=resume_text
            )
            db.session.add(profile)
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('job_seeker_dashboard'))
    
    # Populate form with existing data
    if profile:
        form.full_name.data = profile.full_name
        form.skills.data = profile.skills
        form.desired_position.data = profile.desired_position
        form.desired_location.data = profile.desired_location
        form.desired_salary.data = profile.desired_salary
        form.experience_level.data = profile.experience_level
    
    return render_template('job_seeker_profile.html', form=form, profile=profile)

@app.route('/apply-job/<int:job_id>')
def apply_job(job_id):
    if 'user_id' not in session or session['user_type'] != 'job_seeker':
        return redirect(url_for('index'))
    
    # Check if already applied
    existing_application = JobApplication.query.filter_by(
        job_post_id=job_id, 
        job_seeker_id=session['user_id']
    ).first()
    
    if not existing_application:
        profile = JobSeekerProfile.query.filter_by(user_id=session['user_id']).first()
        job_post = JobPost.query.get_or_404(job_id)
        
        if profile:
            match_result = calculate_match(
                profile.resume_text or profile.skills,
                job_post.job_description,
                job_post.required_skills
            )
            
            application = JobApplication(
                job_post_id=job_id,
                job_seeker_id=session['user_id'],
                match_score=match_result['total_score']
            )
            db.session.add(application)
            db.session.commit()
            
            flash(f'Application submitted successfully! Match score: {match_result["total_score"]}%', 'success')
        else:
            flash('Please complete your profile before applying', 'error')
    else:
        flash('You have already applied for this job', 'warning')
    
    return redirect(url_for('job_seeker_dashboard'))

@app.route('/recruiter/view-applications/<int:job_id>')
def view_applications(job_id):
    if 'user_id' not in session or session['user_type'] != 'recruiter':
        return redirect(url_for('index'))
    
    job_post = JobPost.query.get_or_404(job_id)
    if job_post.user_id != session['user_id']:
        flash('Access denied', 'error')
        return redirect(url_for('recruiter_dashboard'))
    
    applications = JobApplication.query.filter_by(job_post_id=job_id).order_by(JobApplication.match_score.desc()).all()
    
    application_data = []
    for app in applications:
        profile = JobSeekerProfile.query.filter_by(user_id=app.job_seeker_id).first()
        application_data.append({
            'application': app,
            'profile': profile,
            'user': app.job_seeker
        })
    
    return render_template('view_applications.html', job_post=job_post, applications=application_data)

@app.route('/update-application-status/<int:application_id>/<status>')
def update_application_status(application_id, status):
    if 'user_id' not in session or session['user_type'] != 'recruiter':
        return redirect(url_for('index'))
    
    application = JobApplication.query.get_or_404(application_id)
    job_post = JobPost.query.get(application.job_post_id)
    
    if job_post.user_id != session['user_id']:
        flash('Access denied', 'error')
        return redirect(url_for('recruiter_dashboard'))
    
    application.status = status
    db.session.commit()
    
    flash(f'Application status updated to {status}', 'success')
    return redirect(url_for('view_applications', job_id=application.job_post_id))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('index'))

@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', error="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('error.html', error="Internal server error"), 500

@app.errorhandler(Exception)
def handle_exception(error):
    db.session.rollback()
    error_msg = "An unexpected error occurred. Please try again later."
    app.logger.error(f"Error: {str(error)}\n{traceback.format_exc()}")
    return render_template('error.html', error=error_msg), 500

# Initialize database
def init_db():
    with app.app_context():
        db.create_all()
        print("Database initialized successfully!")

# ... all your existing code ...

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)