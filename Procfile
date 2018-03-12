release: python manage.py migrate
web: gunicorn oh-nokiahealth-integration.wsgi --log-file=-
worker: celery -A datauploader worker --without-gossip --without-mingle --without-heartbeat
