# Development image. A multi-stage production build comes later, once there is
# something worth shipping.
FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 3000

# Bind to all interfaces so the published port reaches the host.
CMD ["npx", "next", "dev", "-H", "0.0.0.0", "-p", "3000"]
