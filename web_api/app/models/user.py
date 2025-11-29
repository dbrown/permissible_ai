"""
User and AdminRequest models
"""
from datetime import datetime
from flask_login import UserMixin
from app.extensions import db


class User(UserMixin, db.Model):
    """User model for authentication and authorization"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(255), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255))
    picture = db.Column(db.String(500))
    is_admin = db.Column(db.Boolean, default=False, index=True)
    is_pending_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    admin_requests = db.relationship(
        'AdminRequest', 
        foreign_keys='AdminRequest.user_id',
        backref='user', 
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    reviewed_requests = db.relationship(
        'AdminRequest',
        foreign_keys='AdminRequest.reviewed_by',
        backref='reviewer',
        lazy='dynamic'
    )
    api_keys = db.relationship(
        'APIKey',
        backref='user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    def has_pending_admin_request(self):
        """Check if user has a pending admin request"""
        return self.admin_requests.filter_by(status='pending').first() is not None
    
    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login = datetime.utcnow()
        db.session.commit()


class AdminRequest(db.Model):
    """Admin privilege request model"""
    __tablename__ = 'admin_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status = db.Column(db.String(20), default='pending', index=True)  # pending, approved, rejected
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    reviewed_at = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<AdminRequest {self.user.email} - {self.status}>'
    
    def approve(self, admin_user):
        """Approve the admin request"""
        self.status = 'approved'
        self.reviewed_by = admin_user.id
        self.reviewed_at = datetime.utcnow()
        self.user.is_admin = True
        self.user.is_pending_admin = False
        db.session.commit()
    
    def reject(self, admin_user):
        """Reject the admin request"""
        self.status = 'rejected'
        self.reviewed_by = admin_user.id
        self.reviewed_at = datetime.utcnow()
        self.user.is_pending_admin = False
        db.session.commit()
    
    @classmethod
    def get_pending(cls):
        """Get all pending admin requests"""
        return cls.query.filter_by(status='pending').all()
    
    @classmethod
    def get_recent_approved(cls, limit=10):
        """Get recently approved requests"""
        return cls.query.filter_by(status='approved').order_by(
            cls.reviewed_at.desc()
        ).limit(limit).all()
    
    @classmethod
    def get_recent_rejected(cls, limit=10):
        """Get recently rejected requests"""
        return cls.query.filter_by(status='rejected').order_by(
            cls.reviewed_at.desc()
        ).limit(limit).all()
