# Permissible.ai - Modular OAuth Application

A production-ready Flask application with Google OAuth authentication and PostgreSQL, featuring a clean modular architecture optimized for AI coding and maintenance.

## 🏗️ Architecture Overview

This application follows **Flask best practices** with a modular structure:

```
web_api/
├── app.py                      # Application entry point
├── config.py                   # Configuration management
├── requirements.txt            # Dependencies
├── .env.example               # Environment template
├── .gitignore                 # Git ignore rules
├── README.md                  # This file
│
└── app/                       # Application package
    ├── __init__.py           # Application factory
    ├── extensions.py         # Extension initialization
    ├── models.py             # Database models
    ├── decorators.py         # Custom decorators
    │
    ├── routes/               # Route blueprints
    │   ├── __init__.py
    │   ├── auth.py          # Authentication routes
    │   ├── main.py          # Main routes
    │   ├── admin.py         # Admin routes
    │   ├── api_keys.py      # API key management
    │   └── api.py           # API endpoints
    │
    └── templates/            # Jinja2 templates
        ├── base.html
        ├── index.html
        ├── dashboard.html
        ├── admin_requests.html
        ├── admin_users.html
        └── api_keys.html
```

## ✨ Key Features

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

### 7. (Optional) Run Migration for Existing Installations

If you're upgrading from a previous version without API key support:

```bash
python migrate_add_api_keys.py
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

### `app/decorators.py`
Custom decorators including `@admin_required` for route protection.

### `app/routes/auth.py`
Authentication blueprint handling OAuth login/logout.

### `app/routes/main.py`
Main application routes (landing page, dashboard).

### `app/routes/admin.py`
Admin management routes for users and access requests.

### `app/routes/api_keys.py`
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

## Security Features

- ✅ Google OAuth 2.0 authentication
- ✅ Session management with Flask-Login
- ✅ CSRF protection
- ✅ SQL injection prevention (SQLAlchemy ORM)
- ✅ Secure password-less authentication
- ✅ Admin-only route protection
- ✅ API key authentication for external access
- ✅ Secure random key generation (48-byte URL-safe tokens)

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
```

### Deployment Platforms

This application can be deployed to:
- **Heroku**: Add PostgreSQL addon
- **AWS**: Use RDS for PostgreSQL
- **Google Cloud**: Use Cloud SQL
- **DigitalOcean**: App Platform with managed database
- **Railway**: Built-in PostgreSQL support

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

## License

MIT License - feel free to use this for your own projects!
