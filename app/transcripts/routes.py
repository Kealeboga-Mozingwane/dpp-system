from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app.models import Transcript, Recording, Matter, AuditLog
from app import db
from datetime import datetime, timezone

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
    all_transcripts = Transcript.query.order_by(Transcript.created_at.desc()).all()
    return render_template('transcripts/index.html', transcripts=all_transcripts)

@transcripts.route('/transcripts/<int:id>')
@login_required
def view(id):
    transcript = Transcript.query.get_or_404(id)
    return render_template('transcripts/view.html', transcript=transcript)

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
    transcript = Transcript.query.get_or_404(id)
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