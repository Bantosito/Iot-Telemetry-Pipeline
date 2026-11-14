# System tools this project needs (macOS). Install them all with:
#   brew bundle
# Check what's missing without installing: brew bundle check
# Python packages are NOT here - they're in requirements*.txt (installed into .venv).

# Terraform comes from HashiCorp's own tap (Homebrew's main collection froze
# it at 1.5.7 after the 2023 licence change).
tap "hashicorp/tap"
brew "hashicorp/tap/terraform"

# MQTT broker + mosquitto_pub / mosquitto_sub, for watching traffic locally.
brew "mosquitto"

# Azure CLI (`az`): log in to Azure, and Terraform uses that login.
cask "azure-cli"

# Docker Desktop: runs the containers (step 1.6).
cask "docker-desktop"

# Library used for creating terraform graphs 
brew "graphviz"

# Optional: GitHub CLI, e.g. `gh run watch` to follow CI from the terminal.
# brew "gh"
