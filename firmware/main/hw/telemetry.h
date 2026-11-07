#pragma once
#include <cstdint>

namespace agrosense {

// Status do nó (retido): "online", "dormindo" ou, se ele cair sem avisar, "offline" (testamento).
constexpr const char* kStatusTopic = "agrosense/no/status";

// Conecta ao Wi-Fi e ao broker em segundo plano. Sem SSID configurado, ou sem rede,
// o nó continua funcionando: a decisão de irrigação é local (offline-first).
void TelemetryStart();
bool TelemetryConnected();
bool TelemetryWaitConnected(int timeout_ms);
// Publica se estiver conectado; mensagens com QoS 1 ficam pendentes até a confirmação do broker.
void TelemetryPublish(const char* topic, const char* json, int qos, bool retain);
void TelemetryPublishBinary(const char* topic, const uint8_t* data, int len, int qos, bool retain);
bool TelemetryFlush(int timeout_ms);  // espera as confirmações pendentes
void TelemetryStop();                 // desconexão limpa (não dispara o testamento) e Wi-Fi desligado

}  // namespace agrosense
