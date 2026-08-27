import os
import sys
from flask import Flask, render_template, session, send_from_directory

# Add backend directory and database directory to sys.path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, '..'))
DATABASE_DIR = os.path.join(PROJECT_ROOT, 'database')

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if DATABASE_DIR not in sys.path:
    sys.path.insert(0, DATABASE_DIR)

from init_db import init_db
from models import UserModel, AssignmentModel, db_cursor
from services.auth_service import get_current_user

# Import all Blueprints
from routes.main_routes import main_bp
from routes.auth_routes import auth_bp
from routes.job_routes import job_bp
from routes.application_routes import application_bp
from routes.assignment_routes import assignment_bp
from routes.wallet_routes import wallet_bp
from routes.profile_routes import profile_bp
from routes.review_routes import review_bp
from routes.message_routes import message_bp

def create_app():
    # Ensure database is initialized
    init_db()

    app = Flask(
        __name__,
        template_folder=os.path.join(PROJECT_ROOT, 'frontend', 'templates'),
        static_folder=os.path.join(PROJECT_ROOT, 'frontend', 'static'),
        static_url_path='/static'
    )
    app.secret_key = os.environ.get('SECRET_KEY', 'quickhire-super-secret-key-2026')

    # Explicit static route for Vercel Serverless
    @app.route('/static/<path:filename>')
    def serve_static_files(filename):
        static_dir = os.path.join(PROJECT_ROOT, 'frontend', 'static')
        return send_from_directory(static_dir, filename)

    # Register Blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(job_bp)
    app.register_blueprint(application_bp)
    app.register_blueprint(assignment_bp)
    app.register_blueprint(wallet_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(review_bp)
    app.register_blueprint(message_bp)

    # Context Processors for global template variables
    @app.context_processor
    def inject_global_context():
        current_user = get_current_user()
        current_role = current_user.get('role', 'worker') if current_user else 'worker'
        categories = []
        active_live_gig = None
        awaiting_confirmation_gig = None
        try:
            with db_cursor() as cur:
                cur.execute("SELECT * FROM categories ORDER BY name ASC")
                categories = [dict(r) for r in cur.fetchall()]
            if current_user:
                active_live_gig = AssignmentModel.get_active_in_progress_by_user(current_user['id'])
                if not active_live_gig:
                    awaiting_confirmation_gig = AssignmentModel.get_awaiting_confirmation_by_user(current_user['id'])
        except Exception:
            pass

        return {
            'current_user': current_user,
            'current_role': current_role,
            'all_categories': categories,
            'active_live_gig': active_live_gig,
            'awaiting_confirmation_gig': awaiting_confirmation_gig
        }

    # Error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('base.html', error_message="Page Not Found (404)"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('base.html', error_message="Internal Server Error (500)"), 500

    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
