# ==============================
FROM registry.access.redhat.com/ubi8/python-38 as appbase
# ==============================

ENV PYTHONUNBUFFERED 1
USER 0
WORKDIR /app
RUN mkdir /entrypoint

COPY --chown=1001:1001 requirements.txt /app/requirements.txt
COPY --chown=1001:1001 requirements-prod.txt /app/requirements-prod.txt

RUN yum update -y && yum install -y \
    nc \
    && pip install -U pip \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && pip install --no-cache-dir  -r /app/requirements-prod.txt

COPY --chown=1001:1001 docker-entrypoint.sh /entrypoint/docker-entrypoint.sh
ENTRYPOINT ["/entrypoint/docker-entrypoint.sh"]

# ==============================
FROM appbase as staticbuilder
# ==============================

ENV VAR_ROOT /app
COPY --chown=1001:1001 . /app
RUN SECRET_KEY="only-used-for-collectstatic" python manage.py collectstatic --noinput

# ==============================
FROM appbase as development
# ==============================

COPY --chown=1001:1001 requirements-dev.txt /app/requirements-dev.txt
RUN pip install --no-cache-dir -r /app/requirements-dev.txt

ENV DEV_SERVER=1

COPY --chown=1001:1001 . /app/

USER 1001

RUN django-admin compilemessages

EXPOSE 8081/tcp

# ==============================
FROM appbase as production
# ==============================

COPY --from=staticbuilder --chown=1001:1001 /app/static /app/static
COPY --chown=1001:1001 . /app/

USER 1001

RUN django-admin compilemessages

EXPOSE 8000/tcp
