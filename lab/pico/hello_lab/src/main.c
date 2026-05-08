#include <stdio.h>

#include "hardware/gpio.h"
#include "pico/stdlib.h"

/* cede-rp2: USB CDC — repeat banner so validators can open tty after boot (one-shot prints are often missed).
 * Onboard LED on RP2040 Pico (GP25 via PICO_DEFAULT_LED_PIN). Pico W uses a different LED path (cyw43). */
int main(void) {
    stdio_init_all();

    gpio_init(PICO_DEFAULT_LED_PIN);
    gpio_set_dir(PICO_DEFAULT_LED_PIN, GPIO_OUT);

    sleep_ms(1500);
    /* First line before the loop so a short (e.g. 3s) serial read window still catches the banner. */
    puts("CEDE hello_lab rp2 ok");
    fflush(stdout);

    unsigned ms_since_banner = 0;

    for (;;) {
        gpio_put(PICO_DEFAULT_LED_PIN, 1);
        sleep_ms(250);
        gpio_put(PICO_DEFAULT_LED_PIN, 0);
        sleep_ms(250);

        ms_since_banner += 500;
        if (ms_since_banner >= 3000) {
            puts("CEDE hello_lab rp2 ok");
            fflush(stdout);
            ms_since_banner = 0;
        }
    }
}
