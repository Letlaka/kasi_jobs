#!/usr/bin/env bash
set -euo pipefail

# Resolve project root (one level up from script dir)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Defaults (relative to project root)
RENV_FILE="${PROJECT_ROOT}/renv"
ENV_FILE="${PROJECT_ROOT}/.env"
OUT_DIR="${PROJECT_ROOT}/secrets"
DOCKER_CREATE=false
PREFIX=""

# Parse flags first (supports --docker and --prefix=)
POSITIONAL=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --docker)
      DOCKER_CREATE=true; shift ;;
    --prefix=*)
      PREFIX="${1#--prefix=}"; shift ;;
    --help|-h)
      echo "Usage: $0 [--docker] [--prefix=NAME_] [renv-file] [env-file] [out-dir]"; exit 0 ;;
    --*)
      echo "Unknown option: $1" >&2; exit 2 ;;
    *)
      POSITIONAL+=("$1"); shift ;;
  esac
done

# If positional args provided, override defaults in order
if [ ${#POSITIONAL[@]} -ge 1 ]; then RENV_FILE="${POSITIONAL[0]}"; fi
if [ ${#POSITIONAL[@]} -ge 2 ]; then ENV_FILE="${POSITIONAL[1]}"; fi
if [ ${#POSITIONAL[@]} -ge 3 ]; then OUT_DIR="${POSITIONAL[2]}"; fi

mkdir -p "$OUT_DIR"
while IFS= read -r raw || [ -n "$raw" ]; do
  line="${raw%%#*}"
  name="$(echo "$line" | xargs)"
  [ -z "$name" ] && continue

  # value from environment first
  val="${!name:-}"
  if [ -z "$val" ] && [ -f "$ENV_FILE" ]; then
    # match NAME=... (take last match), preserve everything after first '='
    val="$(grep -E \"^${name}=\" "$ENV_FILE" || true)"
    if [ -n "$val" ]; then
      val="${val##*=}"
      # strip surrounding quotes if present
      val="${val%\"}"; val="${val#\"}"
      val="${val%\'}"; val="${val#\'}"
    fi
  fi

  if [ -z "$val" ]; then
    echo "Warning: no value found for $name; skipping" >&2
    continue
  fi

  outfile="$OUT_DIR/$name"
  printf '%s' "$val" > "$outfile"
  chmod 600 "$outfile"
  echo "Wrote $outfile"

  if [ "$DOCKER_CREATE" = true ]; then
    secret_name="${PREFIX}${name}"
    # Remove existing secret (ignore errors) then create
    docker secret rm "$secret_name" >/dev/null 2>&1 || true
    docker secret create "$secret_name" "$outfile"
    echo "Created docker secret $secret_name"
  fi
done < "$RENV_FILE"