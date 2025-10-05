#include <ArduinoRS485.h>
#include <ArduinoModbus.h>

//Modbus network ID number
const int ID = 16;
const int BAUD = 9600;

const int STEP = 9; //Step
const int DIR = 8; //Direction

const int BUTTON_1 = 14; //Move pump forward
const int BUTTON_2 = 15; //Move pump backward
const int SENSOR_1 = 16; //Motor Side
const int SENSOR_2 = 17; //Syringe
const int RED_LIGHT = 18;

const int LOW_SPEED = 750;
const int HIGH_SPEED = 25;
const int BUTTON_PULSE = 32;
unsigned long button1PressTime1 = 0;
unsigned long button1PressTime2 = 0;
unsigned long buttonPressInterval = 0;
bool isSinglePress = false;

//light flash variables
unsigned long flashTime1 = 0;
unsigned long flashTime2 = 0;
unsigned long flashTimeInterval = 0;
bool lightOn = true;
bool flashInterval = false;

//clearBuffer Variables
byte buffSize;
int serialJunk;

//Prototype functions
void stepMotor(int stepNum, int pulseTime);
void stepMotorAndRetreat(int stepForward, int stepBack, int pulseTime);
void setButtonPressInterval();
void lightPulse();
void clearBuffer();

AccelStepper stepper(1, STEP, DIR)

void setup()
{
  Serial.begin(BAUD);
  ModbusRTUServer.begin(ID, BAUD); //Server number

  ModbusRTUServer.configureCoils(0x00, 2);
  ModbusRTUServer.coilWrite(0, 0); //1 if syringe pump empty
  ModbusRTUServer.coilWrite(1, 0); //1 if signal recived and Stepper Motor Code excuted. Make sure Client set back to 0 after check.

  ModbusRTUServer.configureHoldingRegisters(0x00, 3);
  ModbusRTUServer.holdingRegisterWrite(0, 0); //Number of steps to advance
  ModbusRTUServer.holdingRegisterWrite(1, 0); //Number of steps to retreat after advance
  ModbusRTUServer.holdingRegisterWrite(2, 0); //Stepper speed to advance

  pinMode(STEP, OUTPUT);
  pinMode(DIR, OUTPUT);
  pinMode(BUTTON_1, INPUT_PULLUP);
  pinMode(BUTTON_2, INPUT_PULLUP);
  pinMode(SENSOR_1, INPUT_PULLUP);
  pinMode(SENSOR_2, INPUT_PULLUP);
  pinMode(RED_LIGHT, OUTPUT);
}

void loop() {
  ModbusRTUServer.poll();
  if (digitalRead(SENSOR_1) == LOW && digitalRead(BUTTON_1) == HIGH) {
    digitalWrite(RED_LIGHT, HIGH);
  } else if (digitalRead(SENSOR_2) == LOW && digitalRead(BUTTON_2) == HIGH) {
    lightPulse();
    ModbusRTUServer.coilWrite(0, 1);
  } else if (digitalRead(BUTTON_1) == LOW && digitalRead(BUTTON_2) == HIGH &&
             digitalRead(SENSOR_2) == HIGH) {
    digitalWrite(RED_LIGHT, LOW);
    setButtonPressInterval();
    while (digitalRead(BUTTON_1) == LOW && digitalRead(BUTTON_2) &&
           digitalRead(SENSOR_2) == HIGH) {
      if ((buttonPressInterval > 100) && (buttonPressInterval < 250)) {
        stepMotor(BUTTON_PULSE, HIGH_SPEED);
      } else {
        stepMotor(BUTTON_PULSE, LOW_SPEED);
      }//if()
    }//while
    ModbusRTUServer.holdingRegisterWrite(0, 0);
    ModbusRTUServer.holdingRegisterWrite(1, 0);
    ModbusRTUServer.holdingRegisterWrite(2, 0);
  } else if (digitalRead(BUTTON_2) == LOW && digitalRead(BUTTON_1) == HIGH &&
             digitalRead(SENSOR_1) == HIGH) {
    digitalWrite(RED_LIGHT, LOW);
    stepMotor(-1 * BUTTON_PULSE, HIGH_SPEED);
    ModbusRTUServer.holdingRegisterWrite(0, 0);
    ModbusRTUServer.holdingRegisterWrite(1, 0);
    ModbusRTUServer.holdingRegisterWrite(2, 0);
  } else if (ModbusRTUServer.holdingRegisterRead(0) != 0 && digitalRead(SENSOR_1) == HIGH &&
             digitalRead(SENSOR_2) == HIGH) {
    stepMotorAndRetreat(ModbusRTUServer.holdingRegisterRead(0),
                        ModbusRTUServer.holdingRegisterRead(1),
                        ModbusRTUServer.holdingRegisterRead(2));
    ModbusRTUServer.holdingRegisterWrite(0, 0);
    ModbusRTUServer.holdingRegisterWrite(1, 0);
    ModbusRTUServer.holdingRegisterWrite(2, 0);
    ModbusRTUServer.coilWrite(1, 1);
    clearBuffer();
  } else {
    digitalWrite(RED_LIGHT, LOW);
    ModbusRTUServer.coilWrite(0, 0);
    ModbusRTUServer.holdingRegisterWrite(0, 0);
    ModbusRTUServer.holdingRegisterWrite(1, 0);
    ModbusRTUServer.holdingRegisterWrite(2, 0);
  }
}//loop()

