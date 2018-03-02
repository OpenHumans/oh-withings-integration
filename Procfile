release: python manage.py migrate
web: gunicorn oh-data-demo-template.wsgi --log-file=-
worker: celery -A datauploader worker --without-gossip --without-mingle --without-heartbeat
worker: celery -A datadownloader worker --without-gossip --without-mingle --without-heartbeat
