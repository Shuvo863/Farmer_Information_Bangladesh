# Docker Setup Instructions

## Prerequisites
- Docker installed
- Docker Compose installed

## Build and Run

### Using Docker Compose (Recommended)

1. **Build and start the container:**
   ```bash
   docker-compose up -d --build
   ```

2. **View logs:**
   ```bash
   docker-compose logs -f
   ```

3. **Stop the container:**
   ```bash
   docker-compose down
   ```

4. **Restart the container:**
   ```bash
   docker-compose restart
   ```

### Using Docker directly

1. **Build the image:**
   ```bash
   docker build -t bangladesh-farmer-map .
   ```

2. **Run the container:**
   ```bash
   docker run -d -p 8113:8113 --name bangladesh_farmer_map bangladesh-farmer-map
   ```

## Access the Application

Once the container is running, access the application at:
- **http://192.168.101.232:8113**
- **http://localhost:8113**

## Notes

- The application will automatically run migrations on startup
- Static files will be collected automatically
- All data files (GeoJSON and Farmer_Data.json) are included in the container
- The container will restart automatically if it stops

## Troubleshooting

If you encounter issues:

1. **Check container status:**
   ```bash
   docker-compose ps
   ```

2. **View logs:**
   ```bash
   docker-compose logs web
   ```

3. **Rebuild from scratch:**
   ```bash
   docker-compose down -v
   docker-compose up -d --build
   ```

