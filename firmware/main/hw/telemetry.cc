#include "telemetry.h"

#include <atomic>
#include <cstring>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "mqtt_client.h"
#include "sdkconfig.h"

namespace agrosense {
namespace {

const char* TAG = "telemetria";
esp_mqtt_client_handle_t g_mqtt = nullptr;
std::atomic<bool> g_connected{false};
std::atomic<int> g_pending{0};  // mensagens QoS 1 aguardando confirmação
bool g_wifi_started = false;

void OnMqttEvent(void*, esp_event_base_t, int32_t id, void*) {
  if (id == MQTT_EVENT_CONNECTED) {
    g_connected = true;
    ESP_LOGI(TAG, "MQTT conectado");
    esp_mqtt_client_publish(g_mqtt, kStatusTopic, "online", 0, 1, 1);
  } else if (id == MQTT_EVENT_DISCONNECTED) {
    g_connected = false;
  } else if (id == MQTT_EVENT_PUBLISHED) {
    if (g_pending > 0) --g_pending;
  }
}

void StartMqtt() {
  if (g_mqtt != nullptr) return;
  esp_mqtt_client_config_t cfg = {};
  cfg.broker.address.uri = CONFIG_AGROSENSE_MQTT_URI;
  cfg.session.last_will.topic = kStatusTopic;  // o broker publica "offline" se o nó cair sem avisar
  cfg.session.last_will.msg = "offline";
  cfg.session.last_will.qos = 1;
  cfg.session.last_will.retain = 1;
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
  g_wifi_started = true;
}

bool TelemetryConnected() { return g_connected; }

bool TelemetryWaitConnected(int timeout_ms) {
  if (!g_wifi_started) return false;
  for (int waited = 0; !g_connected && waited < timeout_ms; waited += 100) vTaskDelay(pdMS_TO_TICKS(100));
  return g_connected;
}

void TelemetryPublish(const char* topic, const char* json, int qos, bool retain) {
  if (g_mqtt == nullptr || !g_connected) return;
  const int msg_id = esp_mqtt_client_publish(g_mqtt, topic, json, 0, qos, retain ? 1 : 0);
  if (qos > 0 && msg_id > 0) ++g_pending;
}

void TelemetryPublishBinary(const char* topic, const uint8_t* data, int len, int qos, bool retain) {
  if (g_mqtt == nullptr || !g_connected || data == nullptr || len <= 0) return;
  // Mensagens maiores que o buffer são fragmentadas pelo próprio cliente MQTT
  const int msg_id = esp_mqtt_client_publish(g_mqtt, topic, reinterpret_cast<const char*>(data), len, qos, retain ? 1 : 0);
  if (qos > 0 && msg_id > 0) ++g_pending;
}

bool TelemetryFlush(int timeout_ms) {
  for (int waited = 0; g_pending > 0 && g_connected && waited < timeout_ms; waited += 50) {
    vTaskDelay(pdMS_TO_TICKS(50));
  }
  return g_pending == 0;
}

void TelemetryStop() {
  if (g_mqtt != nullptr) {
    esp_mqtt_client_disconnect(g_mqtt);
    esp_mqtt_client_stop(g_mqtt);
  }
  if (g_wifi_started) esp_wifi_stop();
}

}  // namespace agrosense
