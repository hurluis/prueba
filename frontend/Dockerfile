FROM nginx:alpine

# Copiar configuración de nginx
COPY nginx.conf /etc/nginx/nginx.conf

# Copiar archivos del frontend (solo HTML/CSS/JS)
COPY . /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
