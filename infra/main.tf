resource "azurerm_resource_group" "main" {
  name     = "rg-iot-telemetry"
  location = "northeurope"
  tags = {
    project    = "iot-telemetry"
    managed_by = "terraform"
  }
}