# Despliegue: AWS App Runner (Backend) + Cloudflare Pages (Frontend)

## 1) Backend en AWS App Runner

### Requisitos
- AWS CLI configurado
- Cuenta ECR para alojar la imagen Docker
- RDS (PostgreSQL) existente

### Pasos
1. Construir y subir imagen a ECR (reemplaza REGION y ACCOUNT_ID):
   ```bash
   aws ecr get-login-password --region REGION | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com
   docker build -t gestion-carteras-api .
   docker tag gestion-carteras-api:latest ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/gestion-carteras-api:latest
   docker push ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/gestion-carteras-api:latest
   ```
2. Crear servicio App Runner:
   - Source: Container registry (ECR)
   - Image: la imagen subida
   - Port: 8000
   - Variables de entorno:
     - `DATABASE_URL=postgresql://USER:PASSWORD@RDS_ENDPOINT:5432/DBNAME`
     - `SECRET_KEY=tu-secret`
     - `CORS_ORIGINS=https://<tu-pages>.pages.dev,https://<tu-dominio>`
   - VPC Connector: conecta a la VPC de tu RDS para acceso privado

3. Probar salud:
   - GET `https://<apprunner-url>/` debe responder JSON de bienvenida

## 2) Frontend en Cloudflare Pages

1. Conectar el repositorio
2. Configuración de build:
   - Build command: `cd gestion_carteras_frontend && npm ci && npm run build`
   - Output directory: `gestion_carteras_frontend/dist`
   - Variables:
     - `    VITE_API_BASE_URL=https://<apprunner-url>`
3. Deploy y prueba (Application tab → Manifest, Service Worker)

## 3) DNS
- Frontend: apunta tu dominio o subdominio a Pages (automático en Cloudflare)
- Backend: si deseas dominio propio, crea CNAME a la URL de App Runner y usa ACM

## 4) Notas
- App Runner queda siempre activo y cercano a RDS → baja latencia
- Pages es gratis y cachea estáticos globalmente
- Cuidado con CORS: añade ambos orígenes del frontend
