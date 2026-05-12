/*
 * CEDE i2c_hello (Arduino Uno): USB serial banner + I2C slave @0x43 demo.
 *
 * I2C slave at 0x43, reg0 = 0xCE (magic). Pi validates via: sudo i2cget -y 1 0x43 0 b
 */
#include "cede_build_id.h"
#include <avr/interrupt.h>
#include <avr/io.h>
#include <Wire.h>

static const uint8_t LED_PIN = 13;
static const uint8_t I2C_ADDR_7BIT = 0x43;
static const uint8_t PICO_I2C_ADDR = 0x42;
static const uint8_t REG0_MAGIC = 0xCE;
static const uint8_t REG1_REV = 0x01;

static uint8_t mem[256];
static volatile uint8_t mem_address = 0;
static volatile bool mem_address_written = false;

static void on_receive(int /*n*/) {
  if (Wire.available() < 1) {
    mem_address_written = false;
    return;
  }
  mem_address_written = false;
  while (Wire.available()) {
    const uint8_t b = Wire.read();
    if (!mem_address_written) {
      mem_address = b;
      mem_address_written = true;
    } else {
      mem[mem_address] = b;
      mem_address++;
    }
  }
}

static void on_request() {
  if (!mem_address_written) {
    Wire.write(mem[0]);
    return;
  }
  Wire.write(mem[mem_address]);
  mem_address++;
}

static void i2c_slave_begin() {
  Wire.begin(I2C_ADDR_7BIT);
  Wire.onReceive(on_receive);
  Wire.onRequest(on_request);
}

static void led_timer1_begin(void) {
  noInterrupts();
  TCCR1A = 0;
  TCCR1B = 0;
  TCNT1 = 0;
  OCR1A = 3905;
  TCCR1B |= (1 << WGM12);
  TCCR1B |= (1 << CS12) | (1 << CS10);
  TIMSK1 |= (1 << OCIE1A);
  interrupts();
}

ISR(TIMER1_COMPA_vect) {
  PINB = (1 << PB5);
}

static void run_uno_to_pico_master_probe() {
  Wire.end();
  delay(25);
  Wire.begin();
  Wire.setClock(100000);

  Wire.beginTransmission(PICO_I2C_ADDR);
  Wire.write((uint8_t)0);
  uint8_t txe = Wire.endTransmission(/*sendStop=*/false);

  uint8_t n = 0;
  uint8_t b = 0;
  if (txe == 0) {
    n = Wire.requestFrom(PICO_I2C_ADDR, (uint8_t)1, (uint8_t)1);
    if (n > 0) {
      b = static_cast<uint8_t>(Wire.read());
    }
  }

  Wire.end();
  delay(25);
  i2c_slave_begin();

  if (txe == 0 && n > 0 && b == REG0_MAGIC) {
    Serial.println(F("CEDE i2c uno_to_pico ok"));
  } else {
    Serial.print(F("CEDE i2c uno_to_pico fail tx="));
    Serial.print(txe);
    Serial.print(F(" n="));
    Serial.print(n);
    Serial.print(F(" b=0x"));
    Serial.println(b, HEX);
  }
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  led_timer1_begin();

  for (uint16_t i = 0; i < 256; i++) {
    mem[i] = 0;
  }
  mem[0] = REG0_MAGIC;
  mem[1] = REG1_REV;

  i2c_slave_begin();

  Serial.begin(115200);
  delay(1500);
  Serial.print(F("CEDE i2c_hello ok digest="));
  Serial.print(CEDE_IMAGE_ID);
  Serial.println(F(" (i2c 0x43; send m for uno->pico I2C test)"));
}

void loop() {
  while (Serial.available() > 0) {
    int c = Serial.read();
    if (c == 'm' || c == 'M') {
      run_uno_to_pico_master_probe();
    }
  }
}
