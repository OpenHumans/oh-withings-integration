release: python manage.py migrate
web: gunicorn oh-nokiahealth-integration.wsgi --log-file=-
worker: celery worker -A datauploader