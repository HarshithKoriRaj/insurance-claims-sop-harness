# Hugging Face Space: run the image GitHub Actions publishes from main.
# Set OPENAI_API_KEY (or ANTHROPIC_API_KEY) as a Space secret.
FROM ghcr.io/harshithkoriraj/insurance-claims-sop-harness:latest

# Spaces may run the container as a different user; /tmp is always writable.
ENV DATABASE_PATH=/tmp/sessions.sqlite3
EXPOSE 8000
