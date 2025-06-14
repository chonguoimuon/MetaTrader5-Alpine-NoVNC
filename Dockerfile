# Stage 1: Build stage to clone noVNC
FROM alpine:3.20 AS builder

# Install git to clone noVNC, then clean up
RUN apk add --no-cache git && \
    git clone --depth 1 https://github.com/novnc/noVNC.git /opt/novnc && \
    rm -rf /opt/novnc/.git /opt/novnc/docs /opt/novnc/tests /opt/novnc/*.md

# Stage 2: Final image
FROM alpine:3.20

# Install runtime dependencies and clean up in one layer
RUN apk add --no-cache \
    xvfb \
    x11vnc \
    bash \
    websockify \
    python3 \
    py3-pip \
    wine \
    wget \
    dos2unix \
    nginx \
    apache2-utils \
    xauth \
    util-linux \
    alsa-lib && \
    mkdir -p /root/.vnc /config/.wine /var/log /etc/nginx/conf.d && \
    echo "pcm.!default { type plug slave.pcm \"null\" }" > /etc/asound.conf && \
    touch /var/log/mt5_setup.log && \
    chmod 666 /var/log/mt5_setup.log && \
    touch /var/log/websockify.log && \
    chmod 666 /var/log/websockify.log && \
    touch /var/log/x11vnc.log && \
    chmod 666 /var/log/x11vnc.log && \
    rm -rf /var/cache/apk/* /tmp/* /root/.cache /var/tmp/*

# Copy only necessary noVNC files from builder stage
COPY --from=builder /opt/novnc /opt/novnc

# Make vnc.html accessible at /
RUN ln -s /opt/novnc/vnc.html /opt/novnc/index.html

# Copy scripts and app files
COPY app /app
COPY scripts /scripts
COPY Metatrader /Metatrader

# Ensure scripts have Unix line endings and are executable
RUN dos2unix /scripts/*.sh && \
    chmod +x /scripts/*.sh && \
    chmod +x /app/* || true

# Create custom nginx.conf to ensure proper configuration
RUN echo 'worker_processes 1;' > /etc/nginx/nginx.conf && \
    echo 'events { worker_connections 1024; }' >> /etc/nginx/nginx.conf && \
    echo 'http {' >> /etc/nginx/nginx.conf && \
    echo '    include mime.types;' >> /etc/nginx/nginx.conf && \
    echo '    default_type application/octet-stream;' >> /etc/nginx/nginx.conf && \
    echo '    sendfile on;' >> /etc/nginx/nginx.conf && \
    echo '    keepalive_timeout 65;' >> /etc/nginx/nginx.conf && \
    echo '    include /etc/nginx/conf.d/*.conf;' >> /etc/nginx/nginx.conf && \
    echo '}' >> /etc/nginx/nginx.conf

# Set environment variables, avoid default sensitive values
ENV DISPLAY=:1 \
    VNC_PORT=5901 \
    NOVNC_PORT=6080 \
    WEBSOCKIFY_PORT=6081 \
    WINEPREFIX=/config/.wine \
    WINEDEBUG=-all,err-toolbar,fixme-all \
    WINEDLLOVERRIDES="winmm=b" \
    WINE_ALSA_DRIVER=0

# Expose ports for noVNC and Flask
EXPOSE 6080 5001

# Persistent volume for Wine configuration
VOLUME /config

# Start services with continuous command for HTTP Basic Auth
CMD ["/bin/bash", "-c", "echo 'Starting services...' && echo 'Generating Xauthority...' && touch /root/.Xauthority && xauth add $(hostname):1 . $(mcookie) && echo 'Starting Xvfb...' && Xvfb :1 -screen 0 1920x1080x16 & sleep 10 && echo 'Starting x11vnc...' && x11vnc -display :1 -nopw -forever -rfbport 5901 -scale_cursor 1 -auth /root/.Xauthority -o /var/log/x11vnc.log & sleep 2 && echo 'Starting websockify...' && websockify --web /opt/novnc 6081 0.0.0.0:5901 > /var/log/websockify.log 2>&1 & sleep 1 && echo 'Setting up nginx...' && if [ -n \"${CUSTOM_USER}\" ] && [ -n \"${PASSWORD}\" ]; then echo \"Setting up auth for user: ${CUSTOM_USER}\" && htpasswd -cb /etc/nginx/.htpasswd \"${CUSTOM_USER}\" \"${PASSWORD}\" && echo 'server { listen 6080; server_name 0.0.0.0; auth_basic \"Restricted Access\"; auth_basic_user_file /etc/nginx/.htpasswd; location / { root /opt/novnc; index index.html vnc.html; } location /websockify { proxy_pass http://127.0.0.1:6081; proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection \"upgrade\"; proxy_set_header Host $host; proxy_read_timeout 3600; proxy_send_timeout 3600; proxy_connect_timeout 3600; } }' > /etc/nginx/conf.d/novnc.conf; else echo 'No auth set, serving noVNC directly' && echo 'server { listen 6080; server_name 0.0.0.0; location / { root /opt/novnc; index index.html vnc.html; } location /websockify { proxy_pass http://127.0.0.1:6081; proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection \"upgrade\"; proxy_set_header Host $host; proxy_read_timeout 3600; proxy_send_timeout 3600; proxy_connect_timeout 3600; } }' > /etc/nginx/conf.d/novnc.conf; fi && echo 'Testing nginx config...' && nginx -t && echo 'Starting nginx...' && nginx -g 'daemon off;' & sleep 1 && /bin/bash /scripts/01-start.sh || echo 'Failed to run /scripts/01-start.sh'"]