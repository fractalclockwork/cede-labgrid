static const uint8_t LED_PIN = 13;

void setup() {
  pinMode(LED_PIN, OUTPUT);
  Serial.begin(115200);
  delay(1500);
  Serial.println(F("CEDE hello_lab ok"));
}

void loop() {
  digitalWrite(LED_PIN, HIGH);
  delay(250);
  digitalWrite(LED_PIN, LOW);
  delay(250);

  static uint16_t ms_since_banner = 0;
  ms_since_banner += 500;
  if (ms_since_banner >= 3000) {
    Serial.println(F("CEDE hello_lab ok"));
    ms_since_banner = 0;
  }
}
