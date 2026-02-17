# Guía de Despliegue

## 🐳 Despliegue con Docker

### Requisitos
- Docker
- Docker Compose (opcional)

### Opción 1: Docker Compose (Recomendado)

```bash
# 1. Configurar variables de entorno
cp .env.example .env
# Editar .env y agregar GEMINI_API_KEY

# 2. Construir e iniciar
docker-compose up --build

# 3. Verificar que está corriendo
curl http://localhost:8000/health

# 4. Detener
docker-compose down
```

### Opción 2: Docker Manual

```bash
# 1. Construir imagen
docker build -t form-filler:latest .

# 2. Ejecutar contenedor
docker run -d \
  -p 8000:8000 \
  -e GEMINI_API_KEY=tu_clave_aqui \
  -v $(pwd)/temp:/app/temp \
  --name form-filler \
  form-filler:latest

# 3. Ver logs
docker logs -f form-filler

# 4. Detener
docker stop form-filler
docker rm form-filler
```

## ☁️ Despliegue en la Nube

### Google Cloud Run

```bash
# 1. Crear proyecto en Google Cloud
gcloud projects create form-filler

# 2. Autenticar
gcloud auth login

# 3. Configurar proyecto
gcloud config set project form-filler

# 4. Desplegar
gcloud run deploy form-filler \
  --source . \
  --platform managed \
  --region us-central1 \
  --set-env-vars GEMINI_API_KEY=tu_clave_aqui \
  --allow-unauthenticated

# 5. Obtener URL del servicio
gcloud run services describe form-filler
```

### AWS (EC2)

```bash
# 1. Conectarse a instancia EC2
ssh -i tu_key.pem ec2-user@tu_ip

# 2. Instalar dependencias
sudo yum update -y
sudo yum install -y python3.11 pip git

# 3. Clonar repositorio
git clone <tu_repo> form-filler
cd form-filler

# 4. Crear entorno virtual
python3.11 -m venv venv
source venv/bin/activate

# 5. Instalar dependencias
pip install -r requirements.txt

# 6. Configurar .env
cp .env.example .env
echo "GEMINI_API_KEY=tu_clave" >> .env

# 7. Iniciar con supervisor o systemd
# Opción A: Con supervisor
sudo yum install -y supervisor
sudo tee /etc/supervisord.d/form-filler.conf > /dev/null <<EOF
[program:form-filler]
directory=/home/ec2-user/form-filler
command=/home/ec2-user/form-filler/venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000
user=ec2-user
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/form-filler.log
EOF

sudo systemctl start supervisord
sudo systemctl enable supervisord

# Opción B: Con systemd
sudo tee /etc/systemd/system/form-filler.service > /dev/null <<EOF
[Unit]
Description=Form Filler Service
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/form-filler
ExecStart=/home/ec2-user/form-filler/venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl start form-filler
sudo systemctl enable form-filler
```

### Heroku (Deprecated - usar alternativa)

**Nota**: Heroku descontinuó planes gratuitos. Alternativas:
- Render.com
- Railway.app
- Fly.io

### Render.com

```bash
# 1. Crear cuenta en https://render.com

# 2. Conectar repositorio GitHub

# 3. Crear nuevo Web Service
# - Repository: Tu repo
# - Runtime: Python 3.11
# - Build command: pip install -r requirements.txt
# - Start command: uvicorn src.main:app --host 0.0.0.0 --port 10000

# 4. Configurar variables de entorno
# - GEMINI_API_KEY: tu_clave
# - PORT: 10000 (si es necesario)

# 5. Deploy automático desde Git
```

## 🔧 Producción - Recomendaciones

### 1. Usar Gunicorn + Uvicorn

```bash
pip install gunicorn

# Ejecutar con Gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker src.main:app
```

### 2. Usar Nginx como Reverse Proxy

```nginx
server {
    listen 80;
    server_name tu_dominio.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Aumentar timeouts para archivos grandes
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }
}
```

### 3. SSL/TLS con Let's Encrypt

```bash
sudo certbot certonly --standalone -d tu_dominio.com

# Configurar Nginx para HTTPS
# (ver sección anterior actualizada)
```

### 4. Logging y Monitoring

```python
# Agregar en src/main.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Status: {response.status_code}")
    return response
```

### 5. Rate Limiting

```bash
pip install slowapi

# En src/main.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/fill-document")
@limiter.limit("10/minute")
async def fill_document(...):
    ...
```

### 6. Backup y Recuperación

```bash
# Backup de archivos importantes
# (aunque los temps se limpian automáticamente)

# Monitorear espacio en disco
df -h /path/to/temp

# Limpiar archivos antiguos (cron job)
# Agregar a crontab:
0 2 * * * /path/to/cleanup.sh
```

Donde cleanup.sh:
```bash
#!/bin/bash
find /app/temp -type f -mtime +1 -delete
```

## 📊 Monitoreo

### Health Check Recomendado

```bash
curl -s http://localhost:8000/health | grep -q "ok" && echo "OK" || echo "DOWN"
```

### Métricas con Prometheus (Opcional)

```bash
pip install prometheus-fastapi-instrumentator

# En src/main.py
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)

# Acceder a métricas en: http://localhost:8000/metrics
```

## 🚀 Checklist Despliegue a Producción

- [ ] .env configurado con GEMINI_API_KEY segura
- [ ] Base de datos (si aplica) respaldada
- [ ] CORS configurado correctamente
- [ ] Rate limiting habilitado
- [ ] Logging configurado
- [ ] SSL/TLS configurado
- [ ] Monitoreo y alertas configuradas
- [ ] Backup automático programado
- [ ] Plan de recuperación ante desastres
- [ ] Documentación de despliegue actualizada
- [ ] Tests ejecutados exitosamente
- [ ] Revisión de seguridad completada

## ⚠️ Consideraciones de Seguridad

1. **Variables de Entorno**
   - Nunca commitear .env
   - Usar secretos de la plataforma (Google Cloud Secrets, AWS Secrets Manager)

2. **API Key de Gemini**
   - Rotar regularmente
   - Monitorear uso
   - Limitar a IP específicas si es posible

3. **Archivos Temporales**
   - Limpiar regularmente
   - Considerar cifrado de datos en reposo
   - Auditar acceso a archivos

4. **Rate Limiting**
   - Implementar para evitar abuso
   - Considerar autenticación (JWT, OAuth)

5. **HTTPS**
   - Obligatorio en producción
   - Certificados válidos y actualizados

6. **Validación de Entrada**
   - Verificar tipo y tamaño de archivo
   - Validar JSON
   - Sanitizar paths

## 📞 Soporte Despliegue

Para cada plataforma:
- Google Cloud Run: https://cloud.google.com/run/docs
- AWS: https://aws.amazon.com/ec2/
- Render.com: https://render.com/docs
- Docker: https://docs.docker.com/
