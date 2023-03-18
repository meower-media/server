FROM python:3.10-alpine
WORKDIR /app
COPY . .
RUN apk add --no-cache bash
RUN pip install -r requirements.txt
CMD /bin/bash /app/startServer.sh