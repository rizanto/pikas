#!/bin/sh

# Exit immediately if a command exits with a non-zero status.
set -e

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Creating superuser if it doesn't exist..."
# Using a python one-liner to check and create superuser
python manage.py shell << END
from django.contrib.auth import get_user_model
import os

User = get_user_model()
username = os.getenv('DJANGO_SUPERUSER_USERNAME', 'admin')
password = os.getenv('DJANGO_SUPERUSER_PASSWORD', 'admin')
email = os.getenv('DJANGO_SUPERUSER_EMAIL', 'admin@pikas.com')

if not User.objects.filter(username=username).exists():
    print(f"Creating superuser: {username}")
    User.objects.create_superuser(username, email, password)
else:
    print(f"Superuser {username} already exists.")
END

echo "Starting server..."
exec "$@"
