FROM almalinux:9-minimal as base

USER root

RUN microdnf install \
    --assumeyes \
    --setopt=install_weak_deps=0 \
    --setopt=tsflags=nodocs \
    python3 \
 && microdnf clean all

FROM base as build

COPY requirements.txt /requirements.txt

RUN microdnf install \
    --assumeyes \
    --setopt=install_weak_deps=0 \
    --setopt=tsflags=nodocs \
    python3-pip \
&& microdnf clean all \
&& python3 -m venv /venv \
&& /venv/bin/pip install \
    --disable-pip-version-check \
    -r /requirements.txt \
&& rm /venv/bin/pip*

FROM base

WORKDIR /opt/app

COPY . /opt/app/
COPY --from=build /venv /venv

EXPOSE 80

ENTRYPOINT [ "/venv/bin/python", "nagstamon.py" ]

