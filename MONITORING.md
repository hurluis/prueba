# Monitoreo con Grafana y Prometheus

Este proyecto incluye un stack completo de monitoreo usando Grafana y Prometheus.

## Servicios de Monitoreo

### Prometheus
- **Puerto**: 9090
- **URL**: http://localhost:9090
- **Descripción**: Recolecta métricas de todos los servicios

### Grafana
- **Puerto**: 3000
- **URL**: http://localhost:3000
- **Usuario**: admin
- **Contraseña**: admin
- **Descripción**: Visualización de métricas con dashboards preconfigurds

### Exporters adicionales
- **postgres-exporter** (puerto 9187): Métricas de PostgreSQL
- **node-exporter** (puerto 9100): Métricas del sistema (CPU, memoria, disco)

## Métricas Disponibles

### Aplicación FastAPI
- Tasa de requests por segundo
- Latencia de respuesta (p95, p99)
- Tasa de errores (5xx)
- Requests por endpoint

### Base de Datos PostgreSQL
- Conexiones activas
- Transacciones (commits/rollbacks)
- Tamaño de la base de datos
- Queries por segundo

### Sistema
- Uso de CPU
- Uso de memoria
- Uso de disco
- Network I/O

## Cómo Usar

### 1. Levantar los servicios

```bash
docker-compose up -d
```

### 2. Acceder a Grafana

1. Abrir navegador en http://localhost:3000
2. Login con usuario `admin` y contraseña `admin`
3. El dashboard "FastAPI Application Monitoring" estará disponible automáticamente

### 3. Explorar métricas en Prometheus

Visitar http://localhost:9090 para explorar métricas directamente en Prometheus.

### 4. Endpoints de métricas

- FastAPI metrics: http://localhost:8000/metrics
- PostgreSQL metrics: http://localhost:9187/metrics
- Node metrics: http://localhost:9100/metrics

## Dashboard Preconfigurdo

El dashboard incluye:

1. **Request Rate**: Tasa de peticiones por segundo
2. **Response Time**: Percentiles 95 y 99 de latencia
3. **Error Rate**: Tasa de errores 5xx
4. **Database Connections**: Conexiones activas a PostgreSQL
5. **CPU Usage**: Uso de CPU del sistema
6. **Memory Usage**: Uso de memoria RAM
7. **Database Transactions**: Commits y rollbacks

## Personalización

### Agregar nuevas métricas

Editar `prometheus.yml` para agregar nuevos jobs:

```yaml
scrape_configs:
  - job_name: 'mi-servicio'
    static_configs:
      - targets: ['mi-servicio:puerto']
```

### Crear nuevos dashboards

1. Crear dashboard en Grafana UI
2. Exportar como JSON
3. Guardar en `grafana/dashboards/`
4. Reiniciar Grafana para cargar automáticamente

## Troubleshooting

### Grafana no muestra datos

1. Verificar que Prometheus esté corriendo: `docker ps | grep prometheus`
2. Verificar conectividad: http://localhost:9090/targets
3. Verificar que todos los targets estén "UP"

### Prometheus no recolecta métricas

1. Verificar configuración en `prometheus.yml`
2. Revisar logs: `docker logs prometheus`
3. Verificar que el backend exponga `/metrics`

## Recursos Adicionales

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [FastAPI Instrumentator](https://github.com/trallnag/prometheus-fastapi-instrumentator)
