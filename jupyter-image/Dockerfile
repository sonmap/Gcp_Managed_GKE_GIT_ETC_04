FROM quay.io/jupyter/base-notebook:latest

USER root
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm -f /tmp/requirements.txt

USER ${NB_UID}
WORKDIR /home/jovyan/work
