// Configuração física do protótipo. Wi-Fi, MQTT e intervalo ficam no
// menuconfig (AgroSense), para senha não ir para o Git.
#pragma once
#include "preprocess.h"

namespace agrosense {

// Câmera: pinout do ESP32-S3-EYE, o mesmo da Freenove ESP32-S3 WROOM CAM.
// Placa diferente? Confira o pinout dela antes do primeiro teste.
constexpr int kCamPwdn = -1, kCamReset = -1, kCamXclk = 15, kCamSiod = 4, kCamSioc = 5;
constexpr int kCamY2 = 11, kCamY3 = 9, kCamY4 = 8, kCamY5 = 10;
constexpr int kCamY6 = 12, kCamY7 = 18, kCamY8 = 17, kCamY9 = 16;
constexpr int kCamVsync = 6, kCamHref = 7, kCamPclk = 13;
constexpr bool kRgb565BigEndian = true;  // padrão do esp32-camera; cores trocadas? inverta

// Barramento I2C dos sensores (ADS1115, BME280, BH1750) — pinos livres da Freenove
constexpr int kI2cSda = 1, kI2cScl = 2;

// Vasos: região de cada um no quadro QVGA (320x240) e ligações
constexpr int kNumPots = 3;
constexpr Roi kPotRois[kNumPots] = {{0, 60, 106}, {107, 60, 106}, {214, 60, 106}};  // ajustar com uma foto
constexpr int kPotSoilChannel[kNumPots] = {0, 1, 2};               // canal do ADS1115
constexpr float kSoilDryVolts[kNumPots] = {2.80f, 2.80f, 2.80f};   // calibrar: sensor no ar
constexpr float kSoilWetVolts[kNumPots] = {1.20f, 1.20f, 1.20f};   // calibrar: sensor na água
constexpr int kPumpGpio[kNumPots] = {14, 21, 47};
constexpr bool kRelayActiveLow = true;  // a maioria dos módulos de relé liga com nível baixo

// Boia do reservatório: -1 desativa a trava
constexpr int kTankSwitchGpio = 42;
constexpr int kTankHasWaterLevel = 0;  // nível lido quando há água (boia com pull-up)

// Espécie: confiança mínima e classificações seguidas para confirmar
constexpr float kMinConfidence = 0.60f;
constexpr int kSpeciesConfirmations = 2;

}  // namespace agrosense
