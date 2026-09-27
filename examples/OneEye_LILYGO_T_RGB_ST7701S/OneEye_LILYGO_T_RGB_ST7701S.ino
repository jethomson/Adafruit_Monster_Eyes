// Adafruit Monster Eyes -- one eye on an LILYGO T-RGB ESP32-S3.  // // Eye appearance comes from config.eye and BMP files on the CIRCUITPY drive.

#include <Adafruit_Monster_Eyes.h>
#include <Arduino_GFX_Library.h>
#include "LILYGO_T_RGB_pins.h"
#include "esp_random.h"


#define TRGB_W 480
#define TRGB_H 480
#define EYE_SCALE 2

#define TRGB_INIT_OPS st7701_type4_init_operations

#define TRGB_HS_POL 1 ///< HSYNC polarity
#define TRGB_HS_FP 50 ///< HSYNC front porch
#define TRGB_HS_PW 1  ///< HSYNC pulse width
#define TRGB_HS_BP 30 ///< HSYNC back porch

#define TRGB_VS_POL 1 ///< VSYNC polarity
#define TRGB_VS_FP 20 ///< VSYNC front porch
#define TRGB_VS_PW 1  ///< VSYNC pulse width
#define TRGB_VS_BP 30 ///< VSYNC back porch

#define TRGB_R0 21
#define TRGB_R1 18
#define TRGB_R2 17
#define TRGB_R3 16
#define TRGB_R4 15

#define TRGB_G0 14
#define TRGB_G1 13
#define TRGB_G2 12
#define TRGB_G3 11
#define TRGB_G4 10
#define TRGB_G5 9

#define TRGB_B0 7
#define TRGB_B1 6
#define TRGB_B2 5
#define TRGB_B3 3
#define TRGB_B4 2


#if DEMO_MODE_SECONDS > 0
char demo_mode_config_filepath[EYES_PATH_MAX];
const uint64_t demo_mode_runtime = DEMO_MODE_SECONDS * 1000000ULL; // [seconds]
// comment out a folder name if you do not want to see it in demo mode
// spooky only
const char *demo_mode_eye_folders[] = {
    //"anime",
    //"big_blue",
    "cat",
    "deer",
    "demon",
    //"doom-red",
    "doom-spiral",
    "dragon",
    "fish_eyes",
    //"fizzgig",
    "goat",
    //"hazel",
    //"hypno_red",
    //"nauga",
    "newt",
    "owl",
    "pomni",
    "reflection",
    "skull",
    "snake_green",
    "spikes",
    "terminator",
    //"toonstripe",
    "zombie"
};
#else
    #ifndef CONFIG_FILENAME
        CONFIG_FILENAME "/demon/config.eye"
    #endif
#endif

// tested on 2.1" "oval" display
// "oval" display is round but the flexible printed circuit is not covered
Arduino_XL9535SWSPI expander(SDA, SCL, PWR_EN, LCD_CS, LCD_CLK, LCD_SDA);

Arduino_ESP32RGBPanel rgbpanel(
      LCD_DE, LCD_VSYNC, LCD_HSYNC, LCD_PCLK,
      TRGB_R0, TRGB_R1, TRGB_R2, TRGB_R3, TRGB_R4,
      TRGB_G0, TRGB_G1, TRGB_G2, TRGB_G3, TRGB_G4, TRGB_G5,
      TRGB_B0, TRGB_B1, TRGB_B2, TRGB_B3, TRGB_B4,
      TRGB_HS_POL, TRGB_HS_FP, TRGB_HS_PW, TRGB_HS_BP,
      TRGB_VS_POL, TRGB_VS_FP, TRGB_VS_PW, TRGB_VS_BP,
      1,          // pclk_active_neg
      18000000,   // prefer_speed
      false,      // useBigEndian
      0,          // de_idle_high
      0,          // pclk_idle_high
      10*480      // bounce_buffer_size_px
);

// set rotation to 3. rotate 270 CW so that USB cable is near the bottom of the display.
Arduino_RGB_Display gfx(
 TRGB_W, TRGB_H, &rgbpanel, 3 /* rotation */, true /* auto_flush */,
 &expander, GFX_NOT_DEFINED /* RST */, TRGB_INIT_OPS, sizeof(TRGB_INIT_OPS));

Adafruit_Monster_Eyes eyes(&gfx, EYE_SCALE);

void randomEyes() {
    size_t total_folders = sizeof(demo_mode_eye_folders) / sizeof(demo_mode_eye_folders[0]);
    int random_index = esp_random() % total_folders;

    // snprintf will copy up to EYES_PATH_MAX-1 and add '\0'
    snprintf(demo_mode_config_filepath, sizeof(demo_mode_config_filepath), "/%s/config.eye", demo_mode_eye_folders[random_index]);
}

void setup() {
  pinMode(LCD_BK, OUTPUT);
  digitalWrite(LCD_BK, LOW);

  Serial.begin(115200);
  //delay(8000);
  eyes.setVerbose(Serial);

  Wire.begin(I2C_SDA, I2C_SCL, 800000L);

  // for a single eye, the default is the left eye.
  // using the right eye uses the unflipped versions of upper and lower bmp files making it easier
  // compare the image file to what is shown on the display. this is helpful when creating new eyelids. 
  // setting eyelidMirror in config.eye to false for a single left eye will achieve the same goal.
  //eyes.setSide(true); // true sets side to right eye

  #if DEMO_MODE_SECONDS > 0
    randomEyes();
    eyes.setConfigFile(demo_mode_config_filepath);
  #else
    eyes.setConfigFile(CONFIG_FILENAME);
  #endif

  #if EYELIDS_SYMMETRIC == 1
    eyes.setUpperEyelid("/00/upper-symmetrical.bmp");
    eyes.setLowerEyelid("/00/lower-symmetrical.bmp");
  #endif

  if (!eyes.begin()) {
    Serial.print("Monster Eyes failed: ");
    Serial.println(eyes.errorString());
    while (1)
      delay(1000);
  }

  digitalWrite(LCD_BK, HIGH);
}


void loop() {
#if DEMO_MODE_SECONDS > 0
  static uint64_t start_time = esp_timer_get_time();
  uint64_t time_elapsed_since_start = esp_timer_get_time() - start_time;
  if (time_elapsed_since_start >= demo_mode_runtime) {
    digitalWrite(LCD_BK, LOW);
    //ESP.restart();

    randomEyes();

    // this will load the configuration and create the eye in one
    // go with no opportunity to call setters to tweak the configuration
    //if (!eyes.loadEye(demo_mode_config_filepath)) {
    //  Serial.print("  failed: ");
    //  Serial.println(eyes.errorString());
    //}

    if (!eyes.prepareEye(demo_mode_config_filepath)) {
      Serial.print("  failed: ");
      Serial.println(eyes.errorString());
    }

    #if EYELIDS_SYMMETRIC == 1
      // setters can be called in between prepareEye() and applyEye()
      eyes.setUpperEyelid("/00/upper-symmetrical.bmp");
      eyes.setLowerEyelid("/00/lower-symmetrical.bmp");
    #endif

    if (!eyes.applyEye(demo_mode_config_filepath)) {
      Serial.print("  failed: ");
      Serial.println(eyes.errorString());
    }

    start_time = esp_timer_get_time();
    digitalWrite(LCD_BK, HIGH);
    return;
  }
#endif


  eyes.animate();
}