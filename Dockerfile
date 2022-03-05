FROM python:3.8-alpine as builder

MAINTAINER Cyril Margaria <cyril.margaria@gmail.com>
# Build deps
RUN cd /usr/src; apk update && apk --no-cache upgrade && apk --no-cache --virtual .build-deps add \
   build-base gcc g++ make libffi-dev python3-dev postgresql-client postgresql-dev musl gcompat
COPY . /usr/src/
RUN pip wheel --wheel-dir=/wheels -r /usr/src/requirements.txt
RUN pip wheel --wheel-dir=/wheels cffi
RUN cd /usr/src; python setup.py bdist_wheel -d /wheels;

FROM python:3.8-alpine
RUN apk update && apk --no-cache add libdiscid postgresql-client
COPY --from=builder /wheels/ /wheels
RUN mkdir -p  /home/arm/db/ /home/arm/media/raw/ /home/arm/logs/  /home/arm/etc/ /home/arm/media/transcode/ /home/arm/media/completed/ /home/arm/files
COPY docs/arm-ui.yaml /home/arm/etc/arm.yml
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
EXPOSE 8080/tcp
RUN pip install -f /wheels /wheels/*.whl 
ENTRYPOINT ["/usr/local/bin/arm-ui", "-c" , "/home/arm/etc/arm.yml"]
