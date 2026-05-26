from app import db
from flask_login import UserMixin
from datetime import datetime, timezone
from itsdangerous import URLSafeTimedSerializer
from flask import current_app

def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class User(UserMixin, db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(100), unique=True, nullable=False)
    password   = db.Column(db.String(200), nullable=False)
    role       = db.Column(db.String(50), nullable=False, default='Prosecutor')
    full_name  = db.Column(db.String(200))
    email      = db.Column(db.String(150), unique=True)
    phone      = db.Column(db.String(50))
    is_active  = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_now)
    last_login = db.Column(db.DateTime)
    recordings  = db.relationship('Recording', backref='creator', lazy=True,
                                  foreign_keys='Recording.created_by')

    def get_reset_token(self):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id}, salt='password-reset')

    @staticmethod
    def verify_reset_token(token, max_age=3600):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token, salt='password-reset', max_age=max_age)
        except Exception:
            return None
        return User.query.get(data['user_id'])


class Matter(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    matter_number= db.Column(db.String(100), unique=True, nullable=False)
    title        = db.Column(db.String(200), nullable=False)
    matter_type  = db.Column(db.String(50))
    court        = db.Column(db.String(200))
    accused      = db.Column(db.String(200))
    status       = db.Column(db.String(50), default='Active')
    notes        = db.Column(db.Text)
    created_by   = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at   = db.Column(db.DateTime, default=_now)
    recordings   = db.relationship('Recording', backref='matter', lazy=True)
    transcripts  = db.relationship('Transcript', backref='matter', lazy=True)


class Recording(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    filename     = db.Column(db.String(300), nullable=False)
    original_name= db.Column(db.String(300))
    session_type = db.Column(db.String(100))
    venue        = db.Column(db.String(200))
    officer      = db.Column(db.String(200))
    language     = db.Column(db.String(50), default='English')
    duration     = db.Column(db.Integer)
    file_size    = db.Column(db.Integer)
    matter_id    = db.Column(db.Integer, db.ForeignKey('matter.id'))
    created_by   = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at   = db.Column(db.DateTime, default=_now)
    transcript   = db.relationship('Transcript', backref='recording',
                                   lazy=True, uselist=False)


class Transcript(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    content      = db.Column(db.Text, nullable=False)
    language     = db.Column(db.String(50))
    matter_id    = db.Column(db.Integer, db.ForeignKey('matter.id'))
    recording_id = db.Column(db.Integer, db.ForeignKey('recording.id'))
    created_by   = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at   = db.Column(db.DateTime, default=_now)
    updated_at   = db.Column(db.DateTime, default=_now, onupdate=_now)
    is_approved  = db.Column(db.Boolean, default=False)
    approved_by  = db.Column(db.Integer, db.ForeignKey('user.id'))
    approved_at  = db.Column(db.DateTime)
    author       = db.relationship('User', foreign_keys=[created_by])
    approver     = db.relationship('User', foreign_keys=[approved_by])


class AuditLog(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(100))
    role       = db.Column(db.String(50))
    action     = db.Column(db.String(500))
    ip_address = db.Column(db.String(50))
    timestamp  = db.Column(db.DateTime, default=_now)