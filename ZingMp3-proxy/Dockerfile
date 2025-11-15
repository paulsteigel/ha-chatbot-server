ARG BUILD_FROM
FROM $BUILD_FROM

# Install dependencies
RUN apk add --no-cache \
    nodejs \
    npm \
    python3 \
    make \
    g++ \
    curl && \
    rm -rf /var/cache/apk/*

WORKDIR /app

# Copy package files
COPY rootfs/app/package.json rootfs/app/tsconfig.json ./

# Copy source
COPY rootfs/app/src ./src/

# Install and build
RUN npm install --production=false && \
    npm run build && \
    npm prune --production

# Copy run script
COPY rootfs/app/run.sh /
RUN chmod a+x /run.sh

CMD ["/run.sh"]
