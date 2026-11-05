#pragma once

namespace agrosense {

// Conecta ao Wi-Fi e ao broker MQTT em segundo plano. Sem SSID configurado,
// ou sem rede, o nó continua funcionando: a decisão de irrigação é local.
void TelemetryStart();
bool TelemetryConnected();
void TelemetryPublish(const char* topic, const char* json);

}  // namespace agrosense
