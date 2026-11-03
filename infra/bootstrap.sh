#!/usr/bin/env bash
# Set the interpreter

set -euo pipefail
# -e : stop at the first commmand that fails 
# -u: stop if a variable is used that was never set 
# -o pipe if any part of a | pipe fail count whole as fail

# This bootstrap script is created and run once before the Terraform can take over
# As Terraform operations are stored in statefile that lives in azure storage fro it to exist
# this storage needs to be created. These scripts create a basis and terraform can take over!

# Variables are put in quotation marks "" to allow values in spaces -> good habbit

LOCATION="northeurope"
RESOURCE_GROUP="rg-tfstate"
STORAGE_ACCOUNT="sttfstatebantos"
CONTAINER="tfstate"
# Variables - no spaces around =
#Register Microsoft Storage 
az provider register \
--namespace Microsoft.Storage \
--wait # 2>/dev/null

#Register Microsoft.Devices for IOT
az provider register \
 --namespace Microsoft.Devices \
 --wait # 2>/dev/null

#Create Resource Group
az group create \
--name "$RESOURCE_GROUP" \
--location "$LOCATION" \
 --output table # 2>/dev/null 

#Create Storage Account
az storage account create \
--name "$STORAGE_ACCOUNT" \
--resource-group "$RESOURCE_GROUP" \
--location "$LOCATION" \
--sku Standard_LRS \
--kind StorageV2 \
--min-tls-version TLS1_2 \
--allow-blob-public-access false \
--output table

#  Create Storeage contrainer 
az storage container-rm create \
--storage-account "$STORAGE_ACCOUNT" \
--resource-group "$RESOURCE_GROUP" \
--name "$CONTAINER" \
--output table

#Update storage account rules 
az storage account blob-service-properties update \
--account-name "$STORAGE_ACCOUNT" \
--resource-group "$RESOURCE_GROUP" \
--enable-versioning true \
--enable-delete-retention true --delete-retention-days 7 --output table

