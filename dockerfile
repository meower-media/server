FROM python:3-alpine
WORKDIR /app
COPY . .
RUN apk add --no-cache bash make build-base
RUN pip install -r requirements.txt
CMD python main.py
