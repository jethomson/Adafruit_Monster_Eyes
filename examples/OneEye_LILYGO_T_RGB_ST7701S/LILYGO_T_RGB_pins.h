#ifndef LILYGO_T_RGB_PINS_H
#define LILYGO_T_RGB_PINS_H

#include <stdint.h>

// -----------------------------------------------------------------------------
// LILYGO T-RGB — ESP32-S3
// -----------------------------------------------------------------------------


// -----------------------------------------------------------------------------
// I2C / UART header
// -----------------------------------------------------------------------------
static const uint8_t I2C_SDA = 8;
static const uint8_t I2C_SCL = 48;


// -----------------------------------------------------------------------------
// 2.1" ST7701S IPS LCD / RGB interface
// -----------------------------------------------------------------------------
static const uint8_t LCD_BK    = 46;
static const uint8_t LCD_HSYNC = 47;
static const uint8_t LCD_VSYNC = 41;
static const uint8_t LCD_DE    = 45;
static const uint8_t LCD_PCLK  = 42;

static const uint8_t LCD_DATA1  = 21;
static const uint8_t LCD_DATA2  = 18;
static const uint8_t LCD_DATA3  = 17;
static const uint8_t LCD_DATA4  = 46;
static const uint8_t LCD_DATA5  = 15;
static const uint8_t LCD_DATA6  = 14;
static const uint8_t LCD_DATA7  = 13;
static const uint8_t LCD_DATA8  = 12;
static const uint8_t LCD_DATA9  = 11;
static const uint8_t LCD_DATA10 = 10;
static const uint8_t LCD_DATA11 = 9;
static const uint8_t LCD_DATA13 = 7;
static const uint8_t LCD_DATA14 = 6;
static const uint8_t LCD_DATA15 = 5;
static const uint8_t LCD_DATA16 = 3;
static const uint8_t LCD_DATA17 = 2;

// -----------------------------------------------------------------------------
// Touch — CST820 / FT3267
// -----------------------------------------------------------------------------
static const uint8_t TOUCH_SDA = 8;
static const uint8_t TOUCH_SCL = 48;
static const uint8_t TOUCH_INT = 1;

// -----------------------------------------------------------------------------
// XL9535 I/O expander
// -----------------------------------------------------------------------------
static const uint8_t TP_RES  = 1;
static const uint8_t PWR_EN  = 2;
static const uint8_t LCD_CS  = 3;
static const uint8_t LCD_SDA = 4;
static const uint8_t LCD_CLK  = 5;
static const uint8_t LCD_RST  = 6;
static const uint8_t SD_CS    = 7;

// -----------------------------------------------------------------------------
// TF / SD Card
// -----------------------------------------------------------------------------
static const uint8_t SD_CLK = 39;
static const uint8_t SD_CMD = 40;
static const uint8_t SD_D0  = 38;

// -----------------------------------------------------------------------------
// Battery
// -----------------------------------------------------------------------------
static const uint8_t BATTERY_ADC = 4;

#endif /* LILYGO_T_RGB_PINS_H */
