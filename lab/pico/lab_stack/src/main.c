#include <stdbool.h>
#include <stdio.h>
#include <string.h>

#include "hardware/gpio.h"
#include "hardware/i2c.h"
#include "pico/binary_info.h"
#include "pico/error.h"
#include "pico/i2c_slave.h"
#include "pico/stdio.h"
#include "pico/stdlib.h"

#include "cede_build_id.h"

/* CEDE lab_stack (RP2040): same harness behavior as hello_lab (USB + I2C @0x42); banner identifies app. */

#define HELLO_I2C_INSTANCE i2c0
#define HELLO_I2C_SDA_PIN 0u
#define HELLO_I2C_SCL_PIN 1u
#define HELLO_I2C_BAUD_HZ 100000u
#define HELLO_I2C_ADDR_7BIT 0x42u
#define UNO_I2C_ADDR_7BIT 0x43u

#define HELLO_REG0_MAGIC 0xCEu
#define HELLO_REG1_REV 0x01u

static struct {
  uint8_t mem[256];
  uint8_t mem_address;
  bool mem_address_written;
} i2c_ctx;

bi_decl(bi_program_description("CEDE lab_stack: USB smoke + I2C target"));

static void i2c_slave_handler(i2c_inst_t *i2c, i2c_slave_event_t event) {
  switch (event) {
    case I2C_SLAVE_RECEIVE:
      if (!i2c_ctx.mem_address_written) {
        i2c_ctx.mem_address = i2c_read_byte_raw(i2c);
        i2c_ctx.mem_address_written = true;
      } else {
        i2c_ctx.mem[i2c_ctx.mem_address] = i2c_read_byte_raw(i2c);
        i2c_ctx.mem_address++;
      }
      break;
    case I2C_SLAVE_REQUEST:
      i2c_write_byte_raw(i2c, i2c_ctx.mem[i2c_ctx.mem_address]);
      i2c_ctx.mem_address++;
      break;
    case I2C_SLAVE_FINISH:
      i2c_ctx.mem_address_written = false;
      break;
    default:
      break;
  }
}

static void hello_i2c_slave_init(void) {
  memset(&i2c_ctx, 0, sizeof i2c_ctx);
  i2c_ctx.mem[0] = HELLO_REG0_MAGIC;
  i2c_ctx.mem[1] = HELLO_REG1_REV;

  gpio_init(HELLO_I2C_SDA_PIN);
  gpio_set_function(HELLO_I2C_SDA_PIN, GPIO_FUNC_I2C);
  gpio_pull_up(HELLO_I2C_SDA_PIN);

  gpio_init(HELLO_I2C_SCL_PIN);
  gpio_set_function(HELLO_I2C_SCL_PIN, GPIO_FUNC_I2C);
  gpio_pull_up(HELLO_I2C_SCL_PIN);

  i2c_init(HELLO_I2C_INSTANCE, HELLO_I2C_BAUD_HZ);
  i2c_slave_init(HELLO_I2C_INSTANCE, HELLO_I2C_ADDR_7BIT, &i2c_slave_handler);
}

static void run_pico_to_uno_master_probe(void) {
  i2c_slave_deinit(HELLO_I2C_INSTANCE);
  i2c_deinit(HELLO_I2C_INSTANCE);

  i2c_init(HELLO_I2C_INSTANCE, HELLO_I2C_BAUD_HZ);
  gpio_set_function(HELLO_I2C_SDA_PIN, GPIO_FUNC_I2C);
  gpio_set_function(HELLO_I2C_SCL_PIN, GPIO_FUNC_I2C);

  uint8_t reg = 0;
  int w = i2c_write_blocking(HELLO_I2C_INSTANCE, UNO_I2C_ADDR_7BIT, &reg, 1, true);
  uint8_t rx = 0;
  int r = -1;
  if (w == 1) {
    r = i2c_read_blocking(HELLO_I2C_INSTANCE, UNO_I2C_ADDR_7BIT, &rx, 1, false);
  }

  i2c_deinit(HELLO_I2C_INSTANCE);
  hello_i2c_slave_init();

  if (w == 1 && r == 1 && rx == HELLO_REG0_MAGIC) {
    puts("CEDE i2c pico_to_uno ok");
  } else {
    printf("CEDE i2c pico_to_uno fail w=%d r=%d rx=0x%02x\n", w, r, (unsigned)rx);
  }
  fflush(stdout);
}

int main(void) {
  stdio_init_all();
  hello_i2c_slave_init();

  gpio_init(PICO_DEFAULT_LED_PIN);
  gpio_set_dir(PICO_DEFAULT_LED_PIN, GPIO_OUT);

  sleep_ms(1500);
  printf("CEDE lab_stack rp2 ok digest=%s (i2c 0x42 @ GP0/1; uno lab_stack 0x43; send m for pico→uno I2C test)\n",
         CEDE_IMAGE_ID);
  fflush(stdout);

  unsigned ms_since_banner = 0;

  for (;;) {
    int ch = getchar_timeout_us(0);
    if (ch != PICO_ERROR_TIMEOUT && (ch == 'm' || ch == 'M')) {
      run_pico_to_uno_master_probe();
    }

    gpio_put(PICO_DEFAULT_LED_PIN, 1);
    sleep_ms(250);
    gpio_put(PICO_DEFAULT_LED_PIN, 0);
    sleep_ms(250);

    ms_since_banner += 500;
    if (ms_since_banner >= 3000) {
      printf(
          "CEDE lab_stack rp2 ok digest=%s (i2c 0x42 @ GP0/1; uno lab_stack 0x43; send m for pico→uno I2C test)\n",
          CEDE_IMAGE_ID);
      fflush(stdout);
      ms_since_banner = 0;
    }
  }
}
