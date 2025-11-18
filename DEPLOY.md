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

1. Conecta el repositorio
2. Configuración de build:
   - Build command: `cd gestion_carteras_frontend && npm ci && npm run build`
   - Output directory: `gestion_carteras_frontend/dist`

3. Variables y secretos (GitHub Actions)
   - Producción (workflow: `.github/workflows/frontend-cloudflare-pages.yml`):
     - `CF_API_TOKEN` (API Token de Cloudflare con permisos de Pages)
     - `CF_ACCOUNT_ID` (tu Account ID de Cloudflare)
     - `CF_PAGES_PROJECT` (nombre del proyecto de Pages en producción)
     - `VITE_API_BASE_URL` (URL de App Runner prod)
       - Ejemplo: `https://asjiz6txe3.us-east-2.awsapprunner.com`
   - Staging (workflow: `.github/workflows/frontend-staging-cloudflare-pages.yml`):
     - `CF_API_TOKEN` (mismo de arriba)
     - `CF_ACCOUNT_ID` (mismo de arriba)
     - `CF_PAGES_PROJECT_STAGING` (nombre del proyecto de Pages para staging)
     - `VITE_API_BASE_URL_STAGING` (URL de App Runner para staging)
       - Ejemplo: `https://fxs84upa3u.us-east-2.awsapprunner.com/`

4. Notas importantes
   - El frontend ahora exige `VITE_API_BASE_URL` en entornos de despliegue (staging/prod). Si no está definida, el build correrá pero al ejecutar fallará explícitamente. Asegúrate de configurar los secretos anteriores.
   - En desarrollo local, el cliente usa `http://127.0.0.1:8000` si no estableces variable.
   - Verifica CORS en el backend para incluir los orígenes de Pages (staging y prod).

5. Deploy y prueba
   - Tras push a `develop` (staging) o `main` (producción), GitHub Actions construye y publica en Cloudflare Pages.
   - Abre el sitio y valida en DevTools → Network que las solicitudes van al dominio correcto de App Runner.

## 3) DNS
- Frontend: apunta tu dominio o subdominio a Pages (automático en Cloudflare)
- Backend: si deseas dominio propio, crea CNAME a la URL de App Runner y usa ACM

## 4) Notas
- App Runner queda siempre activo y cercano a RDS → baja latencia
- Pages es gratis y cachea estáticos globalmente
- Cuidado con CORS: añade ambos orígenes del frontend
