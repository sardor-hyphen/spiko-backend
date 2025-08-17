import subprocess
import os
import sys

def check_prerequisites():
    """Check if required tools are installed"""
    
    # Check Node.js
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True)
        print(f"✅ Node.js found: {result.stdout.strip()}")
    except FileNotFoundError:
        print("❌ Node.js not found. Please install Node.js first:")
        print("   Download from: https://nodejs.org/")
        return False
    
    # Check npm
    try:
        result = subprocess.run(['npm', '--version'], capture_output=True, text=True)
        print(f"✅ npm found: {result.stdout.strip()}")
    except FileNotFoundError:
        print("❌ npm not found. Please install Node.js first.")
        return False
    
    return True

def install_supabase_cli():
    """Install Supabase CLI"""
    try:
        print("📦 Installing Supabase CLI...")
        result = subprocess.run(['npm', 'install', '-g', 'supabase'], 
                              capture_output=True, text=True, check=True)
        print("✅ Supabase CLI installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install Supabase CLI: {e}")
        print("Output:", e.stdout)
        print("Error:", e.stderr)
        return False

def deploy_supabase_edge_function():
    """Deploy Supabase Edge Function using Python subprocess"""
    
    print("📁 Current directory:", os.getcwd())
    
    # Check prerequisites
    if not check_prerequisites():
        return
    
    try:
        # Check if Supabase CLI is installed
        try:
            result = subprocess.run(['supabase', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ Supabase CLI found: {result.stdout.strip()}")
            else:
                raise FileNotFoundError()
        except FileNotFoundError:
            print("❌ Supabase CLI not found. Installing...")
            if not install_supabase_cli():
                return
        
        # Login to Supabase (this will open browser for authentication)
        print("🔐 Logging in to Supabase...")
        print("   This will open a browser window for authentication...")
        subprocess.run(['supabase', 'login'], check=True)
        
        # Link to project
        print("🔗 Linking to project...")
        subprocess.run(['supabase', 'link', '--project-ref', 'qxaflkmpeavucazxqzmu'], check=True)
        
        # Deploy Edge Function
        print("🚀 Deploying Edge Function...")
        subprocess.run(['supabase', 'functions', 'deploy', 'spiko-api'], check=True)
        
        # Set environment variables
        print("⚙️ Setting environment variables...")
        env_vars = {
            'OPENROUTER_API_KEY': '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',
            'PROJECT_URL': 'https://qxaflkmpeavucazxqzmu.supabase.co',
            'TELEGRAM_BOT_TOKEN': '7262255753:AAG3uPFjjjlwjytjPhPXhkX_cGjPsIrTBYk',
            'TELEGRAM_CHANNEL_USERNAME': 'https://t.me/SpikoAI',
            'DEV_UZBEK_OVERRIDE': 'true'
        }
        
        for key, value in env_vars.items():
            subprocess.run(['supabase', 'secrets', 'set', f'{key}={value}'], check=True)
            print(f"✅ Set {key}")
        
        print("🎉 Deployment completed successfully!")
        print("🌐 Your API is now live at: https://qxaflkmpeavucazxqzmu.supabase.co/functions/v1/spiko-api/api/")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Deployment failed: {e}")
        if e.stdout:
            print("Output:", e.stdout)
        if e.stderr:
            print("Error:", e.stderr)
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    deploy_supabase_edge_function()