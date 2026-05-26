from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user
from app.models import Matter, Recording, Transcript, AuditLog
from app import db
import os, uuid
from datetime import datetime, timezone

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

def transcribe_audio(file_path, language='English'):
    """
    Transcribe audio using available provider.
    Controlled by TRANSCRIPTION_PROVIDER env var:
      groq   — Groq Whisper API (free tier, default)
      openai — OpenAI Whisper API (paid)
      local  — Self-hosted Whisper on DPP servers
    Language:
      English  — passes 'en' to Whisper
      Setswana — passes None (auto-detect, best results)
      Mixed    — passes None (auto-detect)
    """
    provider = os.environ.get('TRANSCRIPTION_PROVIDER', 'groq').lower()
    lang_map = {
        'English':  'en',
        'Setswana': None,
        'Mixed':    None,
    }
    whisper_lang = lang_map.get(language, 'en')

    if provider == 'groq':
        return _transcribe_groq(file_path, whisper_lang)
    elif provider == 'openai':
        return _transcribe_openai(file_path, whisper_lang)
    elif provider == 'local':
        return _transcribe_local(file_path, whisper_lang)
    else:
        return None, f'Unknown transcription provider: {provider}'


def _transcribe_groq(file_path, whisper_lang):
    """Groq Whisper Large V3 — free tier, fast"""
    api_key = os.environ.get('GROQ_API_KEY')
    if not api_key:
        return None, 'GROQ_API_KEY not configured in environment'
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        with open(file_path, 'rb') as f:
            kwargs = {
                'model'          : 'whisper-large-v3',
                'file'           : f,
                'response_format': 'text',
            }
            if whisper_lang:
                kwargs['language'] = whisper_lang
            response = client.audio.transcriptions.create(**kwargs)
        return response, None
    except Exception as e:
        return None, str(e)


def _transcribe_openai(file_path, whisper_lang):
    """OpenAI Whisper API — paid, reliable"""
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return None, 'OPENAI_API_KEY not configured in environment'
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        with open(file_path, 'rb') as f:
            kwargs = {
                'model': 'whisper-1',
                'file' : f,
            }
            if whisper_lang:
                kwargs['language'] = whisper_lang
            response = client.audio.transcriptions.create(**kwargs)
        return response.text, None
    except Exception as e:
        return None, str(e)


def _transcribe_local(file_path, whisper_lang):
    """
    Self-hosted Whisper on DPP government servers.
    Set LOCAL_WHISPER_URL to the server endpoint.
    e.g. http://dpp-server-ip:9000/asr
    """
    import requests as req
    url = os.environ.get('LOCAL_WHISPER_URL', 'http://localhost:9000/asr')
    try:
        with open(file_path, 'rb') as f:
            params = {}
            if whisper_lang:
                params['language'] = whisper_lang
            response = req.post(
                url,
                files  ={'audio_file': f},
                params =params,
                timeout=300
            )
        if response.status_code == 200:
            return response.text, None
        return None, f'Local Whisper returned status {response.status_code}'
    except Exception as e:
        return None, str(e)


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
    matter_id     = request.args.get('matter_id', type=int)
    matter        = Matter.query.get_or_404(matter_id) if matter_id else None
    ai_transcript = None

    if request.method == 'POST':
        matter_id  = request.form.get('matter_id', type=int)
        matter     = Matter.query.get_or_404(matter_id)
        source     = request.form.get('source', 'live')
        filename   = None
        file_size  = None
        language   = request.form.get('language', 'English')

        if source == 'upload':
            file = request.files.get('audio_file')
            if file and allowed_file(file.filename):
                ext         = file.filename.rsplit('.',1)[1].lower()
                filename    = f"{uuid.uuid4().hex}.{ext}"
                upload_path = os.path.join(
                    current_app.config['UPLOAD_FOLDER'], filename)
                os.makedirs(os.path.dirname(upload_path), exist_ok=True)
                file.save(upload_path)
                file_size = os.path.getsize(upload_path)

                ai_transcript, error = transcribe_audio(upload_path, language)
                if error:
                    flash(f'AI transcription failed: {error}', 'warning')
            else:
                flash('Invalid or missing audio file.', 'danger')
                return redirect(request.url)

        r = Recording(
            filename      = filename or f"live_{uuid.uuid4().hex}.txt",
            original_name = file.filename if source == 'upload' and file else 'Live Recording',
            session_type  = request.form.get('sessionType') or request.form.get(
                'session_type', 'Court Hearing'),
            venue         = request.form.get('venue', '').strip(),
            officer       = request.form.get('officer', '').strip(),
            language      = language,
            duration      = request.form.get('duration', type=int),
            file_size     = file_size,
            matter_id     = matter.id,
            created_by    = current_user.id
        )
        db.session.add(r)
        db.session.flush()

        transcript_content = request.form.get('transcript_content', '').strip()
        final_content      = None

        if source == 'upload' and ai_transcript:
            final_content = ai_transcript
        elif transcript_content:
            final_content = transcript_content

        if final_content:
            t = Transcript(
                content      = final_content,
                language     = language,
                matter_id    = matter.id,
                recording_id = r.id,
                created_by   = current_user.id
            )
            db.session.add(t)

        db.session.commit()
        log_action(f'Added recording to matter {matter.matter_number}')

        provider = os.environ.get('TRANSCRIPTION_PROVIDER', 'groq').upper()
        if source == 'upload' and ai_transcript:
            flash(f'Recording uploaded and transcribed by {provider} AI — Whisper Large V3.', 'success')
        else:
            flash('Recording saved successfully.', 'success')

        return redirect(url_for('recordings.view_matter', id=matter.id))

    return render_template('recordings/new_recording.html', matter=matter)


@recordings.route('/recordings/<int:id>')
@login_required
def view_recording(id):
    recording = Recording.query.get_or_404(id)
    return render_template('recordings/view_recording.html', recording=recording)