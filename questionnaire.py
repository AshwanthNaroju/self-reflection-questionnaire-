from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app import db, load_tree_data
from models import Response

questionnaire_bp = Blueprint('questionnaire', __name__)

@questionnaire_bp.route('/dashboard')
@login_required
def dashboard():
    # Check if user has completed questionnaire
    has_completed = Response.query.filter_by(user_id=current_user.id).count() > 0
    return render_template('dashboard.html', has_completed=has_completed)

@questionnaire_bp.route('/start')
@login_required
def start():
    # Clear previous responses
    Response.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    session['current_node'] = None
    return redirect(url_for('questionnaire.question'))

@questionnaire_bp.route('/question', methods=['GET', 'POST'])
@login_required
def question():
    nodes, children = load_tree_data()
    
    if 'current_node' not in session or not session['current_node']:
        # Start from first root node
        root_nodes = [nid for nid, n in nodes.items() if n['parent'] == ""]
        session['current_node'] = root_nodes[0] if root_nodes else None
    
    current = session['current_node']
    
    if request.method == 'POST':
        answer = request.form.get('answer')
        question_id = request.form.get('question_id')
        
        # Save response
        response = Response(
            user_id=current_user.id,
            question_id=question_id,
            answer=answer
        )
        db.session.add(response)
        db.session.commit()
        
        # Process answer to find next node
        node = nodes[current]
        if current in children:
            next_node = children[current][0]
            if nodes[next_node]['type'].strip() == 'reflection':
                # Process reflection
                reflection_node = nodes[next_node]
                if reflection_node.get('score'):
                    try:
                        score_val = int(reflection_node['score'].replace('+', ''))
                        current_user.total_score += score_val
                        response.score_earned = score_val
                        db.session.commit()
                    except:
                        pass
                
                session['current_node'] = None
                flash('Questionnaire completed!', 'success')
                return redirect(url_for('questionnaire.results'))
            else:
                # Process decision mapping
                decision = nodes[next_node]
                mappings = decision['mapping'].split(';')
                matched = False
                
                for m in mappings:
                    if ':' not in m:
                        continue
                    key, value = m.split(':')
                    key = key.replace('answer=', '').strip()
                    if key == answer:
                        session['current_node'] = value.strip()
                        matched = True
                        break
                
                if not matched:
                    session['current_node'] = None
                    flash('No valid path found', 'error')
                    return redirect(url_for('questionnaire.results'))
        
        return redirect(url_for('questionnaire.question'))
    
    # GET request - display question
    if not current or current not in nodes:
        return redirect(url_for('questionnaire.results'))
    
    node = nodes[current]
    if node['type'].strip() == 'question':
        options = node['options'].split('|') if node['options'] else []
        return render_template('question.html', node=node, options=options)
    else:
        return redirect(url_for('questionnaire.results'))

@questionnaire_bp.route('/results')
@login_required
def results():
    score = current_user.total_score
    
    if score >= 5:
        mindset = "🌟 Strong & Growth-Oriented"
        description = "You demonstrate excellent adaptability, strong teamwork, and balanced focus. Keep up the great work!"
    elif score >= 3:
        mindset = "⚖️ Balanced but Needs Improvement"
        description = "You're on the right track! Focus on areas that need development to achieve your full potential."
    else:
        mindset = "🔧 Needs Focus & Development"
        description = "You've identified areas for growth. With conscious effort, you can improve significantly."
    
    responses = Response.query.filter_by(user_id=current_user.id).all()
    
    return render_template('results.html', 
                         score=score, 
                         mindset=mindset,
                         description=description,
                         responses=responses)

@questionnaire_bp.route('/reset')
@login_required
def reset():
    Response.query.filter_by(user_id=current_user.id).delete()
    current_user.total_score = 0
    db.session.commit()
    session['current_node'] = None
    flash('Your progress has been reset', 'info')
    return redirect(url_for('questionnaire.dashboard'))