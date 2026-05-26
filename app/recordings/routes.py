from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user
from app.models import Matter, Recording, Transcript, AuditLog
from app import db
import os, uuid
from datetime import datetime, timezone
from werkzeug.utils import secure_filename

recordings = Blueprint('recordings', __name__)

ALLOWED = {'mp3','wav','m4a','ogg','mp4','webm','flac','aac'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED

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

@recordings.route('/matters')
@login_required
def matters():
    all_matters = Matter.query.order_by(Matter.created_at.desc()).all()
    return render_template('recordings/matters.html', matters=all_matters)

@recordings.route('/matters/new', methods=['GET','POST'])
@login_required
def new_matter():
    if request.method == 'POST':
        existing = Matter.query.filter_by(
            matter_number=request.form['matter_number'].strip()).first()
        if existing:
            flash('Matter number already exists.', 'danger')
            return redirect(url_for('recordings.new_matter'))
        m = Matter(
            matter_number = request.form['matter_number'].strip().upper(),
            title         = request.form['title'].strip(),
            matter_type   = request.form.get('matter_type'),
            court         = request.form.get('court'),
            accused       = request.form.get('accused','').strip(),
            status        = request.form.get('status','Active'),
            notes         = request.form.get('notes','').strip(),
            created_by    = current_user.id
        )
        db.session.add(m)
        db.session.commit()
        log_action(f'Created matter {m.matter_number}')
        flash(f'Matter {m.matter_number} created successfully.', 'success')
        return redirect(url_for('recordings.view_matter', id=m.id))
    return render_template('recordings/new_matter.html')

@recordings.route('/matters/<int:id>')
@login_required
def view_matter(id):
    matter = Matter.query.get_or_404(id)
    return render_template('recordings/view_matter.html', matter=matter)

@recordings.route('/recordings')
@login_required
def index():
    all_recordings = Recording.query.order_by(Recording.created_at.desc()).all()
    return render_template('recordings/index.html', recordings=all_recordings)

@recordings.route('/recordings/new', methods=['GET','POST'])
@login_required
def new_recording():
    matter_id = request.args.get('matter_id', type=int)
    matter = Matter.query.get_or_404(matter_id) if matter_id else None

    if request.method == 'POST':
        matter_id = request.form.get('matter_id', type=int)
        matter    = Matter.query.get_or_404(matter_id)
        source    = request.form.get('source', 'live')
        filename  = None
        file_size = None

        if source == 'upload':
            file = request.files.get('audio_file')
            if file and allowed_file(file.filename):
                ext      = file.filename.rsplit('.',1)[1].lower()
                filename = f"{uuid.uuid4().hex}.{ext}"
                upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                os.makedirs(os.path.dirname(upload_path), exist_ok=True)
                file.save(upload_path)
                file_size = os.path.getsize(upload_path)
            else:
                flash('Invalid or missing audio file.', 'danger')
                return redirect(request.url)

        r = Recording(
            filename     = filename or f"live_{uuid.uuid4().hex}.txt",
            original_name= request.form.get('audio_file.filename','Live Recording'),
            session_type = request.form.get('sessionType') or request.form.get('session_type','Court Hearing'),
            venue        = request.form.get('venue','').strip(),
            officer      = request.form.get('officer','').strip(),
            language     = request.form.get('language','English'),
            duration     = request.form.get('duration', type=int),
            file_size    = file_size,
            matter_id    = matter.id,
            created_by   = current_user.id
        )
        db.session.add(r)
        db.session.flush()

        transcript_content = request.form.get('transcript_content','').strip()
        if transcript_content:
            t = Transcript(
                content      = transcript_content,
                language     = r.language,
                matter_id    = matter.id,
                recording_id = r.id,
                created_by   = current_user.id
            )
            db.session.add(t)

        db.session.commit()
        log_action(f'Added recording to matter {matter.matter_number}')
        flash('Recording saved successfully.', 'success')
        return redirect(url_for('recordings.view_matter', id=matter.id))

    return render_template('recordings/new_recording.html', matter=matter)

@recordings.route('/recordings/<int:id>')
@login_required
def view_recording(id):
    recording = Recording.query.get_or_404(id)
    return render_template('recordings/view_recording.html', recording=recording)