//functions
void stepMotor(int stepNum, int pulseTime) {
  if (stepNum > 0) {
    digitalWrite(DIR, HIGH);
    for (int i = 0; i < stepNum; i++) {
      digitalWrite(STEP, HIGH);
      delayMicroseconds(pulseTime);
      digitalWrite(STEP, LOW);
      delayMicroseconds(pulseTime);
    }//for
  } else if (stepNum < 0) {
    digitalWrite(DIR, LOW);
    for (int i = 0; i > stepNum; i--) {
      digitalWrite(STEP, HIGH);
      delayMicroseconds(pulseTime);
      digitalWrite(STEP, LOW);
      delayMicroseconds(pulseTime);
    }
  }//if
}//stepMotor()

//functions
void stepMotorAndRetreat(int stepForward, int stepBack, int pulseTime) {
  digitalWrite(DIR, HIGH);
  for (int i = 0; i < stepForward; i++) {
    digitalWrite(STEP, HIGH);
    delayMicroseconds(pulseTime);
    digitalWrite(STEP, LOW);
    delayMicroseconds(pulseTime);
  }//for
  digitalWrite(DIR, LOW);
  for (int i = 0; i < stepBack; i++) {
    digitalWrite(STEP, HIGH);
    delayMicroseconds(pulseTime);
    digitalWrite(STEP, LOW);
    delayMicroseconds(pulseTime);
  }//for
}//stepMotorAndRetreat()

void setButtonPressInterval() {
  if (isSinglePress == true) {
    button1PressTime1 = millis();
    isSinglePress = false;
  } else if (isSinglePress == false) {
    button1PressTime2 = millis();
    isSinglePress = true;
  }//if()
  if (isSinglePress == true) {
    buttonPressInterval = button1PressTime2 - button1PressTime1;
  } else {
    buttonPressInterval = button1PressTime1 - button1PressTime2;
  }//if()
}

void lightPulse() {
  if (lightOn == true) {
    digitalWrite(RED_LIGHT, HIGH);
    if (flashInterval == false) {
      flashTime1 = millis();
      flashInterval = true;
    }//if()
    flashTime2 = millis();
    flashTimeInterval = flashTime2 - flashTime1;
    if (flashTimeInterval > 250) {
      lightOn = false;
      flashInterval = false;
    }//if()
  } else if (lightOn == false) {
    digitalWrite(RED_LIGHT, LOW);
    if (flashInterval == false) {
      flashTime1 = millis();
      flashInterval = true;
    }//if()
    flashTime2 = millis();
    flashTimeInterval = flashTime2 - flashTime1;
    if (flashTimeInterval > 250) {
      lightOn = true;
      flashInterval = false;
    }//if()
  }//if()
}//lightPulse()

void clearBuffer(){
      if (Serial.available() > 0){
        buffSize = Serial.available();
        for (int i=0; i<=buffSize; i++){
          serialJunk = Serial.read();
        }
      }
}//clearBuffer
