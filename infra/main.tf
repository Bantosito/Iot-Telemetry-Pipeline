resource "azurerm_resource_group" "main" {
  name     = "rg-iot-telemetry"
  location = "northeurope"
  tags = {
    project    = "iot-telemetry"
    managed_by = "terraform"
  }
}

resource "azurerm_iothub" "main" {
  name                = "iot-telemetry-bantos"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku {
    name     = "F1"
    capacity = 1
  }

  event_hub_partition_count   = 2
  event_hub_retention_in_days = 1

  tags = {
    project    = "iot-telemetry"
    managed_by = "terraform"
  }
}