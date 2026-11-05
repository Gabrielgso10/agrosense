#include "actuators.h"

#include "app_config.h"
#include "driver/gpio.h"

namespace agrosense {

esp_err_t ActuatorsInit() {
  for (int p = 0; p < kNumPots; ++p) {
    const gpio_num_t pin = static_cast<gpio_num_t>(kPumpGpio[p]);
    gpio_reset_pin(pin);
    gpio_set_direction(pin, GPIO_MODE_OUTPUT);
    SetPump(p, false);
  }
  if (kTankSwitchGpio >= 0) {
    gpio_config_t io = {};
    io.pin_bit_mask = 1ULL << kTankSwitchGpio;
    io.mode = GPIO_MODE_INPUT;
    io.pull_up_en = GPIO_PULLUP_ENABLE;
    return gpio_config(&io);
  }
  return ESP_OK;
}

void SetPump(int pot, bool on) {
  if (pot < 0 || pot >= kNumPots) return;
  const bool level = kRelayActiveLow ? !on : on;
  gpio_set_level(static_cast<gpio_num_t>(kPumpGpio[pot]), level ? 1 : 0);
}

bool TankOk() {
  if (kTankSwitchGpio < 0) return true;
  return gpio_get_level(static_cast<gpio_num_t>(kTankSwitchGpio)) == kTankHasWaterLevel;
}

}  // namespace agrosense
