#include <ArduinoRS485.h>
#include <ArduinoModbus.h>

//Modbus network ID number
const int ID = 21;
const int BAUD = 9600;

const int PWM_lights = 3;
const int PWM_lights_IR = 9;

void setup() {
  Serial.begin(BAUD);
  ModbusRTUServer.begin(ID, BAUD);

  ModbusRTUServer.configureHoldingRegisters(0x00, 2);
  ModbusRTUServer.holdingRegisterWrite(0, 0);
  ModbusRTUServer.holdingRegisterWrite(1, 0);

  pinMode(PWM_lights, OUTPUT);
  pinMode(PWM_lights_IR, OUTPUT);
}//setup()

void loop() {
  ModbusRTUServer.poll();
  analogWrite(PWM_lights, ModbusRTUServer.holdingRegisterRead(0));
  analogWrite(PWM_lights_IR, ModbusRTUServer.holdingRegisterRead(1));
}//void()
