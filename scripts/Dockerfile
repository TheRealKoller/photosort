# Kleines, eigenstaendiges Image fuer den "seed"-Compose-Service (siehe
# docker-compose.demo.yml, specs/decisions/0010-demo-seed-script-as-compose-service.md). Laeuft
# im selben Docker-Netzwerk wie opencloud-demo, damit der dort per OC_URL konfigurierte
# Servicename ("opencloud-demo") fuer alle drei Konsumenten (Backend, Worker, dieses Skript)
# konsistent aufloesbar ist.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY seed-opencloud-demo.py .
COPY demo_photos/ demo_photos/

ENTRYPOINT ["python", "seed-opencloud-demo.py"]
