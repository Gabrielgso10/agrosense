#include "sensors.h"

#include <cstring>

#include "ads111x.h"
#include "app_config.h"
#include "bh1750.h"
#include "bmp280.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "i2cdev.h"

namespace agrosense {
namespace {

const char* TAG = "sensores";
constexpr ads111x_gain_t kGain = ADS111X_GAIN_4V096;  // faixa de ±4,096 V
constexpr float kAdsFullScale = 32767.0f;
const ads111x_mux_t kMux[4] = {ADS111X_MUX_0_GND, ADS111X_MUX_1_GND, ADS111X_MUX_2_GND, ADS111X_MUX_3_GND};

i2c_dev_t g_ads;
i2c_dev_t g_light;
bmp280_t g_bme;
bool g_ads_ok = false, g_light_ok = false, g_bme_ok = false;

gpio_num_t Pin(int n) { return static_cast<gpio_num_t>(n); }

}  // namespace

esp_err_t SensorsInit() {
  esp_err_t err = i2cdev_init();
  if (err != ESP_OK) return err;

  std::memset(&g_ads, 0, sizeof(g_ads));
  g_ads_ok = ads111x_init_desc(&g_ads, ADS111X_ADDR_GND, I2C_NUM_0, Pin(kI2cSda), Pin(kI2cScl)) == ESP_OK &&
             ads111x_set_mode(&g_ads, ADS111X_MODE_SINGLE_SHOT) == ESP_OK &&
             ads111x_set_data_rate(&g_ads, ADS111X_DATA_RATE_32) == ESP_OK &&
             ads111x_set_gain(&g_ads, kGain) == ESP_OK;

  std::memset(&g_light, 0, sizeof(g_light));
  g_light_ok = bh1750_init_desc(&g_light, BH1750_ADDR_LO, I2C_NUM_0, Pin(kI2cSda), Pin(kI2cScl)) == ESP_OK &&
               bh1750_setup(&g_light, BH1750_MODE_CONTINUOUS, BH1750_RES_HIGH) == ESP_OK;

  bmp280_params_t params;
  bmp280_init_default_params(&params);
  std::memset(&g_bme, 0, sizeof(g_bme));
  g_bme_ok = bmp280_init_desc(&g_bme, BMP280_I2C_ADDRESS_0, I2C_NUM_0, Pin(kI2cSda), Pin(kI2cScl)) == ESP_OK &&
             bmp280_init(&g_bme, &params) == ESP_OK;

  ESP_LOGI(TAG, "ADS1115 %s | BH1750 %s | BME280 %s", g_ads_ok ? "ok" : "FALHOU",
           g_light_ok ? "ok" : "FALHOU", g_bme_ok ? "ok" : "FALHOU");
  return g_ads_ok ? ESP_OK : ESP_FAIL;  // sem o ADS1115 não há leitura de solo
}

bool ReadSoilVolts(int channel, float* volts) {
  if (!g_ads_ok || channel < 0 || channel > 3) return false;
  if (ads111x_set_input_mux(&g_ads, kMux[channel]) != ESP_OK) return false;
  if (ads111x_start_conversion(&g_ads) != ESP_OK) return false;
  bool busy = true;
  for (int i = 0; i < 20 && busy; ++i) {  // a 32 amostras/s, uma conversão leva ~31 ms
    vTaskDelay(pdMS_TO_TICKS(10));
    if (ads111x_is_busy(&g_ads, &busy) != ESP_OK) return false;
  }
  int16_t raw = 0;
  if (busy || ads111x_get_value(&g_ads, &raw) != ESP_OK) return false;
  *volts = static_cast<float>(raw) * ads111x_gain_values[kGain] / kAdsFullScale;
  return true;
}

Environment ReadEnvironment() {
  Environment e = {false, 0.0f, 0.0f, -1.0f};
  float pressure = 0.0f;
  if (g_bme_ok) e.valid = bmp280_read_float(&g_bme, &e.temperature_c, &pressure, &e.humidity_pct) == ESP_OK;
  uint16_t lux = 0;
  if (g_light_ok && bh1750_read(&g_light, &lux) == ESP_OK) e.lux = static_cast<float>(lux);
  return e;
}

}  // namespace agrosense
