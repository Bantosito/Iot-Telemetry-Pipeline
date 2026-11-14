data "azurerm_subscription" "current" {}
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
resource "azurerm_consumption_budget_subscription" "monthly" {
  name            = "budget_iot_monthly"
  subscription_id = data.azurerm_subscription.current.id
  amount          = 70
  time_grain      = "Monthly"
  time_period {
    start_date = "2026-11-01T00:00:00Z" # First of the month, ISO 8601 with time zone
  }

  notification { # Alert 1 Actual 50%$
    enabled        = true
    threshold      = 50.0
    operator       = "GreaterThanOrEqualTo"
    threshold_type = "Actual"
    contact_emails = [var.alert_email]
  }

  notification { #Alert 2 Forecasted 100%
    enabled        = true
    threshold      = 100.0
    operator       = "GreaterThanOrEqualTo"
    threshold_type = "Forecasted"
    contact_emails = [var.alert_email]
  }
}
resource "azurerm_consumption_budget_resource_group" "resource_group" {
  name              = "budget_iot_resource"
  resource_group_id = azurerm_resource_group.main.id
  amount            = 50
  time_grain        = "Monthly"
  time_period {
    start_date = "2026-11-01T00:00:00Z" # First of the month, ISO 8601 with time zone
  }
  notification { # Alert 1 Actual 50%$
    enabled        = true
    threshold      = 50.0
    operator       = "GreaterThanOrEqualTo"
    threshold_type = "Actual"
    contact_emails = [var.alert_email]
  }

  notification { #Alert 2 Forecasted 100%
    enabled        = true
    threshold      = 100.0
    operator       = "GreaterThanOrEqualTo"
    threshold_type = "Forecasted"
    contact_emails = [var.alert_email]
  }
}