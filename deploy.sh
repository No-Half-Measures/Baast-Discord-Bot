#!/bin/bash

# Baast Web Deployment Script
# This script handles the deployment of the Baast web application

set -e

echo "🚀 Starting Baast Web deployment..."

# Configuration
PROJECT_DIR="/home/ubuntu/Baast_Depo"
BACKUP_DIR="/home/ubuntu/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Change to project directory
print_status "Changing to project directory: $PROJECT_DIR"
cd "$PROJECT_DIR" || {
    print_error "Failed to change to project directory: $PROJECT_DIR"
    exit 1
}

# Check if we're in the right directory
if [ ! -f "docker-compose.yaml" ]; then
    print_error "docker-compose.yaml not found in $PROJECT_DIR"
    exit 1
fi

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Backup current database (if running)
# print_status "Creating database backup..."
# if sudo docker compose ps | grep -q "postgres.*Up"; then
#     sudo docker compose exec -T postgres pg_dump -U BAAST_DB_USR live_baast > "$BACKUP_DIR/db_backup_$DATE.sql"
#     print_status "Database backup created: db_backup_$DATE.sql"
# else
#     print_warning "Database not running, skipping backup"
# fi

# Stop existing containers gracefully
print_status "Stopping existing containers..."
sudo docker compose down --timeout 30

# Pull latest code changes (only if this is a git repository)
if [ -d ".git" ]; then
    print_status "Pulling latest changes from Git..."
    git pull origin main || {
        print_warning "Git pull failed or no changes to pull. Continuing deployment..."
    }
else
    print_warning "Not a git repository. Skipping git pull. (Code may be deployed via CI/CD)"
fi

# Build and start containers
print_status "Building and starting containers..."
sudo docker compose up --build -d

# Wait for services to be ready
print_status "Waiting for services to start..."
sleep 10

# Check if services are running
print_status "Checking service status..."
if sudo docker compose ps | grep -q "baast-web.*Up" && sudo docker compose ps | grep -q "baast_bot.*Up"; then
    print_status "✅ All services are running successfully!"
else
    print_error "❌ Some services failed to start. Check logs with: docker compose logs"
    exit 1
fi

# Copy environment file if it doesn't exist
if [ ! -f ".env" ]; then
    if [ -f "env.production" ]; then
        print_status "Copying production environment file..."
        cp env.production .env
    else
        print_warning "No .env file found. Please create one from env.example"
    fi
fi

# Run database migrations
print_status "Running database migrations..."
sudo docker compose exec baast-web python manage.py migrate

# Collect static files
print_status "Collecting static files..."
sudo docker compose exec baast-web python manage.py collectstatic --no-input

# Clean up old Docker images
print_status "Cleaning up old Docker images..."
sudo docker image prune -f

# Show running containers
print_status "Current running containers:"
sudo docker compose ps

print_status "🎉 Deployment completed successfully!"
print_status "Application is available at: https://baast.app"
print_status "Monitoring dashboard: https://monitoring.baast.app"
