# Permissible.ai - Secure Multi-Party Data Collaboration Platform

A production-ready Flask application enabling secure multi-party data analysis using **Trusted Execution Environments (TEEs)** on Google Cloud Platform. Features Google OAuth authentication, PostgreSQL, and a clean modular architecture optimized for AI coding and maintenance.

## 🔒 Core Purpose

**Permissible.ai** allows multiple parties to securely collaborate on sensitive data analysis without exposing raw data to each other. Using Google Cloud Platform's Confidential Computing:

- 🔐 **Upload encrypted datasets** to a trusted execution environment
- 🔍 **Submit queries** for collaborative analysis
- ✅ **Verify queries** don't violate privacy before execution
- 📊 **Receive results** distributed to all authorized parties
- 🛡️ **TEE attestation** proves code runs in a genuine secure enclave

**Use Cases:**
- Healthcare: Multi-hospital research without sharing patient records
- Finance: Cross-bank fraud detection preserving customer privacy
- Research: Collaborative studies on proprietary datasets
- Government: Inter-agency analytics with data sovereignty

## 🏗️ Architecture Overview

This application follows **Flask and GCP best practices** with a modular structure:

```
web_api/
├── wsgi.py                     # WSGI entry point (production)
├── app.py                      # Development entry point
├── setup.py                    # Package configuration
├── requirements.txt            # Production dependencies
├── requirements-dev.txt        # Development dependencies
├── requirements-test.txt       # Test dependencies
├── pytest.ini                  # Pytest configuration
├── .env.example               # Environment template
│
├── app/                       # Application package
│   ├── __init__.py           # Application factory
│   ├── config.py             # Configuration management
│   ├── extensions.py         # Extension initialization
│   │
│   ├── models/               # Database models (split by domain)
│   │   ├── __init__.py      # Model exports
│   │   ├── user.py          # User and AdminRequest models
│   │   ├── api_key.py       # API key model
│   │   └── tee.py           # TEE, Dataset, Query models
│   │
│   ├── routes/               # Route blueprints
│   │   ├── __init__.py
│   │   ├── auth.py          # Authentication routes
│   │   ├── main.py          # Main routes
│   │   ├── admin.py         # Admin routes
│   │   ├── api_keys.py      # API key management
│   │   ├── api.py           # General API endpoints
│   │   └── tee.py           # TEE API endpoints
│   │
│   ├── services/             # Business logic services
│   │   └── gcp_tee.py       # GCP Confidential Computing integration
│   │
│   ├── utils/                # Utility modules
│   │   └── decorators.py    # Custom decorators
│   │
│   └── templates/            # Jinja2 templates
│       ├── base.html
│       ├── index.html
│       ├── dashboard.html
│       ├── admin_requests.html
│       ├── admin_users.html
│       └── api_keys.html
│
├── docs/                      # Documentation
│   ├── README.md             # Documentation index
│   ├── api/                  # API documentation
│   │   ├── examples.md      # API usage examples
│   │   └── tee.md           # TEE API documentation
│   └── setup/                # Setup guides
│       ├── gcp.md           # GCP setup guide
│       └── testing.md       # Testing guide
│
├── scripts/                   # Utility scripts
│   ├── migrations/           # Database migrations
│   │   ├── migrate_add_api_keys.py
│   │   └── migrate_add_tee.py
│   └── examples/             # Example usage scripts
│       ├── example_api_usage.py
│       └── example_tee_workflow.py
│
├── tests/                     # Test suite
│   ├── __init__.py
│   ├── conftest.py           # Pytest fixtures
│   ├── unit/                 # Unit tests
│   ├── integration/          # Integration tests
│   └── fixtures/             # Test data fixtures
│
└── deployment/                # Deployment configurations
    ├── gcp/                  # GCP deployment
    │   ├── app.yaml         # App Engine config
    │   └── cloudbuild.yaml  # Cloud Build CI/CD
    └── docker/               # Docker deployment
        └── Dockerfile       # Container image
```

## ✨ Key Features

