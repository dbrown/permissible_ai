"""
Routes package initialization
"""
from app.routes import auth, main, admin, api_keys, api, tee, tee_web, tee_callbacks, datasets_web

__all__ = ['auth', 'main', 'admin', 'api_keys', 'api', 'tee', 'tee_web', 'tee_callbacks', 'datasets_web']
