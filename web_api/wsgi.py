"""
WSGI entry point for production deployment
"""
import os
from app import create_app

# Create application instance
config_name = os.getenv('FLASK_ENV', 'production')
application = create_app(config_name)
app = application  # For compatibility with different WSGI servers

if __name__ == '__main__':
    # This allows running with `python wsgi.py` for testing
    # In production, use a proper WSGI server like Gunicorn
    port = int(os.environ.get('PORT', 8080))
    application.run(host='0.0.0.0', port=port)
