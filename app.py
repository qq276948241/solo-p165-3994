from flask import Flask, jsonify
from config import Config
from models import db
from api.member import member_bp
from api.course import course_bp
from api.checkin import checkin_bp
from api.coach import coach_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    app.register_blueprint(member_bp, url_prefix='/api/member')
    app.register_blueprint(course_bp, url_prefix='/api/course')
    app.register_blueprint(checkin_bp, url_prefix='/api/checkin')
    app.register_blueprint(coach_bp, url_prefix='/api/coach')

    @app.route('/api/health')
    def health_check():
        return jsonify({'status': 'ok', 'message': 'Gym API is running'})

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Resource not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500

    return app


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
