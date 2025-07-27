# Dockerfile
FROM nginx:alpine

# Copy application files
COPY index.html /usr/share/nginx/html/
COPY js/ /usr/share/nginx/html/js/
COPY models/ /usr/share/nginx/html/models/

# Create a custom nginx configuration with CORS headers
RUN echo 'server { \
    listen 8500; \
    server_name localhost; \
    location / { \
        root /usr/share/nginx/html; \
        index index.html index.htm; \
        try_files $uri $uri/ =404; \
        \
        # Configure CORS \
        add_header Access-Control-Allow-Origin *; \
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS"; \
        add_header Access-Control-Allow-Headers "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range"; \
    } \
}' > /etc/nginx/conf.d/default.conf

# Expose port 8181
EXPOSE 8500

# Start Nginx server
CMD ["nginx", "-g", "daemon off;"]