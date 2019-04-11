FROM ubuntu:xenial

# System dependencies
RUN apt-get update && apt-get install --yes python3-pip net-tools

# Python dependencies
ENV LANG C.UTF-8
RUN pip3 install --upgrade pip
RUN pip3 install gunicorn

# Set revision ID
ARG TALISKER_REVISION_ID
RUN test -n "${TALISKER_REVISION_ID}"
ENV TALISKER_REVISION_ID=$TALISKER_REVISION_ID

# Import code, install code dependencies
WORKDIR /srv
ADD . .
RUN pip3 install -r requirements.txt

# Setup commands to run server
ENTRYPOINT ["./entrypoint"]
CMD ["0.0.0.0:80"]

