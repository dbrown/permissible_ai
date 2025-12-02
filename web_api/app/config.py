"""
Configuration settings for the Flask application
"""
import os
from datetime import timedelta


class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Google OAuth
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_DISCOVERY_URL = 'https://accounts.google.com/.well-known/openid-configuration'
    
    # GCP Configuration for TEE
    GOOGLE_CLOUD_PROJECT = os.environ.get('GOOGLE_CLOUD_PROJECT') or os.environ.get('GCP_PROJECT')
    GOOGLE_APPLICATION_CREDENTIALS = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    GCP_DEFAULT_ZONE = os.environ.get('GCP_DEFAULT_ZONE', 'us-central1-a')
    GCP_DEFAULT_REGION = os.environ.get('GCP_DEFAULT_REGION', 'us-central1')

    # TEE Service Endpoint
    TEE_SERVICE_ENDPOINT = os.environ.get('TEE_SERVICE_ENDPOINT')
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 
        'postgresql://localhost/permissible_ai'
    )


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SESSION_COOKIE_SECURE = True
    
    # Require environment variables in production
    @classmethod
    def init_app(cls, app):
        if not cls.SQLALCHEMY_DATABASE_URI:
            raise ValueError("DATABASE_URL must be set in production")
        if not cls.GOOGLE_CLIENT_ID or not cls.GOOGLE_CLIENT_SECRET:
            raise ValueError("Google OAuth credentials must be set in production")
        if not cls.TEE_SERVICE_ENDPOINT:
            raise ValueError("TEE_SERVICE_ENDPOINT must be set in production")


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'  # In-memory SQLite for fast tests
    WTF_CSRF_ENABLED = False
    SERVER_NAME = 'localhost.localdomain'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
