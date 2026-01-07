#!/usr/bin/env python3
"""Ensure all required dependencies are installed for the research plugin."""

import subprocess
import sys
import shutil


# Required packages: (import_name, pip_name)
REQUIRED_PACKAGES = [
    ("chromadb", "chromadb"),
    ("sentence_transformers", "sentence-transformers"),
    ("trafilatura", "trafilatura"),
    ("bs4", "beautifulsoup4"),
    ("requests", "requests"),
]

# Optional packages
OPTIONAL_PACKAGES = [
    ("yt_dlp", "yt-dlp"),  # For YouTube transcripts
]


def check_and_install_packages(packages: list, optional: bool = False) -> bool:
    """Check for packages and install if missing.
    
    Args:
        packages: List of (import_name, pip_name) tuples
        optional: If True, don't fail on install errors
        
    Returns:
        True if all packages are available
    """
    missing = []
    
    for import_name, pip_name in packages:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)
    
    if not missing:
        return True
    
    label = "optional" if optional else "required"
    print(f"📦 Installing {label} packages: {', '.join(missing)}", file=sys.stderr)
    
    try:
        # Use pip to install missing packages
        cmd = [sys.executable, "-m", "pip", "install", "--quiet"] + missing
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print(f"✅ Installed: {', '.join(missing)}", file=sys.stderr)
            return True
        else:
            if optional:
                print(f"⚠️  Optional packages failed to install: {result.stderr[:100]}", file=sys.stderr)
                return False
            else:
                print(f"❌ Failed to install packages: {result.stderr}", file=sys.stderr)
                print(f"   Try manually: pip install {' '.join(missing)}", file=sys.stderr)
                return False
                
    except subprocess.TimeoutExpired:
        print(f"❌ Installation timed out", file=sys.stderr)
        return False
    except Exception as e:
        print(f"❌ Installation error: {e}", file=sys.stderr)
        return False


def ensure_dependencies() -> bool:
    """Ensure all dependencies are installed.
    
    Returns:
        True if all required dependencies are available
    """
    print("🔍 Checking dependencies...", file=sys.stderr)
    
    # Check required packages
    if not check_and_install_packages(REQUIRED_PACKAGES, optional=False):
        return False
    
    # Check optional packages (don't fail if these don't install)
    check_and_install_packages(OPTIONAL_PACKAGES, optional=True)
    
    # Verify critical imports work
    try:
        import chromadb
        import sentence_transformers
        print("✅ All dependencies ready!", file=sys.stderr)
        return True
    except ImportError as e:
        print(f"❌ Dependency check failed: {e}", file=sys.stderr)
        return False


def main():
    """Run dependency check and report status."""
    success = ensure_dependencies()
    
    if success:
        print("\n✅ Research plugin is ready to use!", file=sys.stderr)
        sys.exit(0)
    else:
        print("\n❌ Some dependencies could not be installed.", file=sys.stderr)
        print("   Please install manually:", file=sys.stderr)
        print("   pip install chromadb sentence-transformers trafilatura beautifulsoup4 requests yt-dlp", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
