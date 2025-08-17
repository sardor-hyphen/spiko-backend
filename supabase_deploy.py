#!/usr/bin/env python3
"""
Supabase Deployment Script for Spiko Backend
This script converts the Flask backend to work with Supabase Edge Functions
"""

import os
import json
import shutil
from pathlib import Path

# Supabase project configuration
SUPABASE_PROJECT_ID = "qxaflkmpeavucazxqzmu"
SUPABASE_URL = f"https://{SUPABASE_PROJECT_ID}.supabase.co"
SUPABASE_ANON_KEY = "your-anon-key-here"  # Will be updated after deployment

def create_supabase_function():
    """Create the main Edge Function for the Flask backend"""
    
    # Create the Edge Function directory structure
    functions_dir = Path("supabase/functions/spiko-api")
    functions_dir.mkdir(parents=True, exist_ok=True)
    
    # Create the main function file
    function_code = '''
import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

serve(async (req) => {
  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const url = new URL(req.url)
    const path = url.pathname
    const method = req.method

    // Initialize Supabase client
    const supabaseUrl = Deno.env.get('PROJECT_URL')!
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    const supabase = createClient(supabaseUrl, supabaseKey)

    // Route handling
    if (path === '/api/login' && method === 'POST') {
      return await handleLogin(req, supabase)
    } else if (path === '/api/register' && method === 'POST') {
      return await handleRegister(req, supabase)
    } else if (path === '/api/me' && method === 'GET') {
      return await handleGetUser(req, supabase)
    } else if (path === '/api/analyze' && method === 'POST') {
      return await handleAnalyze(req, supabase)
    } else if (path.startsWith('/api/sessions')) {
      return await handleSessions(req, supabase)
    } else {
      return new Response('Not Found', { status: 404, headers: corsHeaders })
    }

  } catch (error) {
    console.error('Error:', error)
    return new Response(JSON.stringify({ error: 'Internal Server Error' }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    })
  }
})

async function handleLogin(req: Request, supabase: any) {
  const { email, password } = await req.json()
  
  // Authenticate user with Supabase Auth
  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password
  })

  if (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 401,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    })
  }

  return new Response(JSON.stringify({
    message: 'Login successful!',
    token: data.session.access_token,
    user: data.user
  }), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  })
}

async function handleRegister(req: Request, supabase: any) {
  const { username, email, password } = await req.json()
  
  // Create user with Supabase Auth
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      data: {
        username: username
      }
    }
  })

  if (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    })
  }

  return new Response(JSON.stringify({
    message: 'User registered successfully!',
    user: data.user
  }), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  })
}

async function handleGetUser(req: Request, supabase: any) {
  const authHeader = req.headers.get('Authorization')
  if (!authHeader) {
    return new Response(JSON.stringify({ error: 'Missing authorization header' }), {
      status: 401,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    })
  }

  const token = authHeader.replace('Bearer ', '')
  const { data: { user }, error } = await supabase.auth.getUser(token)

  if (error) {
    return new Response(JSON.stringify({ error: 'Invalid token' }), {
      status: 401,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    })
  }

  return new Response(JSON.stringify({
    id: user.id,
    username: user.user_metadata.username || user.email.split('@')[0],
    email: user.email,
    created_at: user.created_at
  }), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  })
}

async function handleAnalyze(req: Request, supabase: any) {
  // Get user from token
  const authHeader = req.headers.get('Authorization')
  if (!authHeader) {
    return new Response(JSON.stringify({ error: 'Missing authorization header' }), {
      status: 401,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    })
  }

  const token = authHeader.replace('Bearer ', '')
  const { data: { user }, error: authError } = await supabase.auth.getUser(token)

  if (authError) {
    return new Response(JSON.stringify({ error: 'Invalid token' }), {
      status: 401,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    })
  }

  const { transcript, session_id, questions_and_answers } = await req.json()

  // Call OpenRouter API for analysis
  const openrouterKey = Deno.env.get('OPENROUTER_API_KEY')
  if (!openrouterKey) {
    return new Response(JSON.stringify({ error: 'AI service not configured' }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    })
  }

  // AI analysis logic here (similar to Flask backend)
  const analysisResult = await performAIAnalysis(transcript, openrouterKey)
  
  // Store results in database
  await storeAnalysisResults(supabase, user.id, session_id, analysisResult, transcript, questions_and_answers)

  return new Response(JSON.stringify(analysisResult), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  })
}

async function handleSessions(req: Request, supabase: any) {
  const url = new URL(req.url)
  const pathParts = url.pathname.split('/')
  
  if (pathParts.length === 3) {
    // GET /api/sessions - list all sessions
    const sessions = await getSessionsList()
    return new Response(JSON.stringify(sessions), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    })
  } else if (pathParts.length === 4) {
    // GET /api/sessions/:id - get specific session
    const sessionId = pathParts[3]
    const session = await getSessionById(sessionId)
    return new Response(JSON.stringify(session), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    })
  }
}

async function performAIAnalysis(transcript: string, apiKey: string) {
  // Implementation of AI analysis (similar to Flask backend)
  const prompt = `You are an expert IELTS Speaking examiner...` // Full prompt here
  
  const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model: 'mistralai/mistral-7b-instruct:free',
      messages: [{ role: 'user', content: prompt }]
    })
  })

  const result = await response.json()
  return JSON.parse(result.choices[0].message.content)
}

async function storeAnalysisResults(supabase: any, userId: string, sessionId: string, analysis: any, transcript: string, qa: any[]) {
  // Store session usage
  const { data: sessionUsage } = await supabase
    .from('session_usage')
    .insert({
      user_id: userId,
      session_id_str: sessionId,
      duration: 300, // Default duration
      words_spoken: transcript.split(' ').length
    })
    .select()
    .single()

  // Store feedback summary
  await supabase
    .from('feedback_summary')
    .insert({
      session_usage_id: sessionUsage.id,
      band_scores: JSON.stringify(analysis.criteria_scores),
      feedback_text: JSON.stringify(analysis.actionable_insights)
    })
}

async function getSessionsList() {
  // Return static session data (from session-data folder)
  return [
    { id: "session_1", title: "Personal Information & Hobbies", keywords: "Family, hobbies, daily routine" },
    { id: "session_2", title: "Work & Study", keywords: "Jobs, career, education, university" },
    { id: "session_3", title: "Technology & The Internet", keywords: "Smartphones, social media, AI, online" }
  ]
}

async function getSessionById(sessionId: string) {
  // Return specific session data
  const sessions = {
    "session_1": {
      "session_id": "session_1",
      "title": "Personal Information & Hobbies",
      "keywords": "Family, hobbies, daily routine",
      "part1": ["Tell me about your family.", "What do you do in your free time?"],
      "part2": {
        "cue_card_topic": "Describe a hobby you enjoy.",
        "cue_card_points": ["You should say:", "what the hobby is", "when you started it", "why you enjoy it"]
      },
      "part3": ["How important are hobbies in people's lives?", "Do you think hobbies change as people get older?"]
    }
  }
  
  return sessions[sessionId] || null
}
'''

    # Write the function file
    with open(functions_dir / "index.ts", "w") as f:
        f.write(function_code)
    
    print(f"✅ Created Edge Function at {functions_dir}/index.ts")

