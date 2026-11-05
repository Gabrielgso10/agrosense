#include "telemetry.h"

#include <cstring>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "mqtt_client.h"
#include "sdkconfig.h"

namespace agrosense {
namespace {

const char* TAG = "telemetria";
esp_mqtt_client_handle_t g_mqtt = nullptr;
volatile bool g_mqtt_connected = false;

void OnMqttEvent(void*, esp_event_base_t, int32_t id, void*) {
  if (id == MQTT_EVENT_CONNECTED) {
    g_mqtt_connected = true;
    ESP_LOGI(TAG, "MQTT conectado");
  } else if (id == MQTT_EVENT_DISCONNECTED) {
    g_mqtt_connected = false;
  }
}

void StartMqtt() {
  if (g_mqtt != nullptr) return;
  esp_mqtt_client_config_t cfg = {};
  cfg.broker.address.uri = CONFIG_AGROSENSE_MQTT_URI;
  g_mqtt = esp_mqtt_client_init(&cfg);
  esp_mqtt_client_register_event(g_mqtt, static_cast<esp_mqtt_event_id_t>(ESP_EVENT_ANY_ID), OnMqttEvent, nullptr);
  esp_mqtt_client_start(g_mqtt);
}

void OnNetworkEvent(void*, esp_event_base_t base, int32_t id, void*) {
  if (base == WIFI_EVENT && (id == WIFI_EVENT_STA_START || id == WIFI_EVENT_STA_DISCONNECTED)) {
    esp_wifi_connect();  // tenta de novo sozinho
  } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
    ESP_LOGI(TAG, "Wi-Fi conectado");
    StartMqtt();
  }
}

}  // namespace

void TelemetryStart() {
  if (std::strlen(CONFIG_AGROSENSE_WIFI_SSID) == 0) {
    ESP_LOGW(TAG, "Sem rede configurada (menuconfig > AgroSense): modo offline");
    return;
  }
  ESP_ERROR_CHECK(esp_netif_init());
  ESP_ERROR_CHECK(esp_event_loop_create_default());
  esp_netif_create_default_wifi_sta();
  wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
  ESP_ERROR_CHECK(esp_wifi_init(&init));
  ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, OnNetworkEvent, nullptr));
  ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, OnNetworkEvent, nullptr));
  wifi_config_t wc = {};
  std::strncpy(reinterpret_cast<char*>(wc.sta.ssid), CONFIG_AGROSENSE_WIFI_SSID, sizeof(wc.sta.ssid) - 1);
  std::strncpy(reinterpret_cast<char*>(wc.sta.password), CONFIG_AGROSENSE_WIFI_PASSWORD, sizeof(wc.sta.password) - 1);
  ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
  ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wc));
  ESP_ERROR_CHECK(esp_wifi_start());
}

bool TelemetryConnected() { return g_mqtt_connected; }

void TelemetryPublish(const char* topic, const char* json) {
  if (g_mqtt != nullptr && g_mqtt_connected) esp_mqtt_client_publish(g_mqtt, topic, json, 0, 0, 0);
}

}  // namespace agrosense
