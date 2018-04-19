release: python manage.py migrate
web: gunicorn nokia.wsgi --log-file=-
worker: celery worker -A datauploader
