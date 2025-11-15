ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG C.UTF-8

# Install Node.js 18 and dependencies
RUN apk add --no-cache \
    nodejs \
    npm \
    python3 \
    make \
    g++ \
    curl \
    && rm -rf /var/cache/apk/*

# Set working directory
WORKDIR /app

# Copy package files first (for better caching)
COPY rootfs/app/package.json rootfs/app/tsconfig.json ./

# Install dependencies
RUN npm install --production=false

# Copy application source
COPY rootfs/app/src ./src/

# Build TypeScript
RUN npm run build

# Copy run script
COPY rootfs/app/run.sh /
RUN chmod a+x /run.sh

# Expose port
EXPOSE 5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5001/health || exit 1

CMD ["/run.sh"]
