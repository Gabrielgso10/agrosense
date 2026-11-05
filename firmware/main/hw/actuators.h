#pragma once
#include "esp_err.h"

namespace agrosense {

esp_err_t ActuatorsInit();  // relés desligados + entrada da boia
void SetPump(int pot, bool on);
bool TankOk();  // true se houver água (ou se a boia estiver desativada)

}  // namespace agrosense
