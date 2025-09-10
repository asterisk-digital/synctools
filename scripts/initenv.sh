#!/bin/bash

# Script to initialize the environment variables from a template

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

cd "$(dirname "${SCRIPT_DIR}")"

# Check if the op command exists
if ! command -v op &>/dev/null; then
  echo "Error: op command not found. Please install 1Password CLI." >&2
  exit 1
fi

# Check if argument is provided
if [ $# -ne 1 ]; then
  echo "Error: Function requires exactly one argument: environment (prod, dev)"
  exit 1
fi

ENV="$1"
ENVTEMPLATE="envtemplate-${ENV}.txt"
ENVFILE=".env-${ENV}"

# Check if the template file exists
if [ ! -f "${ENVTEMPLATE}" ]; then
  echo "Error: Template file ${ENVTEMPLATE} does not exist."
  exit 1
fi

op inject -i "${ENVTEMPLATE}" -o "${ENVFILE}"
