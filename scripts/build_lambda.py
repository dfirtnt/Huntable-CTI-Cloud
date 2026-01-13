#!/usr/bin/env python3
"""Build Lambda deployment package for CTI Scraper

This script creates a zip file containing:
- Application code (src/cti_scraper/)
- Dependencies from requirements-lambda.txt

Usage:
    python scripts/build_lambda.py

Output:
    lambda_package.zip in project root
"""
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def get_project_root() -> Path:
    """Get project root directory"""
    return Path(__file__).parent.parent


def clean_build_dir(build_dir: Path):
    """Remove existing build directory"""
    if build_dir.exists():
        print(f"Cleaning {build_dir}...")
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True)


def check_docker_available() -> bool:
    """Check if Docker is available"""
    try:
        subprocess.run(["docker", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_dependencies_docker(build_dir: Path, requirements_file: Path, project_root: Path):
    """Install dependencies using Docker for Linux compatibility"""
    print("Using Docker to build Linux-compatible packages...")

    # Use AWS Lambda Python image for exact compatibility
    docker_cmd = [
        "docker", "run", "--rm",
        "-v", f"{project_root}:/var/task",
        "-w", "/var/task",
        "public.ecr.aws/lambda/python:3.11",
        "pip", "install",
        "-r", f"/var/task/{requirements_file.relative_to(project_root)}",
        "-t", f"/var/task/{build_dir.relative_to(project_root)}",
        "--upgrade",
    ]

    subprocess.run(docker_cmd, check=True)


def install_dependencies_pip(build_dir: Path, requirements_file: Path):
    """Install dependencies using pip with platform specification"""
    print("Installing dependencies with pip...")

    # Packages with native extensions that need Linux wheels
    # These MUST be installed with manylinux wheels for Lambda
    native_packages = [
        "pydantic-core==2.14.6",  # Match pydantic 2.5.3
        "pydantic==2.5.3",
        "asyncpg==0.29.0",
        "psycopg2-binary==2.9.9",
        "lxml==5.1.0",
        "aiohttp==3.9.3",
        "greenlet",
        "sqlalchemy==2.0.25",
        "multidict",
        "yarl",
        "frozenlist",
        "propcache",
        "numpy",  # Required by pgvector
    ]

    # Install native packages with platform specification FIRST
    print("Installing native packages with manylinux wheels...")
    native_cmd = [
        sys.executable, "-m", "pip", "install",
        "-t", str(build_dir),
        "--platform", "manylinux2014_x86_64",
        "--implementation", "cp",
        "--python-version", "3.11",
        "--only-binary=:all:",
        "--no-deps",  # Don't install deps yet, we control order
    ] + native_packages

    subprocess.run(native_cmd, check=True)

    # Pure Python packages that are safe to install without platform restriction
    pure_packages = [
        "boto3",
        "botocore",
        "feedparser",
        "beautifulsoup4",
        "soupsieve",
        "chardet",
        "python-dateutil",
        "six",
        "tenacity",
        "pydantic-settings==2.1.0",
        "python-dotenv==1.0.1",
        "typing-extensions",
        "annotated-types",
        "sgmllib3k",
        "attrs",
        "aiosignal",
        "aiohappyeyeballs",
        "idna",
        "jmespath",
        "s3transfer",
        "urllib3",
        "pgvector",  # For PostgreSQL vector extension
        "alembic",  # Database migrations
        "Mako",  # Alembic template engine
    ]

    # Install pure Python packages
    print("Installing pure Python packages...")
    pure_cmd = [
        sys.executable, "-m", "pip", "install",
        "-t", str(build_dir),
        "--no-deps",  # Don't reinstall native packages
    ] + pure_packages

    subprocess.run(pure_cmd, check=True)


def install_dependencies(build_dir: Path, requirements_file: Path, project_root: Path):
    """Install dependencies to build directory"""
    print(f"Installing dependencies from {requirements_file}...")

    # Prefer Docker for guaranteed Linux compatibility
    if check_docker_available():
        try:
            install_dependencies_docker(build_dir, requirements_file, project_root)
            return
        except subprocess.CalledProcessError as e:
            print(f"Docker build failed: {e}")
            print("Falling back to pip with platform specification...")

    # Fallback to pip with platform specification
    try:
        install_dependencies_pip(build_dir, requirements_file)
    except subprocess.CalledProcessError as e:
        print(f"Platform-specific install failed: {e}")
        print("ERROR: Cannot build Linux-compatible packages on this system.")
        print("Please install Docker or build on a Linux system.")
        sys.exit(1)


def copy_source_code(build_dir: Path, src_dir: Path, project_root: Path):
    """Copy application source code to build directory"""
    print(f"Copying source code from {src_dir}...")

    dest_dir = build_dir / "cti_scraper"
    shutil.copytree(
        src_dir / "cti_scraper",
        dest_dir,
        ignore=shutil.ignore_patterns(
            "__pycache__",
            "*.pyc",
            "*.pyo",
            ".pytest_cache",
            "*.egg-info",
        )
    )

    # Copy alembic directory for database migrations
    print("Copying alembic configuration...")
    alembic_src = project_root / "alembic"
    alembic_dest = build_dir / "alembic"
    if alembic_src.exists():
        # Remove existing alembic from pip install if present
        if alembic_dest.exists():
            shutil.rmtree(alembic_dest)
        shutil.copytree(
            alembic_src,
            alembic_dest,
            ignore=shutil.ignore_patterns(
                "__pycache__",
                "*.pyc",
            )
        )

    # Copy alembic.ini
    alembic_ini = project_root / "alembic.ini"
    if alembic_ini.exists():
        shutil.copy(alembic_ini, build_dir / "alembic.ini")


def cleanup_build_dir(build_dir: Path):
    """Remove unnecessary files from build directory"""
    print("Cleaning up unnecessary files...")

    patterns_to_remove = [
        "**/__pycache__",
        "**/*.pyc",
        "**/*.pyo",
        "**/*.dist-info",
        "**/*.egg-info",
        "**/tests",
        "**/test",
        "**/*.so.debug",
    ]

    for pattern in patterns_to_remove:
        for path in build_dir.glob(pattern):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


def create_zip(build_dir: Path, output_file: Path):
    """Create zip file from build directory"""
    print(f"Creating {output_file}...")

    if output_file.exists():
        output_file.unlink()

    with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in build_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(build_dir)
                zf.write(file_path, arcname)

    size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"Created {output_file} ({size_mb:.2f} MB)")

    # Lambda has 50 MB limit for direct upload, 250 MB unzipped
    if size_mb > 50:
        print("WARNING: Package exceeds 50 MB. Consider using S3 for deployment.")


def main():
    project_root = get_project_root()
    build_dir = project_root / "lambda_build"
    src_dir = project_root / "src"
    requirements_file = project_root / "requirements-lambda.txt"
    output_file = project_root / "lambda_package.zip"

    # Check requirements file exists
    if not requirements_file.exists():
        print(f"Creating {requirements_file}...")
        create_lambda_requirements(project_root)

    print("=" * 50)
    print("Building Lambda deployment package")
    print("=" * 50)

    # Build steps
    clean_build_dir(build_dir)
    install_dependencies(build_dir, requirements_file, project_root)
    copy_source_code(build_dir, src_dir, project_root)
    cleanup_build_dir(build_dir)
    create_zip(build_dir, output_file)

    # Cleanup build directory
    print("Cleaning up build directory...")
    shutil.rmtree(build_dir)

    print("=" * 50)
    print("Build complete!")
    print(f"Deploy with: aws lambda update-function-code --function-name <name> --zip-file fileb://{output_file}")
    print("=" * 50)


def create_lambda_requirements(project_root: Path):
    """Create requirements-lambda.txt with Lambda-compatible dependencies"""
    requirements = """# Lambda dependencies for CTI Scraper
# Minimal set for scraping functionality

# AWS SDK (included in Lambda runtime, but pinning for consistency)
boto3>=1.34.69

# Database
sqlalchemy[asyncio]==2.0.25
asyncpg==0.29.0
psycopg2-binary==2.9.9

# Web scraping
feedparser==6.0.11
beautifulsoup4==4.12.3
lxml==5.1.0
aiohttp==3.9.3
chardet==5.2.0

# Utilities
python-dateutil==2.8.2
tenacity==8.2.3
pydantic==2.5.3
pydantic-settings==2.1.0
python-dotenv==1.0.1
"""
    (project_root / "requirements-lambda.txt").write_text(requirements)


if __name__ == "__main__":
    main()
