from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from models import User, Response

profile_bp = Blueprint('profile', __name__)

@profile_bp.route('/profile')
@login_required
def profile():
    responses = Response.query.filter_by(user_id=current_user.id).all()
    return render_template('profile.html', user=current_user, responses=responses)

@profile_bp.route('/profile/edit', methods=['GET', 'POST'])
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
                return render_template('edit_profile.html')
            current_user.email = email
        
        if current_password and new_password:
            if not current_user.check_password(current_password):
                flash('Current password is incorrect', 'error')
                return render_template('edit_profile.html')
            
            if new_password != confirm_password:
                flash('New passwords do not match', 'error')
                return render_template('edit_profile.html')
            
            current_user.set_password(new_password)
        
        db.session.commit()
        flash('Profile updated successfully', 'success')
        return redirect(url_for('profile.profile'))
    
    return render_template('edit_profile.html')