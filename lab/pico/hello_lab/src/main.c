#include "pico/stdlib.h"

int main(void) {
    /* Minimal smoke firmware: heartbeat timing without requiring CYW43 LED on Pico W. */
    for (;;) {
        sleep_ms(500);
    }
}
