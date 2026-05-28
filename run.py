from dotenv import load_dotenv
load_dotenv()

from app import create_app, db

app = create_app()

with app.app_context():
    from app.models import User, Matter, Recording, Transcript, AuditLog

    try:
        db.create_all()
    except Exception as e:
        print(f'Warning: db.create_all() failed: {e}')
        print('Tables may already exist — continuing...')

    try:
        from werkzeug.security import generate_password_hash
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                full_name='System Administrator',
                email='admin@dpp.gov.bw',
                role='Admin',
                password=generate_password_hash('Admin@1234'),
                is_active=True
            )
            db.session.add(admin)
            db.session.commit()
            print('Admin created successfully')
        else:
            print('Admin already exists')
    except Exception as e:
        print(f'Warning: Admin check failed: {e}')
        db.session.rollback()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)