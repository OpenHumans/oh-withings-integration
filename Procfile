release: python manage.py migrate
web: gunicorn nokia.wsgi --log-file=-
worker: celery -A datauploader worker --concurrency 1
