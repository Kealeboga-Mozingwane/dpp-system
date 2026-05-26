from app import create_app, db

app = create_app()

with app.app_context():
    # Import models FIRST so SQLAlchemy knows what tables to create
    from app.models import User, Matter, Recording, Transcript, AuditLog
    
    # NOW create all tables
    db.create_all()
    
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

if __name__ == '__main__':
    app.run(debug=True)