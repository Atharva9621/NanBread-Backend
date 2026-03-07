# SETUP
```
git clone https://github.com/Atharva9621/NanBread-Backend.git

docker build -t nanbread .
docker run -d --restart unless-stopped --env-file .env -p 8080:8080 --name nanbread-api nanbread
```

```
python -m venv venv
venv/Scripts/activate
pip install -e .
pip install dev_requirements.txt
```

# To run

```
venv/Scripts/activate
python main.py
```
