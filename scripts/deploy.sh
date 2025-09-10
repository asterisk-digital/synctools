#!/bin/bash

# Runs the deploy process to push the code to Google Cloud with Docker
# Note that Docker must be running
# We expect one argument: the env file to use for the deployment, which includes all the data about
# both the deployment itself and the application

set -euxo pipefail

# Check if gcloud is installed
if ! command -v gcloud &>/dev/null; then
  echo "Error: gcloud command not found. Please install the Google Cloud SDK." >&2
  exit 1
fi

# Check if docker daemon is running
if ! docker info &> /dev/null; then
  echo "Error: Docker daemon not running. Please start Docker." >&2
  exit 1
fi

if [ $# -ne 1 ]; then
  echo "Error: Function requires exactly one argument: path to the envfile to use."
  exit 1
fi

if [ ! -f "$1" ]; then
  echo "Error: Env file $1 does not exist."
  exit 1
fi

ENV_FILE="$1"

# Source the env file and export all variables
set -a
ENV_VARS=""
while IFS='=' read -r key value; do
  # Skip comments and empty lines
  [[ -z "$key" || "$key" =~ ^# ]] && continue

  # Strip wrapping quotes from value
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"

  # Export the variable
  export "$key=$value"

  # Append to ENV_VARS
  ENV_VARS+="$key=$value,"
done < "$ENV_FILE"
set +a

# Remove trailing comma from environment variable list
ENV_VARS="${ENV_VARS%,}"

ARTIFACT_REPO="apps"

# For logging purposes
gcloud auth list
gcloud auth application-default print-access-token

# Check if the artifact repository already exists
if gcloud artifacts repositories describe "${ARTIFACT_REPO}" \
    --location="${REGION}" \
    --project="${GOOGLE_PROJECT_ID}" 2>/dev/null; then
  echo "Artifact repository '${ARTIFACT_REPO}' already exists."
else
  # Create the artifact repository if it does not exist
  echo "Artifact repository '${ARTIFACT_REPO}' does not exist. Creating..."
  # Make sure the API is enabled
  gcloud services enable artifactregistry.googleapis.com --project "$GOOGLE_PROJECT_ID"
  # Enable the API to "run" the code too (lol)
  gcloud services enable run.googleapis.com --project "$GOOGLE_PROJECT_ID"
  gcloud artifacts repositories create "${ARTIFACT_REPO}" \
    --location="${REGION}" \
    --project="${GOOGLE_PROJECT_ID}" \
    --repository-format=docker
fi

IMAGE_NAME="${REGION}-docker.pkg.dev/${GOOGLE_PROJECT_ID}/${ARTIFACT_REPO}/${APP_NAME}:latest"
echo "Deploying ${IMAGE_NAME}"

# Need this to build x86 image on arm machine
# Expects buildx to be enabled: docker buildx create --use
if [[ "$(uname -m)" == "arm"* || "$(uname -m)" == "aarch64" ]]; then
    BUILD_CMD="buildx build --platform linux/amd64"
else
    BUILD_CMD="build"
fi

# shellcheck disable=SC2086
docker ${BUILD_CMD} -t "${IMAGE_NAME}" --push .

gcloud run jobs deploy "${APP_NAME}" \
  --image="${IMAGE_NAME}" \
  --region="${REGION}" \
  --project="${GOOGLE_PROJECT_ID}" \
  --update-env-vars="${ENV_VARS}"
