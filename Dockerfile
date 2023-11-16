# ==============================
FROM registry.access.redhat.com/ubi8/python-38 as appbase
# ==============================

ENV PYTHONUNBUFFERED 1
USER 0
WORKDIR /app
RUN mkdir /entrypoint

RUN yum update -y && yum install -y nc
RUN pip install -U pip

COPY --chown=1001:1001 requirements.txt .
RUN --mount=type=cache,target=/tmp/pip-cache \
    pip install --cache-dir /tmp/pip-cache -r requirements.txt

COPY --chown=1001:1001 requirements-prod.txt .
RUN --mount=type=cache,target=/tmp/pip-cache \
    pip install --cache-dir /tmp/pip-cache -r requirements-prod.txt

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

# Install poppler-utils to get pdftotext, which is used in tests
RUN yum install -y poppler-utils

COPY --chown=1001:1001 requirements-dev.txt /app/requirements-dev.txt
RUN pip install --no-cache-dir -r /app/requirements-dev.txt

ENV DEV_SERVER=1

COPY --chown=1001:1001 . /app/

# required to make compilemessages command work in OpenShift
RUN chmod -R g+w /app/locale && chgrp -R root /app/locale

USER 1001

EXPOSE 8081/tcp

# ==============================
FROM appbase as production
# ==============================

COPY --from=staticbuilder --chown=1001:1001 /app/static /app/static
COPY --chown=1001:1001 . /app/

# required to make compilemessages command work in OpenShift
RUN chmod -R g+w /app/locale && chgrp -R root /app/locale

USER 1001

EXPOSE 8000/tcp
