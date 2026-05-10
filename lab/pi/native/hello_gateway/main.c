/* Tiny native check for Raspberry Pi OS 64-bit gateway (aarch64). Built in orchestration-dev. */
#include <stdio.h>

#include "cede_gateway_build.h"

int main(void) {
  printf("CEDE hello_gateway ok digest=%s\n", CEDE_GATEWAY_DIGEST);
  return 0;
}
