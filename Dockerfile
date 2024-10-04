ARG  CODE_VERSION=latest
FROM python:3.12.3-bookworm

WORKDIR / firebase-realtime

RUN git clone https://github.com/curiouslearning/realtime-users-app.git .

RUN pip3 install -r requirements.txt

EXPOSE 8080

CMD ["python3", "run", "world-map-server.py", "--server.port=8080"]