### Trusted Execution Environment (TEE) Platform
- 🔐 **Multi-party secure computation** without data sharing
- 🛡️ **GCP Confidential VM attestation** for trust verification
- 📦 **Encrypted dataset management** with GCP KMS
- ✅ **Query verification workflow** prevents privacy violations
- 📊 **Results distribution** to all authorized participants
- 🔄 **Cross-party data joins** without exposing raw data

### Multi-Tenant Admin System
- ✅ First user automatically becomes administrator
- ✅ Subsequent users can request admin privileges
- ✅ Any admin can approve/reject requests

### Authentication & Security
- ✅ Google OAuth 2.0 integration
- ✅ Secure session management (Flask-Login)
- ✅ Role-based access control
- ✅ CSRF protection
- ✅ PostgreSQL with SQLAlchemy ORM
- ✅ API key management for external access

### Modular Architecture Benefits
- 🔧 **Easy Maintenance**: Each component in its own file
- 🤖 **AI-Friendly**: Clear separation of concerns
- 🧪 **Testable**: Factory pattern enables easy testing
- 📈 **Scalable**: Add new blueprints easily
- 🔄 **Reusable**: Import components across modules

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.8+
- PostgreSQL
- Google OAuth credentials

### 2. Get Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Google+ API
4. Go to "Credentials" → "Create Credentials" → "OAuth client ID"
5. Choose "Web application"
6. Add authorized redirect URIs:
   - `http://localhost:5000/auth/authorize` (for development)
   - Your production URL + `/auth/authorize`
7. Save the Client ID and Client Secret

### 3. Setup Database

```bash
# Install and start PostgreSQL
createdb permissible_ai
```

### 4. Install Dependencies

```bash
cd web_api
pip install -r requirements.txt
```

### 5. Configure Environment

```env
SECRET_KEY=your-secret-key-change-in-production
DATABASE_URL=postgresql://localhost/permissible_ai
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
FLASK_ENV=development
```

### 6. Run Application

```bash
python app.py
```

Visit `http://localhost:5000`

### 7. Run Database Migrations

For new installations, tables are created automatically. For existing installations:

```bash
# Add API key support (if upgrading)
python migrate_add_api_keys.py

# Add TEE functionality
python migrate_add_tee.py
```

## 🔐 TEE API Quick Start

The TEE API enables secure multi-party data collaboration. See [TEE_API_DOCUMENTATION.md](TEE_API_DOCUMENTATION.md) for complete documentation.

### Basic Workflow

```python
import requests

API_KEY = "your-api-key"
headers = {"Authorization": f"Bearer {API_KEY}"}

# 1. Create a TEE
tee = requests.post("http://localhost:5000/api/tee/environments", 
    headers=headers,
    json={
        "name": "Research Collaboration",
        "gcp_project_id": "my-project",
        "gcp_zone": "us-central1-a",
        "participant_emails": ["partner@company.com"]
    }
).json()

# 2. Upload encrypted dataset
dataset = requests.post(f"http://localhost:5000/api/tee/environments/{tee['tee']['id']}/datasets",
    headers=headers,
    json={
        "name": "My Dataset",
        "gcs_bucket": "my-bucket",
        "gcs_path": "data.csv",
        "schema": {"columns": [{"name": "id", "type": "int"}]}
    }
).json()

# 3. Submit query
query = requests.post(f"http://localhost:5000/api/tee/environments/{tee['tee']['id']}/queries",
    headers=headers,
    json={
        "name": "Analysis",
        "query_text": "SELECT COUNT(*) FROM dataset_1",
        "accesses_datasets": [dataset['dataset']['id']],
        "privacy_level": "aggregate_only"
    }
).json()

# 4. Approve query (all participants must approve)
requests.post(f"http://localhost:5000/api/tee/queries/{query['query']['id']}/approve",
    headers=headers,
    json={"notes": "Verified"})

# 5. Get results
results = requests.get(f"http://localhost:5000/api/tee/queries/{query['query']['id']}/results",
    headers=headers).json()
```

