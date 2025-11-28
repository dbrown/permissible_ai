"""
Flask application entry point
Uses application factory pattern for better modularity and testing
"""
import os
from app import create_app

# Determine configuration from environment
config_name = os.environ.get('FLASK_ENV', 'development')

# Create application instance
app = create_app(config_name)






if __name__ == '__main__':
    # Run the application
    app.run(host='0.0.0.0', port=5000)
