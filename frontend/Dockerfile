FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Wird zur Build-Zeit ins statische Bundle eingebacken (Vite liest VITE_-praefigierte
# Prozessumgebungsvariablen automatisch, siehe .env.example) - kein Laufzeit-Konfigurationswert.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