Run the complete example:
```bash
python example_tee_workflow.py
```

This will add the `api_keys` table to your existing database.

## 📁 Module Documentation

### `config.py`
Configuration classes for different environments (development, production, testing). Uses environment variables with sensible defaults.

### `app/__init__.py`
Application factory that:
- Creates Flask app instance
- Loads configuration
- Initializes extensions
- Registers blueprints
- Creates database tables

### `app/extensions.py`
Centralized extension initialization for SQLAlchemy, Flask-Login, and Authlib OAuth.

### `app/models.py`
Database models with business logic:
- **User**: Authentication and user management
- **AdminRequest**: Admin privilege workflow
- **APIKey**: API key management for external access
- **TEE**: Trusted Execution Environment instances
- **Dataset**: Encrypted datasets uploaded to TEEs
- **Query**: Analysis queries submitted for execution
- **QueryResult**: Results from completed queries

### `app/decorators.py`
Custom decorators including `@admin_required` and `@api_key_required` for route protection.

### `app/routes/auth.py`
Authentication blueprint handling OAuth login/logout.

### `app/routes/main.py`
Main application routes (landing page, dashboard).

### `app/routes/admin.py`
Admin management routes for users and access requests.

### `app/routes/api_keys.py`
API key management routes for creating, viewing, renaming, and deleting API keys.

### `app/routes/api.py`
General API endpoints (health, user info, etc.).

### `app/routes/tee.py`
**TEE API endpoints** for secure multi-party data collaboration:
- TEE creation and management
- Dataset upload and encryption
- Query submission and approval workflow
- Results distribution
- Attestation verification

### `app/services/gcp_tee.py`
**GCP Confidential Computing integration**:
- Confidential VM creation
- Attestation token verification
- Dataset encryption with KMS
- Query execution in TEE
- Signed URL generation for results
API key management routes for creating, viewing, renaming, and deleting API keys.

### `app/routes/api.py`
API endpoints that require API key authentication for external access.

## 🧪 Testing

This application includes comprehensive tests for all API key functionality.

