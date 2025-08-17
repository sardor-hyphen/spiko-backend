# Spiko Backend Deployment to Supabase

## Project Information
- **Project ID**: qxaflkmpeavucazxqzmu
- **Project URL**: https://qxaflkmpeavucazxqzmu.supabase.co
- **Database**: PostgreSQL (Supabase)

## Deployment Steps

### 1. Install Supabase CLI
```bash
npm install -g supabase
```

### 2. Login to Supabase
```bash
supabase login
```

### 3. Link to your project
```bash
supabase link --project-ref qxaflkmpeavucazxqzmu
```

### 4. Deploy Edge Functions
```bash
supabase functions deploy spiko-api
```

### 5. Set Environment Variables
```bash
supabase secrets set OPENROUTER_API_KEY=your_openrouter_key_here
supabase secrets set PROJECT_URL=https://qxaflkmpeavucazxqzmu.supabase.co
```

### 6. Update Frontend Configuration
Update your frontend to use the new Supabase URL:
```javascript
const API_BASE_URL = 'https://qxaflkmpeavucazxqzmu.supabase.co/functions/v1/spiko-api';
```

## Database Schema
The following tables have been created:
- `users` - User authentication and profiles
- `session_usage` - Session tracking
- `feedback_summary` - AI feedback storage

## API Endpoints
All Flask routes are now available at:
- `https://qxaflkmpeavucazxqzmu.supabase.co/functions/v1/spiko-api/api/login`
- `https://qxaflkmpeavucazxqzmu.supabase.co/functions/v1/spiko-api/api/register`
- `https://qxaflkmpeavucazxqzmu.supabase.co/functions/v1/spiko-api/api/me`
- `https://qxaflkmpeavucazxqzmu.supabase.co/functions/v1/spiko-api/api/analyze`
- `https://qxaflkmpeavucazxqzmu.supabase.co/functions/v1/spiko-api/api/sessions`

## Authentication
The backend now uses Supabase Auth instead of custom JWT tokens.
Users will authenticate through Supabase's built-in authentication system.

## Next Steps
1. Deploy the Edge Function
2. Update frontend API URLs
3. Test all endpoints
4. Configure custom domain (optional)
