#!/bin/bash

# Spiko Backend - Environment Variables Setup Script
# This script sets up all required environment variables in Supabase

echo "🔧 Setting up Supabase environment variables..."

# Check if Supabase CLI is installed
if ! command -v supabase &> /dev/null; then
    echo "❌ Supabase CLI not found. Please install it first:"
    echo "npm install -g supabase"
    exit 1
fi

# Set environment variables
echo "📝 Setting OPENROUTER_API_KEY..."
supabase secrets set OPENROUTER_API_KEY="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"

echo "📝 Setting PROJECT_URL..."
supabase secrets set PROJECT_URL="https://qxaflkmpeavucazxqzmu.supabase.co"

echo "📝 Setting TELEGRAM_BOT_TOKEN..."
supabase secrets set TELEGRAM_BOT_TOKEN="7262255753:AAG3uPFjjjlwjytjPhPXhkX_cGjPsIrTBYk"

echo "📝 Setting TELEGRAM_CHANNEL_USERNAME..."
supabase secrets set TELEGRAM_CHANNEL_USERNAME="https://t.me/SpikoAI"

echo "📝 Setting DEV_UZBEK_OVERRIDE..."
supabase secrets set DEV_UZBEK_OVERRIDE="true"

echo "✅ Environment variables setup complete!"
echo ""
echo "🔍 Verify with: supabase secrets list"
echo "🚀 Deploy function with: supabase functions deploy spiko-api"
