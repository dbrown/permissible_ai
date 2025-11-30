"""
TEE (Trusted Execution Environment) models
"""
from datetime import datetime
import enum
from app.extensions import db


class SessionStatus(enum.Enum):
    """Collaboration session lifecycle states"""
    ACTIVE = 'active'
    SUSPENDED = 'suspended'
    CLOSED = 'closed'


class DatasetStatus(enum.Enum):
    """Dataset upload and processing states"""
    PENDING = 'pending'        # Metadata created, waiting for client upload
    UPLOADING = 'uploading'    # Client is uploading encrypted data to TEE
    UPLOADED = 'uploaded'      # Upload complete, TEE processing
    ENCRYPTED = 'encrypted'    # Encrypted at rest in TEE
    AVAILABLE = 'available'    # Ready for queries
    FAILED = 'failed'          # Upload or processing failed
    ERROR = 'error'            # Generic error state


class QueryStatus(enum.Enum):
    """Query processing states"""
    SUBMITTED = 'submitted'
    VERIFYING = 'verifying'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    EXECUTING = 'executing'
    COMPLETED = 'completed'
    ERROR = 'error'


# Association table for collaboration session participants (many-to-many)
session_participants = db.Table('session_participants',
    db.Column('session_id', db.Integer, db.ForeignKey('collaboration_sessions.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('joined_at', db.DateTime, default=datetime.utcnow, nullable=False)
)


# Association table for query approvals (many-to-many)
query_approvals = db.Table('query_approvals',
    db.Column('query_id', db.Integer, db.ForeignKey('queries.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('approved', db.Boolean, nullable=False),
    db.Column('approved_at', db.DateTime, default=datetime.utcnow, nullable=False),
    db.Column('notes', db.Text)
)


class CollaborationSession(db.Model):
    """Collaboration session using shared TEE service"""
    __tablename__ = 'collaboration_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Session Configuration
    allow_cross_party_joins = db.Column(db.Boolean, default=True)
    require_unanimous_approval = db.Column(db.Boolean, default=True)
    
    # Status and Lifecycle
    status = db.Column(db.Enum(SessionStatus), default=SessionStatus.ACTIVE, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    closed_at = db.Column(db.DateTime)
    
    # Relationships
    creator = db.relationship('User', foreign_keys=[creator_id], backref='created_sessions')
    participants = db.relationship('User', secondary=session_participants, backref='participating_sessions')
    datasets = db.relationship('Dataset', backref='session', lazy='dynamic', cascade='all, delete-orphan')
    queries = db.relationship('Query', backref='session', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<CollaborationSession {self.name} - {self.status.value}>'
    
    def to_dict(self):
        """Convert session to dictionary for API responses"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'creator': {
                'id': self.creator.id,
                'email': self.creator.email,
                'name': self.creator.name
            },
            'status': self.status.value,
            'participants': [{
                'id': user.id,
                'email': user.email,
                'name': user.name
            } for user in self.participants],
            'allow_cross_party_joins': self.allow_cross_party_joins,
            'require_unanimous_approval': self.require_unanimous_approval,
            'created_at': self.created_at.isoformat(),
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'dataset_count': self.datasets.count(),
            'query_count': self.queries.count()
        }
    
    def close(self):
        """Close the collaboration session"""
        self.status = SessionStatus.CLOSED
        self.closed_at = datetime.utcnow()
        db.session.commit()
    
    def add_participant(self, user):
        """Add a participant to the session"""
        if user not in self.participants:
            self.participants.append(user)
            db.session.commit()
    
    def is_participant(self, user):
        """Check if user is a participant"""
        return user in self.participants or user.id == self.creator_id


class Dataset(db.Model):
    """Dataset uploaded to a collaboration session"""
    __tablename__ = 'datasets'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('collaboration_sessions.id'), nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    schema_info = db.Column(db.JSON)  # Store column names, types, etc.
    
    # Storage Information
    gcs_bucket = db.Column(db.String(255))
    gcs_path = db.Column(db.String(500))
    encrypted_path = db.Column(db.String(500))
    encryption_key_id = db.Column(db.String(255))  # KMS key ID
    
    # Metadata
    file_size_bytes = db.Column(db.BigInteger)
    row_count = db.Column(db.Integer)
    checksum = db.Column(db.String(255))
    
    # Status
    status = db.Column(db.Enum(DatasetStatus), default=DatasetStatus.UPLOADING, nullable=False, index=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    available_at = db.Column(db.DateTime)
    
    # Relationships
    owner = db.relationship('User', backref='datasets')
    
    def __repr__(self):
        return f'<Dataset {self.name} - {self.status.value}>'
    
    def to_dict(self):
        """Convert Dataset to dictionary for API responses"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'name': self.name,
            'description': self.description,
            'owner': {
                'id': self.owner.id,
                'email': self.owner.email,
                'name': self.owner.name
            },
            'schema': self.schema_info,
            'file_size_bytes': self.file_size_bytes,
            'row_count': self.row_count,
            'status': self.status.value,
            'uploaded_at': self.uploaded_at.isoformat(),
            'available_at': self.available_at.isoformat() if self.available_at else None
        }
    
    def mark_available(self):
        """Mark dataset as available for use"""
        self.status = DatasetStatus.AVAILABLE
        self.available_at = datetime.utcnow()
        db.session.commit()


class Query(db.Model):
    """Query submitted to a collaboration session for execution"""
    __tablename__ = 'queries'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('collaboration_sessions.id'), nullable=False, index=True)
    submitter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    query_text = db.Column(db.Text, nullable=False)
    query_hash = db.Column(db.String(64), index=True)  # SHA256 of query for deduplication
    
    # Trust Verification
    accesses_datasets = db.Column(db.JSON)  # List of dataset IDs accessed
    privacy_level = db.Column(db.String(50))  # e.g., 'aggregate_only', 'full_access'
    verification_notes = db.Column(db.Text)
    
    # Status
    status = db.Column(db.Enum(QueryStatus), default=QueryStatus.SUBMITTED, nullable=False, index=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    approved_at = db.Column(db.DateTime)
    executed_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    # Execution
    execution_time_seconds = db.Column(db.Float)
    error_message = db.Column(db.Text)
    
    # Relationships
    submitter = db.relationship('User', backref='submitted_queries')
    results = db.relationship('QueryResult', backref='query', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Query {self.name} - {self.status.value}>'
    
    def to_dict(self, include_query_text=False):
        """Convert Query to dictionary for API responses"""
        data = {
            'id': self.id,
            'session_id': self.session_id,
            'name': self.name,
            'description': self.description,
            'submitter': {
                'id': self.submitter.id,
                'email': self.submitter.email,
                'name': self.submitter.name
            },
            'accesses_datasets': self.accesses_datasets,
            'privacy_level': self.privacy_level,
            'status': self.status.value,
            'submitted_at': self.submitted_at.isoformat(),
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'execution_time_seconds': self.execution_time_seconds
        }
        if include_query_text:
            data['query_text'] = self.query_text
        if self.error_message:
            data['error_message'] = self.error_message
        return data
    
    def approve(self):
        """Mark query as approved"""
        self.status = QueryStatus.APPROVED
        self.approved_at = datetime.utcnow()
        db.session.commit()
    
    def reject(self, reason):
        """Reject the query"""
        self.status = QueryStatus.REJECTED
        self.verification_notes = reason
        db.session.commit()
    
    def start_execution(self):
        """Mark query as executing"""
        self.status = QueryStatus.EXECUTING
        self.executed_at = datetime.utcnow()
        db.session.commit()
    
    def complete(self, execution_time):
        """Mark query as completed"""
        self.status = QueryStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.execution_time_seconds = execution_time
        db.session.commit()
    
    def get_approval_count(self):
        """Get the number of approvals for this query"""
        from sqlalchemy import select
        result = db.session.execute(
            select(db.func.count()).select_from(query_approvals).where(
                query_approvals.c.query_id == self.id,
                query_approvals.c.approved == True
            )
        )
        return result.scalar()
    
    def user_has_approved(self, user):
        """Check if a specific user has approved this query"""
        result = db.session.execute(
            db.select(query_approvals).where(
                query_approvals.c.query_id == self.id,
                query_approvals.c.user_id == user.id,
                query_approvals.c.approved == True
            )
        )
        return result.first() is not None


class QueryResult(db.Model):
    """Results from a completed query"""
    __tablename__ = 'query_results'
    
    id = db.Column(db.Integer, primary_key=True)
    query_id = db.Column(db.Integer, db.ForeignKey('queries.id'), nullable=False, index=True)
    
    # Result Storage
    result_data = db.Column(db.JSON)  # For small results
    gcs_path = db.Column(db.String(500))  # For large results
    result_format = db.Column(db.String(50))  # json, csv, parquet, etc.
    
    # Metadata
    row_count = db.Column(db.Integer)
    file_size_bytes = db.Column(db.BigInteger)
    checksum = db.Column(db.String(255))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<QueryResult {self.query_id}>'
    
    def to_dict(self, include_data=True):
        """Convert QueryResult to dictionary for API responses"""
        data = {
            'id': self.id,
            'query_id': self.query_id,
            'result_format': self.result_format,
            'row_count': self.row_count,
            'file_size_bytes': self.file_size_bytes,
            'created_at': self.created_at.isoformat()
        }
        if include_data and self.result_data:
            data['result_data'] = self.result_data
        elif self.gcs_path:
            data['download_path'] = f'/api/tee/queries/{self.query_id}/results/{self.id}/download'
        return data