### Run Tests

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Or use the test runner script
./run_tests.sh coverage
```

### Test Coverage

- ✅ API Key model (creation, validation, relationships)
- ✅ API Key CRUD routes (create, read, update, delete)
- ✅ API authentication (Bearer, X-API-Key, query params)
- ✅ Security features (ownership, permissions, limits)
- ✅ Admin-only endpoints

See [TESTING.md](TESTING.md) for detailed testing documentation.

## 🤖 AI Coding Benefits

This architecture is optimized for AI-assisted development:

1. **Clear Boundaries**: Each file has a single responsibility
2. **Predictable Structure**: AI can easily locate relevant code
3. **Type Hints**: Better AI code suggestions
4. **Docstrings**: AI understands context
5. **Modular**: Changes don't cascade unexpectedly
6. **Factory Pattern**: Easy to mock and test

## Usage

### First User (Administrator)

1. Click "Sign in with Google"
2. Authenticate with your Google account
3. You'll be automatically granted administrator privileges
4. You can now:
   - View all users
   - Approve/reject admin requests
   - Manage the system

### Subsequent Users

1. Sign in with Google
2. Request admin access from the dashboard (optional)
3. Wait for an existing admin to approve your request

### Admin Actions

- **View Admin Requests**: See pending, approved, and rejected requests
- **Approve/Reject Requests**: Manage admin access requests
- **View All Users**: See all registered users and their roles

### API Key Management

All authenticated users can manage their API keys for external API access:

1. Go to Dashboard → "🔑 Manage API Keys"
2. Create a new API key with a descriptive name
3. **Save the key immediately** - it's only shown once!
4. Use the key to authenticate API requests

#### Using API Keys

API keys can be provided in three ways:

1. **Authorization Header (Recommended)**:
   ```bash
   curl -H "Authorization: Bearer YOUR_API_KEY" https://your-domain.com/api/me
   ```

2. **X-API-Key Header**:
   ```bash
   curl -H "X-API-Key: YOUR_API_KEY" https://your-domain.com/api/me
   ```

3. **Query Parameter** (less secure):
   ```bash
   curl https://your-domain.com/api/me?api_key=YOUR_API_KEY
   ```

#### Available API Endpoints

- `GET /api/health` - Public health check (no auth required)
- `GET /api/me` - Get authenticated user information
- `GET /api/users` - List all users (admin only)

#### API Key Security

- Maximum 10 active keys per user
- Keys are only shown once when created
- Keys can be renamed for better organization
- Deactivated keys cannot be reactivated (create a new one)
- Last used timestamp tracks key activity

## Database Schema

### Users Table
- `id`: Primary key
- `google_id`: Unique Google ID
- `email`: User email (unique)
- `name`: Display name
- `picture`: Profile picture URL
- `is_admin`: Admin status
- `is_pending_admin`: Pending admin request flag
- `created_at`: Account creation timestamp
- `last_login`: Last login timestamp

### Admin Requests Table
- `id`: Primary key
- `user_id`: Foreign key to users
- `requested_at`: Request timestamp
- `status`: pending/approved/rejected
- `reviewed_by`: Admin who reviewed (foreign key)
- `reviewed_at`: Review timestamp

### API Keys Table
- `id`: Primary key
- `user_id`: Foreign key to users
- `key`: Unique API key (64 characters)
- `name`: Descriptive name for the key
- `created_at`: Creation timestamp
- `last_used`: Last usage timestamp
- `is_active`: Active status

### TEE Tables

#### tees
- `id`: Primary key
- `name`: TEE name
- `creator_id`: Foreign key to users
- `gcp_instance_id`: GCP Confidential VM identifier
- `attestation_token`: JWT attestation from GCP
- `status`: creating/active/suspended/terminated
- `allow_cross_party_joins`: Boolean
- `require_unanimous_approval`: Boolean

#### datasets
- `id`: Primary key
- `tee_id`: Foreign key to tees
- `owner_id`: Foreign key to users
- `name`: Dataset name
- `gcs_path`: Cloud Storage path
- `encryption_key_id`: KMS key identifier
- `status`: uploading/encrypted/available
- `schema_info`: JSON schema

#### queries
- `id`: Primary key
- `tee_id`: Foreign key to tees
- `submitter_id`: Foreign key to users
- `query_text`: SQL or analysis code
- `accesses_datasets`: JSON array of dataset IDs
- `privacy_level`: aggregate_only/k_anonymized/etc.
- `status`: submitted/approved/executing/completed

#### query_results
- `id`: Primary key
- `query_id`: Foreign key to queries
- `result_data`: JSON results (for small results)
- `gcs_path`: Cloud Storage path (for large results)
- `result_format`: json/csv/parquet

## Security Features

- ✅ Google OAuth 2.0 authentication
- ✅ Session management with Flask-Login
- ✅ CSRF protection
- ✅ SQL injection prevention (SQLAlchemy ORM)
- ✅ Secure password-less authentication
- ✅ Admin-only route protection
- ✅ API key authentication for external access
- ✅ Secure random key generation (48-byte URL-safe tokens)
- ✅ **GCP Confidential Computing** with AMD SEV/Intel TDX
- ✅ **TEE attestation verification** for trusted execution
- ✅ **End-to-end encryption** with GCP KMS
- ✅ **Query verification workflow** prevents privacy violations
- ✅ **Multi-party approval** for data access

## Deployment Considerations

### Production Settings

1. **Set strong SECRET_KEY**: Use a cryptographically secure random string
2. **Use HTTPS**: Always use SSL in production
3. **Update DATABASE_URL**: Use production PostgreSQL credentials
4. **Update OAuth redirect URIs**: Add production URLs to Google Console
5. **Set DEBUG=False**: Disable debug mode in production

### Environment Variables for Production

```env
SECRET_KEY=<strong-random-key>
DATABASE_URL=postgresql://user:password@host:port/database
GOOGLE_CLIENT_ID=<your-client-id>
GOOGLE_CLIENT_SECRET=<your-client-secret>
FLASK_ENV=production

