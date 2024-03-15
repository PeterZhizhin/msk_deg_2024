# Use the official Rust image as the base image
FROM rust:1.76 as builder

# Set the working directory inside the container
WORKDIR /app
RUN cd /app

# Copy the source code of your application to the container
COPY src src
COPY Cargo.toml Cargo.toml
COPY Cargo.lock Cargo.lock

# Build your application
RUN cargo build --release

FROM debian:stable-slim
WORKDIR /app
RUN apt update \
    && apt install -y openssl ca-certificates \
    && apt clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /app

# Copy the binary from the builder stage to the runtime container
COPY --from=builder /app/target/release/postgres_ingest /app/postgres_ingest
COPY certificate.pem /app/certificate.pem

ENV DUMP_PATH /please/specify/the/dump/dir/as/DUMP_PATH/env/variable

# Set the command to run your binary
CMD ["sh", "-c", "/app/postgres_ingest ${DUMP_PATH}"]