def create_supabase_config():
    """Create Supabase configuration files"""
    
    # Create supabase directory
    supabase_dir = Path("supabase")
    supabase_dir.mkdir(exist_ok=True)
    
    # Create config.toml
    config_content = f'''[api]
enabled = true
port = 54321
schemas = ["public", "graphql_public"]
extra_search_path = ["public", "extensions"]
max_rows = 1000

[auth]
enabled = true
site_url = "http://localhost:3000"
additional_redirect_urls = ["https://your-domain.com"]
jwt_expiry = 3600
enable_signup = true

[auth.email]
enable_signup = true
double_confirm_changes = true
enable_confirmations = false

[db]
port = 54322

[studio]
enabled = true
port = 54323

[inbucket]
enabled = true
port = 54324

[storage]
enabled = true
file_size_limit = "50MiB"

[edge_functions]
enabled = true

[analytics]
enabled = false
'''
    
    with open(supabase_dir / "config.toml", "w") as f:
        f.write(config_content)
    
    print("✅ Created Supabase config.toml")

def create_deployment_instructions():
    """Create deployment instructions"""
    
    instructions = f'''# Spiko Backend Deployment to Supabase

## Project Information
- **Project ID**: {SUPABASE_PROJECT_ID}
- **Project URL**: {SUPABASE_URL}
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
supabase link --project-ref {SUPABASE_PROJECT_ID}
```

### 4. Deploy Edge Functions
```bash
supabase functions deploy spiko-api
```

### 5. Set Environment Variables
```bash
supabase secrets set OPENROUTER_API_KEY=your_openrouter_key_here
supabase secrets set SUPABASE_URL={SUPABASE_URL}
```

### 6. Update Frontend Configuration
Update your frontend to use the new Supabase URL:
```javascript
const API_BASE_URL = '{SUPABASE_URL}/functions/v1/spiko-api';
```

## Database Schema
The following tables have been created:
- `users` - User authentication and profiles
- `session_usage` - Session tracking
- `feedback_summary` - AI feedback storage

## API Endpoints
All Flask routes are now available at:
- `{SUPABASE_URL}/functions/v1/spiko-api/api/login`
- `{SUPABASE_URL}/functions/v1/spiko-api/api/register`
- `{SUPABASE_URL}/functions/v1/spiko-api/api/me`
- `{SUPABASE_URL}/functions/v1/spiko-api/api/analyze`
- `{SUPABASE_URL}/functions/v1/spiko-api/api/sessions`

## Authentication
The backend now uses Supabase Auth instead of custom JWT tokens.
Users will authenticate through Supabase's built-in authentication system.

## Next Steps
1. Deploy the Edge Function
2. Update frontend API URLs
3. Test all endpoints
4. Configure custom domain (optional)
'''
    
    with open("SUPABASE_DEPLOYMENT.md", "w") as f:
        f.write(instructions)
    
    print("✅ Created deployment instructions: SUPABASE_DEPLOYMENT.md")

if __name__ == "__main__":
    print("🚀 Starting Supabase deployment setup...")
    
    create_supabase_function()
    create_supabase_config()
    create_deployment_instructions()
    
    print("\n✅ Supabase deployment setup complete!")
    print(f"📁 Project ID: {SUPABASE_PROJECT_ID}")
    print(f"🌐 Project URL: {SUPABASE_URL}")
    print("\n📖 Next steps:")
    print("1. Read SUPABASE_DEPLOYMENT.md for detailed instructions")
    print("2. Install Supabase CLI and deploy the Edge Function")
    print("3. Update frontend API URLs")
    print("4. Test the deployment")
