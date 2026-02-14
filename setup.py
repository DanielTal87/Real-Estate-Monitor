#!/usr/bin/env python3
"""
Setup script for Real Estate Monitor
Run this script to set up the application for first use
"""

import os
import sys
from pathlib import Path
import subprocess


def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")


def check_python_version():
    """Check if Python version is 3.9+"""
    print_header("Checking Python Version")
    
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print("❌ Python 3.9 or higher is required!")
        print(f"   Current version: {version.major}.{version.minor}.{version.micro}")
        return False
    
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} detected")
    return True


def create_virtualenv():
    """Create virtual environment"""
    print_header("Creating Virtual Environment")
    
    venv_path = Path("venv")
    
    if venv_path.exists():
        print("⚠️  Virtual environment already exists")
        response = input("   Recreate? (y/N): ").lower()
        if response != 'y':
            print("   Skipping...")
            return True
        
        # Remove old venv
        import shutil
        shutil.rmtree(venv_path)
    
    try:
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print("✅ Virtual environment created")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create virtual environment: {e}")
        return False


def get_pip_command():
    """Get the pip command for current platform"""
    if sys.platform == "win32":
        return str(Path("venv") / "Scripts" / "pip.exe")
    else:
        return str(Path("venv") / "bin" / "pip")


def install_dependencies():
    """Install Python dependencies"""
    print_header("Installing Dependencies")
    
    pip_cmd = get_pip_command()
    
    try:
        # Upgrade pip
        print("Upgrading pip...")
        subprocess.run([pip_cmd, "install", "--upgrade", "pip"], check=True)
        
        # Install requirements
        print("Installing requirements...")
        subprocess.run([pip_cmd, "install", "-r", "requirements.txt"], check=True)
        
        print("✅ Dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False


def install_playwright():
    """Install Playwright browsers"""
    print_header("Installing Playwright Browsers")
    
    if sys.platform == "win32":
        python_cmd = str(Path("venv") / "Scripts" / "python.exe")
    else:
        python_cmd = str(Path("venv") / "bin" / "python")
    
    try:
        subprocess.run([python_cmd, "-m", "playwright", "install", "chromium"], check=True)
        print("✅ Playwright browsers installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install Playwright: {e}")
        return False


def create_env_file():
    """Create .env file from template"""
    print_header("Creating Configuration File")
    
    env_path = Path(".env")
    env_example_path = Path(".env.example")
    
    if env_path.exists():
        print("⚠️  .env file already exists")
        response = input("   Overwrite? (y/N): ").lower()
        if response != 'y':
            print("   Keeping existing .env file")
            return True
    
    if not env_example_path.exists():
        print("❌ .env.example not found")
        return False
    
    # Copy example to .env
    import shutil
    shutil.copy(env_example_path, env_path)
    print("✅ Created .env file")
    print("\n⚠️  IMPORTANT: Edit .env file with your settings!")
    
    return True


def create_directories():
    """Create necessary directories"""
    print_header("Creating Directories")
    
    dirs = ['templates', 'scrapers', 'logs']
    
    for directory in dirs:
        Path(directory).mkdir(exist_ok=True)
    
    print("✅ Directories created")
    return True


def print_activation_instructions():
    """Print instructions for activating virtual environment"""
    print_header("Activation Instructions")
    
    if sys.platform == "win32":
        activate_cmd = "venv\\Scripts\\activate"
    else:
        activate_cmd = "source venv/bin/activate"
    
    print("To activate the virtual environment, run:")
    print(f"\n   {activate_cmd}\n")


def print_next_steps():
    """Print next steps"""
    print_header("Next Steps")
    
    steps = [
        "1. Edit .env file with your preferences",
        "2. (Optional) Set up Telegram bot for notifications",
        "3. (Optional) Extract Facebook cookies for Facebook scraping",
        "4. Run the application: python main.py",
        "5. Open dashboard: http://127.0.0.1:8000"
    ]
    
    for step in steps:
        print(f"   {step}")
    
    print("\n📖 For detailed instructions, see README.md\n")


def main():
    """Main setup function"""
    print("\n" + "🏠" * 20)
    print("   REAL ESTATE MONITOR - SETUP")
    print("🏠" * 20)
    
    # Run setup steps
    steps = [
        ("Python Version", check_python_version),
        ("Virtual Environment", create_virtualenv),
        ("Dependencies", install_dependencies),
        ("Playwright", install_playwright),
        ("Configuration", create_env_file),
        ("Directories", create_directories)
    ]
    
    for step_name, step_func in steps:
        if not step_func():
            print(f"\n❌ Setup failed at: {step_name}")
            print("   Please fix the error and run setup again.")
            return False
    
    # Success!
    print_header("Setup Complete! 🎉")
    
    print_activation_instructions()
    print_next_steps()
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        sys.exit(1)
