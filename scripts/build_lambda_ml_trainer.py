#!/usr/bin/env python3
"""Build Lambda deployment package for ML trainer

This script builds a Lambda deployment package that includes:
- Source code (src/cti_scraper)
- Training scripts (scripts/)
- Dependencies (from requirements.txt)

The package is optimized for Lambda with:
- Platform-specific binaries (manylinux2014_x86_64)
- Only binary packages (no source compilation in Lambda)
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_ZIP = PROJECT_ROOT / "lambda_ml_trainer.zip"
BUILD_DIR = PROJECT_ROOT / "build" / "ml_trainer"


def main():
    print("=" * 70)
    print("Building ML Trainer Lambda Package")
    print("=" * 70)

    # Clean build directory
    if BUILD_DIR.exists():
        print(f"\nCleaning build directory: {BUILD_DIR}")
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True)

    # Install dependencies
    print("\n[1/4] Installing dependencies...")
    print(f"  Target: {BUILD_DIR}")
    try:
        # First, install without platform restrictions to get all dependencies
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "-r", str(PROJECT_ROOT / "requirements.txt"),
            "-t", str(BUILD_DIR),
            "--upgrade"
        ])
        print("  [OK] Dependencies installed")
    except subprocess.CalledProcessError as e:
        print(f"  [ERROR] Failed to install dependencies: {e}")
        sys.exit(1)

    # Copy source code
    print("\n[2/4] Copying source code...")
    src_source = PROJECT_ROOT / "src" / "cti_scraper"
    src_dest = BUILD_DIR / "cti_scraper"

    if src_source.exists():
        shutil.copytree(src_source, src_dest)
        print(f"  [OK] Copied: src/cti_scraper -> cti_scraper/")
    else:
        print(f"  [ERROR] Source directory not found: {src_source}")
        sys.exit(1)

    # Copy scripts (for training code reuse)
    print("\n[3/4] Copying training scripts...")
    scripts_source = PROJECT_ROOT / "scripts"
    scripts_dest = BUILD_DIR / "scripts"

    if scripts_source.exists():
        # Copy only Python files (not build scripts)
        scripts_dest.mkdir(exist_ok=True)
        for script_file in scripts_source.glob("*.py"):
            if not script_file.name.startswith("build_"):
                shutil.copy2(script_file, scripts_dest / script_file.name)
        print(f"  [OK] Copied: scripts/*.py -> scripts/")
    else:
        print(f"  [ERROR] Scripts directory not found: {scripts_source}")

    # Create zip
    print("\n[4/4] Creating deployment package...")
    if OUTPUT_ZIP.exists():
        OUTPUT_ZIP.unlink()

    shutil.make_archive(
        str(OUTPUT_ZIP.with_suffix("")),
        "zip",
        BUILD_DIR
    )

    # Calculate size
    size_mb = OUTPUT_ZIP.stat().st_size / 1024 / 1024

    print(f"  [OK] Package created: {OUTPUT_ZIP.name}")
    print(f"  Size: {size_mb:.1f} MB")

    if size_mb > 50:
        print(f"\n[WARNING] Package size ({size_mb:.1f} MB) is large.")
        print("  Consider using Lambda layers for dependencies.")
    elif size_mb > 250:
        print(f"\n[ERROR] Package size ({size_mb:.1f} MB) exceeds Lambda limit (250 MB).")
        print("  You must use Lambda layers for large dependencies.")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("Build Complete!")
    print("=" * 70)
    print(f"\nNext steps:")
    print(f"  1. Upload to S3 or deploy with Terraform")
    print(f"  2. Set deploy_ml_pipeline = true in terraform.tfvars")
    print(f"  3. Run: cd terraform && terraform apply")


if __name__ == "__main__":
    main()
