#pragma once
#include "esp_err.h"

namespace agrosense {

struct Environment {
  bool valid;
  float temperature_c;
  float humidity_pct;
  float lux;  // < 0 se o BH1750 falhar
};

esp_err_t SensorsInit();                    // I2C + ADS1115 + BME280 + BH1750
bool ReadSoilVolts(int channel, float* v);  // canal 0..3 do ADS1115
Environment ReadEnvironment();

}  // namespace agrosense