# For TEE functionality (when using real GCP services)
# GCP_PROJECT_ID=<your-gcp-project>
# GCP_DEFAULT_ZONE=us-central1-a
```

### Deployment Platforms

This application can be deployed to:
- **Google Cloud Platform**: **Required** for full TEE functionality (App Engine + Cloud SQL + Confidential Computing)
- **Heroku**: Add PostgreSQL addon (basic features only, no TEE)
- **AWS**: Use RDS for PostgreSQL (basic features only, no TEE)
- **DigitalOcean**: App Platform with managed database (basic features only, no TEE)
- **Railway**: Built-in PostgreSQL support (basic features only, no TEE)

**Important:** Full TEE functionality requires GCP with:
- Confidential Computing (AMD SEV or Intel TDX)
- Cloud KMS for encryption
- Cloud Storage for datasets
- Service account with appropriate permissions

See [GCP_SETUP_GUIDE.md](GCP_SETUP_GUIDE.md) for complete setup instructions.

## File Structure

```
web_api/
├── app.py                 # Main application file
├── requirements.txt       # Python dependencies
├── .env                  # Environment variables (create this)
├── templates/
│   ├── base.html         # Base template
│   ├── index.html        # Landing page
│   ├── dashboard.html    # User dashboard
│   ├── admin_requests.html  # Admin requests management
│   └── admin_users.html  # User management
└── README.md             # This file
```

## API Routes

### Web Routes
- `GET /` - Landing page
- `GET /login` - Initiate Google OAuth
- `GET /authorize` - OAuth callback
- `GET /logout` - Logout user
- `GET /dashboard` - User dashboard (protected)
- `POST /request-admin` - Request admin access (protected)
- `GET /admin/requests` - View admin requests (admin only)
- `POST /admin/approve/<id>` - Approve admin request (admin only)
- `POST /admin/reject/<id>` - Reject admin request (admin only)
- `GET /admin/users` - View all users (admin only)

### API Key Management Routes
- `GET /api-keys/` - List user's API keys (protected)
- `POST /api-keys/create` - Create new API key (protected)
- `POST /api-keys/delete/<id>` - Delete API key (protected)
- `POST /api-keys/rename/<id>` - Rename API key (protected)

### API Endpoints (require API key)
- `GET /api/health` - Health check (public)
- `GET /api/me` - Get authenticated user info
- `GET /api/users` - List all users (admin only)

### TEE API Endpoints (require API key)

See [TEE_API_DOCUMENTATION.md](TEE_API_DOCUMENTATION.md) for complete documentation.

**TEE Management:**
- `GET /api/tee/environments` - List TEEs
- `POST /api/tee/environments` - Create TEE
- `GET /api/tee/environments/{id}` - Get TEE details
- `POST /api/tee/environments/{id}/attestation` - Verify attestation
- `POST /api/tee/environments/{id}/participants` - Add participant
- `POST /api/tee/environments/{id}/terminate` - Terminate TEE

**Dataset Management:**
- `GET /api/tee/environments/{id}/datasets` - List datasets
- `POST /api/tee/environments/{id}/datasets` - Upload dataset
- `GET /api/tee/datasets/{id}` - Get dataset details
- `POST /api/tee/datasets/{id}/mark-available` - Mark available

**Query Management:**
- `GET /api/tee/environments/{id}/queries` - List queries
- `POST /api/tee/environments/{id}/queries` - Submit query
- `GET /api/tee/queries/{id}` - Get query details
- `POST /api/tee/queries/{id}/approve` - Approve query
- `POST /api/tee/queries/{id}/reject` - Reject query

**Results:**
- `GET /api/tee/queries/{id}/results` - Get results
- `GET /api/tee/queries/{qid}/results/{rid}/download` - Download result file
- `GET /api/users` - List all users (admin only)

## License

MIT License - feel free to use this for your own projects!
