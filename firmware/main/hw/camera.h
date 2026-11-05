#pragma once
#include "esp_camera.h"
#include "esp_err.h"

namespace agrosense {

esp_err_t CameraInit();        // QVGA (320x240) RGB565, quadros na PSRAM
camera_fb_t* CameraCapture();  // descarta o quadro guardado e devolve um novo
void CameraRelease(camera_fb_t* fb);

}  // namespace agrosense
