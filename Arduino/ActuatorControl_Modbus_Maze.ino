
#include <EEPROMex.h>
#include <Stepper.h>
#include <ArduinoRS485.h>
#include <ArduinoModbus.h>

//Modbus network ID number
const int ID = 15;
const int BAUD = 9600;

//eepromex address for long
int addressLong;

//Motor control inputs
int RPWM = 10; //Forward Level/PWM
int LPWM = 9; //Reverse Level/PWM
int Ren = 8; //Forward High
int Len = 7; //Reverse High

//Variables to clear the serial buffer
byte buffSize;
int serialJunk;

void setup() {
  //Modbus Setup
  Serial.begin(BAUD);
  ModbusRTUServer.begin(ID, BAUD);

  //EEPROMEx setup
  EEPROM.setMemPool(0, EEPROMSizeNano);
  addressLong = EEPROM.getAddress(sizeof(long));
  
  //Modbus Address
  ModbusRTUServer.configureHoldingRegisters(0x00,8);
  ModbusRTUServer.holdingRegisterWrite(0,0); //0: do nothing, 1: move up, 2: move down, 5: reset cycle count, 
                                             //6: simulate up with light on 7: simulate down with light off
  ModbusRTUServer.holdingRegisterWrite(1,0); //maxPWM
  ModbusRTUServer.holdingRegisterWrite(2,0); //midMoveTime
  ModbusRTUServer.holdingRegisterWrite(3,0); //decelStep
  ModbusRTUServer.holdingRegisterWrite(4,0); //endMoveTime
  ModbusRTUServer.holdingRegisterWrite(5,EEPROM.readLong(addressLong)); //Number of actuator cycles
  ModbusRTUServer.holdingRegisterWrite(6,0); //Temp reg to hold eeprom update value
  

  //Motor control pinout
  pinMode(Ren, OUTPUT);
  pinMode(Len, OUTPUT);
  pinMode(RPWM, OUTPUT);//PWM 0 (stop) to 255 (allways on)
  pinMode(LPWM, OUTPUT);
  //test pinout
  pinMode(LED_BUILTIN, OUTPUT);

}

void loop() {
  ModbusRTUServer.poll();

  switch(ModbusRTUServer.holdingRegisterRead(0)){
    case 0: //Do nothing
      doNothing();
      break;
    case 1: //Raise Up
      raiseBarrier(ModbusRTUServer.holdingRegisterRead(1),
                   ModbusRTUServer.holdingRegisterRead(2),
                   ModbusRTUServer.holdingRegisterRead(3),
                   ModbusRTUServer.holdingRegisterRead(4));
      ModbusRTUServer.holdingRegisterWrite(0,0);
      clearBuffer();
      break;
    case 2: //Lower Down
      lowerBarrier(ModbusRTUServer.holdingRegisterRead(1),
                   ModbusRTUServer.holdingRegisterRead(2),
                   ModbusRTUServer.holdingRegisterRead(3),
                   ModbusRTUServer.holdingRegisterRead(4));
      ModbusRTUServer.holdingRegisterWrite(0,0);
      EEPROM.writeLong(addressLong, EEPROM.readLong(addressLong)+1); //Update cycle count to EEPROM
      ModbusRTUServer.holdingRegisterWrite(5, EEPROM.readLong(addressLong)); //Update value on holding register
      clearBuffer();
      break;
    case 5:
      EEPROM.writeLong(addressLong, ModbusRTUServer.holdingRegisterRead(6));
      ModbusRTUServer.holdingRegisterWrite(5, ModbusRTUServer.holdingRegisterRead(6));
      ModbusRTUServer.holdingRegisterWrite(0,0);
      break;
    case 6:
      delay(ModbusRTUServer.holdingRegisterRead(2) + ModbusRTUServer.holdingRegisterRead(4));
      digitalWrite(LED_BUILTIN, HIGH);
      ModbusRTUServer.holdingRegisterWrite(0,0);
      break;
    case 7:
      delay(ModbusRTUServer.holdingRegisterRead(2) + ModbusRTUServer.holdingRegisterRead(4));
      digitalWrite(LED_BUILTIN, LOW);
      ModbusRTUServer.holdingRegisterWrite(0,0);
      break;     
    default:
      doNothing();
  }//switch
}

//maxPWM: maximum speed of acctuator
//midStrokeTime: how long to move at constant speed after acceleration
//decelStep: delay of time between deccelerations steps (miliseconds)
//endStrokeTime: delay to reach end of stroke
void raiseBarrier(int maxPWM, int midMoveTime, int decelStep, int endMoveTime){
    digitalWrite(Ren, HIGH);
    digitalWrite(Len, HIGH);
    analogWrite(RPWM, 0);
    analogWrite(LPWM, maxPWM);
    delay(midMoveTime);
    if(maxPWM > 100){
      for(int i=maxPWM; i>100; i--){
        analogWrite(LPWM, i);
        delay(decelStep);
      }//for
      delay(endMoveTime);
    }//if
    doNothing();
}

//maxPWM: maximum speed of acctuator
//midStrokeTime: how long to move at constant speed after acceleration
//decelStep: delay of time between deccelerations steps (miliseconds)
//endStrokeTime: delay to reach end of stroke
void lowerBarrier(int maxPWM, int midMoveTime, int decelStep, int endMoveTime){
    digitalWrite(Ren, HIGH);
    digitalWrite(Len, HIGH);
    analogWrite(LPWM, 0);
    analogWrite(RPWM, maxPWM);
    delay(midMoveTime);
    if(maxPWM > 70){
      for(int i=maxPWM; i>70; i--){
        analogWrite(RPWM, i);
        delay(decelStep);
      }//for
      delay(endMoveTime);
    }//if
    doNothing;
}

void clearBuffer(){
      if (Serial.available() > 0){
        buffSize = Serial.available();
        for (int i=0; i<=buffSize; i++){
          serialJunk = Serial.read();
        }
      }
}//clearBuffer

void doNothing(){
  digitalWrite(Len, LOW);
  digitalWrite(Ren, LOW);
  analogWrite(LPWM, 0);
  analogWrite(RPWM, 0);
}
