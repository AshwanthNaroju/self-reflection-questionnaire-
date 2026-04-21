from flask import Flask, render_template, redirect, url_for, flash, request, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import csv
import os
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-please-make-it-secure'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    total_score = db.Column(db.Integer, default=0)
    responses = db.relationship('Response', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Response(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    question_id = db.Column(db.String(50))
    answer = db.Column(db.String(200))
    score_earned = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Load tree data
def load_tree_data():
    nodes = {}
    children = {}
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    tree_path = os.path.join(base_dir, 'tree.tsv')
    
    if not os.path.exists(tree_path):
        print(f"Warning: tree.tsv not found at {tree_path}")
        return nodes, children
    
    with open(tree_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            node_id = row['id'].strip()
            parent = row['parent'].strip()
            nodes[node_id] = row
            if parent:
                children.setdefault(parent, []).append(node_id)
    
    return nodes, children

def get_next_node(nodes, children, current_node, answer):
    """Get the next node based on the answer"""
    if current_node not in children:
        return None
    
    # Get the decision node (first child of current question)
    decision_node_id = children[current_node][0]
    decision_node = nodes[decision_node_id]
    
    if decision_node['type'].strip() != 'decision':
        return None
    
    # Parse mapping
    mappings = decision_node['mapping'].split(';')
    for mapping in mappings:
        if ':' not in mapping:
            continue
        key, value = mapping.split(':')
        key = key.replace('answer=', '').strip()
        if key == answer:
            return value.strip()
    
    return None

def get_score_for_answer(question_id, answer):
    """Return points based on the question and answer (first option is correct)"""
    score_mapping = {
        # Section 1: Adaptability
        'Q1': {'Adjusted strategy': 2, 'Stayed calm': 1, 'Took initiative': 1, 'Felt stuck': 0, 'Avoided situation': 0, 'Blamed others': 0},
        'Q2P': {'Planning': 2, 'Experience': 1, 'Support': 1},
        'Q3P': {'Yes': 2, 'Maybe': 1, 'No': 0},
        'Q2N': {'Confusion': 1, 'Stress': 1, 'Lack of clarity': 1},
        'Q3N': {'Plan better': 2, 'Ask help': 1, 'Stay calm': 1},
        
        # Section 2: Teamwork
        'Q4': {'Helped someone': 2, 'Shared knowledge': 2, 'Supported team': 2, 'Did not help': 0, 'Focused only on self': 0, 'Ignored others': 0},
        'Q5P': {'Helped team': 2, 'Improved work': 2, 'Built trust': 2},
        'Q6P': {'Be consistent': 2, 'Take initiative': 1, 'Support more': 1},
        'Q5N': {'Busy': 0, 'Not interested': 0, 'Unaware': 0},
        'Q6N': {'Help one person': 2, 'Communicate': 1, 'Be aware': 1},
        
        # Section 3: Focus
        'Q7': {'Balanced both': 2, 'Self goals': 1, 'Team goals': 1, 'Got distracted': 0, 'No clear focus': 0},
        'Q8P': {'Time management': 2, 'Prioritization': 1, 'Planning': 1},
        'Q8M': {'Yes': 2, 'No': 0, 'Partially': 1},
        'Q8N': {'Social media': 0, 'Lack of planning': 0, 'Low motivation': 0},
        'Q9N': {'Set goals': 2, 'Reduce distractions': 1, 'Follow schedule': 1},
    }
    
    return score_mapping.get(question_id, {}).get(answer, 0)

def extract_score(score_text):
    """Extract numeric score from score text"""
    if not score_text:
        return 0
    numbers = re.findall(r'\d+', score_text)
    if numbers:
        return int(numbers[0])
    return 0

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            
            # Redirect to the page they were trying to access
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('register.html')
        
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    has_completed = Response.query.filter_by(user_id=current_user.id).count() > 0
    return render_template('dashboard.html', has_completed=has_completed)

@app.route('/profile')
@login_required
def profile():
    responses = Response.query.filter_by(user_id=current_user.id).all()
    return render_template('profile.html', user=current_user, responses=responses)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        email = request.form.get('email')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if email:
            if User.query.filter(User.email == email, User.id != current_user.id).first():
                flash('Email already in use', 'error')
                return render_template('edit_profile.html', user=current_user)
            current_user.email = email
        
        if current_password and new_password:
            if not current_user.check_password(current_password):
                flash('Current password is incorrect', 'error')
                return render_template('edit_profile.html', user=current_user)
            
            if new_password != confirm_password:
                flash('New passwords do not match', 'error')
                return render_template('edit_profile.html', user=current_user)
            
            current_user.set_password(new_password)
        
        db.session.commit()
        flash('Profile updated successfully', 'success')
        return redirect(url_for('profile'))
    
    return render_template('edit_profile.html', user=current_user)

@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_admin:
        flash('Access denied. Admin only.', 'error')
        return redirect(url_for('dashboard'))
    
    users = User.query.all()
    return render_template('admin.html', users=users)

@app.route('/admin/user/<int:user_id>')
@login_required
def view_user(user_id):
    if not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    responses = Response.query.filter_by(user_id=user_id).all()
    return render_template('user_details.html', user=user, responses=responses)

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Cannot delete yourself', 'error')
        return redirect(url_for('admin_panel'))
    
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/stats')
@login_required
def stats():
    if not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))
    
    total_users = User.query.count()
    total_responses = Response.query.count()
    avg_score = db.session.query(db.func.avg(User.total_score)).scalar() or 0
    
    return render_template('stats.html', 
                         total_users=total_users,
                         total_responses=total_responses,
                         avg_score=avg_score)

@app.route('/start')
@login_required
def start():
    # Clear previous responses
    Response.query.filter_by(user_id=current_user.id).delete()
    current_user.total_score = 0
    db.session.commit()
    
    # Clear session but keep login info
    session.pop('questions_to_ask', None)
    session.pop('current_question_set', None)
    session.pop('total_score', None)
    session.pop('current_path', None)
    
    # Get all root questions
    nodes, children = load_tree_data()
    root_questions = [nid for nid, n in nodes.items() if n['parent'] == "" and n['type'].strip() == 'question']
    
    # Store questions to ask
    session['questions_to_ask'] = root_questions.copy()
    session['current_question_set'] = 0
    session['total_score'] = 0
    session['current_path'] = {}  # Store current position for each root question
    
    # Start with first root question
    if root_questions:
        return redirect(url_for('ask_question', question_id=root_questions[0]))
    else:
        flash('No questions found', 'error')
        return redirect(url_for('dashboard'))

@app.route('/ask/<question_id>', methods=['GET', 'POST'])
@login_required
def ask_question(question_id):
    nodes, children = load_tree_data()
    
    if question_id not in nodes:
        flash('Question not found', 'error')
        return redirect(url_for('dashboard'))
    
    node = nodes[question_id]
    
    if request.method == 'POST':
        answer = request.form.get('answer')
        
        # Calculate score for this answer
        score_for_answer = get_score_for_answer(question_id, answer)
        
        # Save the response with score
        response = Response(
            user_id=current_user.id,
            question_id=question_id,
            answer=answer,
            score_earned=score_for_answer
        )
        db.session.add(response)
        
        # Add to total score
        session['total_score'] = session.get('total_score', 0) + score_for_answer
        print(f"Question {question_id}: '{answer}' earned {score_for_answer} points. Total: {session['total_score']}")
        
        db.session.commit()
        
        # Find the next node based on answer
        next_node = get_next_node(nodes, children, question_id, answer)
        
        if next_node and next_node in nodes:
            # Check if next node is a reflection
            if nodes[next_node]['type'].strip() == 'reflection':
                # Also add score from reflection node if any
                reflection_score = extract_score(nodes[next_node].get('score', ''))
                if reflection_score > 0:
                    session['total_score'] = session.get('total_score', 0) + reflection_score
                    print(f"Reflection {next_node} added {reflection_score} points. Total: {session['total_score']}")
                
                # Move to next root question
                questions_to_ask = session.get('questions_to_ask', [])
                current_set = session.get('current_question_set', 0)
                next_set = current_set + 1
                
                if next_set < len(questions_to_ask):
                    session['current_question_set'] = next_set
                    return redirect(url_for('ask_question', question_id=questions_to_ask[next_set]))
                else:
                    # All questions completed
                    current_user.total_score = session.get('total_score', 0)
                    db.session.commit()
                    flash('Questionnaire completed!', 'success')
                    return redirect(url_for('results'))
            else:
                # Continue with next question in same path
                return redirect(url_for('ask_question', question_id=next_node))
        else:
            # Move to next root question
            questions_to_ask = session.get('questions_to_ask', [])
            current_set = session.get('current_question_set', 0)
            next_set = current_set + 1
            
            if next_set < len(questions_to_ask):
                session['current_question_set'] = next_set
                return redirect(url_for('ask_question', question_id=questions_to_ask[next_set]))
            else:
                current_user.total_score = session.get('total_score', 0)
                db.session.commit()
                flash('Questionnaire completed!', 'success')
                return redirect(url_for('results'))
    
    # GET request - display question
    options = node['options'].split('|') if node['options'] else []
    questions_to_ask = session.get('questions_to_ask', [])
    current_set = session.get('current_question_set', 0)
    total_questions = len(questions_to_ask)
    progress = int((current_set / total_questions) * 100) if total_questions > 0 else 0
    
    return render_template('question.html', 
                         node=node, 
                         options=options,
                         question_number=current_set + 1,
                         total_questions=total_questions,
                         progress=progress)

@app.route('/results')
@login_required
def results():
    # Get final score from session or database
    score = session.get('total_score', current_user.total_score)
    
    # Update database with final score
    if score > 0:
        current_user.total_score = score
        db.session.commit()
    
    # Get all responses
    responses = Response.query.filter_by(user_id=current_user.id).all()
    
    # Calculate maximum possible score
    max_score = 0
    for response in responses:
        # For each question, get the maximum possible score
        question_id = response.question_id
        if question_id == 'Q1':
            max_score += 2
        elif question_id == 'Q2P':
            max_score += 2
        elif question_id == 'Q3P':
            max_score += 2
        elif question_id == 'Q4':
            max_score += 2
        elif question_id == 'Q5P':
            max_score += 2
        elif question_id == 'Q6P':
            max_score += 2
        elif question_id == 'Q7':
            max_score += 2
        elif question_id == 'Q8P':
            max_score += 2
        elif question_id == 'Q2N' or question_id == 'Q3N' or question_id == 'Q5N' or question_id == 'Q6N' or question_id == 'Q8M' or question_id == 'Q9N':
            max_score += 2
    
    if score >= 8:
        mindset = "🌟 Strong & Growth-Oriented"
        description = "You demonstrate excellent adaptability, strong teamwork, and balanced focus. Keep up the great work!"
    elif score >= 5:
        mindset = "⚖️ Balanced but Needs Improvement"
        description = "You're on the right track! Focus on areas that need development to achieve your full potential."
    else:
        mindset = "🔧 Needs Focus & Development"
        description = "You've identified areas for growth. With conscious effort, you can improve significantly."
    
    return render_template('results.html', 
                         score=score,
                         mindset=mindset,
                         description=description,
                         responses=responses,
                         max_score=max_score)

@app.route('/reset')
@login_required
def reset():
    Response.query.filter_by(user_id=current_user.id).delete()
    current_user.total_score = 0
    db.session.commit()
    session.pop('questions_to_ask', None)
    session.pop('current_question_set', None)
    session.pop('total_score', None)
    session.pop('current_path', None)
    flash('Your progress has been reset', 'info')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create admin user if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', email='admin@example.com', is_admin=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("="*50)
            print("Admin user created successfully!")
            print("Username: admin")
            print("Password: admin123")
            print("="*50)
    print("\n" + "="*50)
    print("Server is running!")
    print("Open your browser and go to: http://localhost:5000")
    print("="*50 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)