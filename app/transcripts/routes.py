from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app.models import Transcript, Recording, Matter, AuditLog, User
from app import db
from datetime import datetime, timezone
from sqlalchemy import or_

transcripts = Blueprint('transcripts', __name__)

def log_action(action):
    entry = AuditLog(
        username=current_user.username,
        role=current_user.role,
        action=action,
        ip_address=request.remote_addr
    )
    db.session.add(entry)
    db.session.commit()

def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

@transcripts.route('/transcripts')
@login_required
def index():
    all_transcripts = Transcript.query.order_by(
        Transcript.created_at.desc()).all()
    return render_template('transcripts/index.html',
        transcripts=all_transcripts)

@transcripts.route('/transcripts/search')
@login_required
def search():
    query        = request.args.get('q', '').strip()
    language     = request.args.get('language', '')
    session_type = request.args.get('session_type', '')
    status       = request.args.get('status', '')
    date_from    = request.args.get('date_from', '')
    date_to      = request.args.get('date_to', '')

    results = Transcript.query

    # Full text search across transcript content and matter number
    if query:
        results = results.join(Matter, Transcript.matter_id == Matter.id,
                               isouter=True)\
                         .join(Recording, Transcript.recording_id == Recording.id,
                               isouter=True)\
                         .filter(or_(
                             Transcript.content.ilike(f'%{query}%'),
                             Matter.matter_number.ilike(f'%{query}%'),
                             Matter.title.ilike(f'%{query}%'),
                             Matter.accused.ilike(f'%{query}%'),
                             Recording.venue.ilike(f'%{query}%'),
                             Recording.officer.ilike(f'%{query}%'),
                         ))

    # Language filter
    if language:
        results = results.filter(Transcript.language == language)

    # Session type filter — join Recording if not already joined
    if session_type:
        if not query:
            results = results.join(Recording,
                Transcript.recording_id == Recording.id, isouter=True)
        results = results.filter(Recording.session_type == session_type)

    # Approval status filter
    if status == 'approved':
        results = results.filter(Transcript.is_approved == True)
    elif status == 'pending':
        results = results.filter(Transcript.is_approved == False)

    # Date range filter
    if date_from:
        try:
            df = datetime.strptime(date_from, '%Y-%m-%d')
            results = results.filter(Transcript.created_at >= df)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, '%Y-%m-%d')
            results = results.filter(Transcript.created_at <= dt)
        except ValueError:
            pass

    results = results.order_by(Transcript.created_at.desc()).all()

    # Count keyword matches per result for relevance display
    match_counts = {}
    if query:
        for t in results:
            count = t.content.lower().count(query.lower()) if t.content else 0
            match_counts[t.id] = count

    return render_template('transcripts/search.html',
        results      = results,
        query        = query,
        language     = language,
        session_type = session_type,
        status       = status,
        date_from    = date_from,
        date_to      = date_to,
        match_counts = match_counts,
        total        = len(results)
    )

@transcripts.route('/transcripts/<int:id>')
@login_required
def view(id):
    transcript = Transcript.query.get_or_404(id)
    # Highlight query if coming from search
    query = request.args.get('q', '')
    return render_template('transcripts/view.html',
        transcript=transcript, highlight_query=query)

@transcripts.route('/transcripts/new', methods=['GET', 'POST'])
@login_required
def new():
    recording_id = request.args.get('recording_id', type=int)
    recording    = Recording.query.get_or_404(recording_id) if recording_id else None

    if request.method == 'POST':
        recording_id = request.form.get('recording_id', type=int)
        recording    = Recording.query.get_or_404(recording_id)
        content      = request.form.get('content', '').strip()

        if not content:
            flash('Transcript content cannot be empty.', 'danger')
            return redirect(request.url)

        t = Transcript(
            content      = content,
            language     = request.form.get('language', 'English'),
            matter_id    = recording.matter_id,
            recording_id = recording.id,
            created_by   = current_user.id
        )
        db.session.add(t)
        db.session.commit()
        log_action(f'Created transcript for recording {recording.id}')
        flash('Transcript saved successfully.', 'success')
        return redirect(url_for('transcripts.view', id=t.id))

    return render_template('transcripts/new.html', recording=recording)

@transcripts.route('/transcripts/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    transcript = Transcript.query.get_or_404(id)
    if request.method == 'POST':
        transcript.content    = request.form.get('content', '').strip()
        transcript.updated_at = _now()
        db.session.commit()
        log_action(f'Edited transcript {id}')
        flash('Transcript updated.', 'success')
        return redirect(url_for('transcripts.view', id=transcript.id))
    return render_template('transcripts/edit.html', transcript=transcript)

@transcripts.route('/transcripts/<int:id>/approve', methods=['POST'])
@login_required
def approve(id):
    transcript             = Transcript.query.get_or_404(id)
    transcript.is_approved = True
    transcript.approved_by = current_user.id
    transcript.approved_at = _now()
    db.session.commit()
    log_action(f'Approved transcript {id}')
    flash('Transcript approved.', 'success')
    return redirect(url_for('transcripts.view', id=transcript.id))

@transcripts.route('/transcripts/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    transcript = Transcript.query.get_or_404(id)
    matter_id  = transcript.matter_id
    db.session.delete(transcript)
    db.session.commit()
    log_action(f'Deleted transcript {id}')
    flash('Transcript deleted.', 'success')
    return redirect(url_for('recordings.view_matter', id=matter_id))