Steps
Create virtual environment and activate.
Install python dependencies


python3 -m venv env

<!-- virtualenv -p python3 env -->
source env/bin/activate

pip3 install -r requirements.txt

#cron job 
#Make setup script executable
chmod +x setup_councillor_cron.sh

# Run setup (creates cron job every 6 hours)
./setup_councillor_cron.sh

# Verify cron
crontab -l


# Council API Docker Setup

## Quick Start

### 1. Setup Environment
```bash
# Copy environment file
cp .env.example .env

# Edit with your values
nano .env
```

### 2. Start Services

**Start API only (with external MongoDB):**
```bash
docker-compose up -d council-api
```

**Start API + MongoDB:**
```bash
docker-compose up -d council-api mongodb
```

**Start everything including scheduler:**
```bash
docker-compose --profile scheduler up -d
```

### 3. Verify Running
```bash
# Check status
docker-compose ps

# View logs
docker-compose logs -f council-api

# Test API
curl http://localhost:8000/
```

---

## Available Services

| Service | Description | Command |
|---------|-------------|---------|
| `council-api` | FastAPI application | Always runs |
| `mongodb` | MongoDB database | Optional |
| `council-cron` | One-time cron job | Manual trigger |
| `council-scheduler` | Scheduled cron jobs | Runs every 6 hours |

---

## Common Commands

### Start/Stop
```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# Stop and remove volumes (CAUTION: deletes data)
docker-compose down -v

# Restart
docker-compose restart council-api
```

### Logs
```bash
# All logs
docker-compose logs -f

# Specific service
docker-compose logs -f council-api

# Last 100 lines
docker-compose logs --tail=100 council-api
```

### Run Cron Job Manually
```bash
# Run cron job once
docker-compose run --rm council-cron

# Or exec into running container
docker exec council-api python script/automation/councilor_cron.py
```

### Rebuild After Code Changes
```bash
# Rebuild and restart
docker-compose up -d --build

# Rebuild specific service
docker-compose up -d --build council-api
```

### Access Container Shell
```bash
docker exec -it council-api /bin/bash
```

## Using External MongoDB

If you have MongoDB running elsewhere, update `docker-compose.yml`:

1. Remove or comment out the `mongodb` service
2. Remove `depends_on: - mongodb` from api service
3. Update environment variables:

```yaml
environment:
  - MONGODB_HOST=your-mongodb-host.com
  - MONGODB_PORT=*****
  - MONGODB_USER=your_username
  - MONGODB_PASSWORD=your_password
```

---

## Adding New Services

To add another Python script as a service:

```yaml
# Add to docker-compose.yml under services:
  my-new-service:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: my-new-service
    command: ["python", "script/path/to/your_script.py"]
    environment:
      - MONGODB_HOST=mongodb
    volumes:
      - ./logs:/app/logs
    restart: always
    networks:
      - ***-network
```


## Production Tips

1. **Remove volume mounts** for code in production
2. **Use specific image tags** instead of `latest`
3. **Set resource limits:**
```yaml
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M
```

4. **Use secrets for passwords** instead of environment variables
5. **Enable HTTPS** with a reverse proxy (nginx/traefik)


## Troubleshooting

**Container won't start:**
```bash
docker-compose logs council-api
```

**Can't connect to MongoDB:**
```bash
# Check if MongoDB is running
docker-compose ps mongodb

# Test connection
docker exec council-api python -c "from pymongo import MongoClient; print(MongoClient('mongodb://mongodb:27017').server_info())"
```

**Permission issues:**
```bash
# Fix log directory permissions
sudo chown -R $USER:$USER logs/
```
