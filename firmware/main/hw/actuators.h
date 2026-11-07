#pragma once
#include "esp_err.h"

namespace agrosense {

esp_err_t ActuatorsInit();     // relés desligados, travas do sono liberadas, boia configurada
void SetPump(int pot, bool on);
bool TankOk();                 // true se houver água (ou se a boia estiver desativada)
void ActuatorsPrepareSleep();  // desliga as bombas e trava os pinos durante o sono profundo

}  // namespace agrosense
