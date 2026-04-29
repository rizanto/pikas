# Use official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Create directory for static files
RUN mkdir -p /app/staticfiles

# Collect static files
# We set a dummy SECRET_KEY for the collectstatic command if not provided
RUN SECRET_KEY=collectstatic-dummy DEBUG=False python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Run entrypoint script and start gunicorn
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "pikas_project.wsgi:application"]
