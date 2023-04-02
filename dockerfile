FROM python:3.11-alpine
WORKDIR /app
COPY . .
RUN apk add --no-cache bash
RUN pip install -r requirements.txt
CMD /bin/bash /app/start_server.sh