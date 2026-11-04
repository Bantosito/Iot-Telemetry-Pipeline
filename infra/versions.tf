terraform {
  required_version = ">= 1.9"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }

  }
  backend "azurerm" {
    resource_group_name  = "rg-tfstate"
    storage_account_name = "sttfstatebantos"
    container_name       = "tfstate"
    key                  = "iot.terraform.tfstate"
  }
}
provider "azurerm" {
  features {}

}