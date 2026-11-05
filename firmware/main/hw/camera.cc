#include "camera.h"

#include "app_config.h"

namespace agrosense {

esp_err_t CameraInit() {
  camera_config_t c = {};
  c.pin_pwdn = kCamPwdn;
  c.pin_reset = kCamReset;
  c.pin_xclk = kCamXclk;
  c.pin_sccb_sda = kCamSiod;
  c.pin_sccb_scl = kCamSioc;
  c.pin_d7 = kCamY9;
  c.pin_d6 = kCamY8;
  c.pin_d5 = kCamY7;
  c.pin_d4 = kCamY6;
  c.pin_d3 = kCamY5;
  c.pin_d2 = kCamY4;
  c.pin_d1 = kCamY3;
  c.pin_d0 = kCamY2;
  c.pin_vsync = kCamVsync;
  c.pin_href = kCamHref;
  c.pin_pclk = kCamPclk;
  c.xclk_freq_hz = 20000000;
  c.ledc_timer = LEDC_TIMER_0;
  c.ledc_channel = LEDC_CHANNEL_0;
  c.pixel_format = PIXFORMAT_RGB565;
  c.frame_size = FRAMESIZE_QVGA;
  c.jpeg_quality = 12;
  c.fb_count = 1;
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  return esp_camera_init(&c);
}

camera_fb_t* CameraCapture() {
  // Com um único buffer, o primeiro quadro pode ser antigo: descarta e pega outro.
  camera_fb_t* stale = esp_camera_fb_get();
  if (stale != nullptr) esp_camera_fb_return(stale);
  return esp_camera_fb_get();
}

void CameraRelease(camera_fb_t* fb) {
  if (fb != nullptr) esp_camera_fb_return(fb);
}

}  // namespace agrosense
