FROM python:3.11-slim

WORKDIR /app

# install deps first (cached layer — only rebuilds if requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy project and install as editable package
COPY . .
RUN pip install --no-cache-dir -e .

# stdlib logging only — Rich doesn't play well headless
ENV USE_RICH_LOGGING=false
ENV LOCAL=DOCKER
EXPOSE 5000

CMD ["python", "app.py"]