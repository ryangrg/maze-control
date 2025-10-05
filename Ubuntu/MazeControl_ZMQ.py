#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun 24 16:20:50 2021

@author: blairlab
"""

import subprocess
import time
import threading
import minimalmodbus
import pyaudio
import numpy as np
import zmq
import json

def update_json(file_name, key, value):
    with open(file_name, 'r+') as f:
        json_file = json.load(f)
        json_file[key] = int(value)
        f.seek(0)
        json.dump(json_file, f, indent=4)
        f.truncate()

def get_value_json(file_name, key):
    with open(file_name, 'r') as f:
        json_file = json.load(f)
        value = json_file[key]
    return value

class ModbusCommunication:
    tries = 3

    def __init__(self, server_id, timeout, port):
        if port == 1:
            self.connection_to_server = minimalmodbus.Instrument('/dev/ttyUSB0',
                                                                 server_id)
        elif port == 2:
            self.connection_to_server = minimalmodbus.Instrument('/dev/ttyUSB1',
                                                                 server_id)
        self.connection_to_server.serial.baudrate = 9600
        self.connection_to_server.serial.timeout = timeout
        #self.connection_to_server.serial.write_timeout = 0.5
        self.connection_to_server.debug = False
        self.connection_to_server.handle_local_echo = False
        self.connection_to_server.close_port_after_each_call = False

    def mc_write_register(self, start_address, value):
        for attempt in range(self.tries):
            try:
                self.connection_to_server.write_register(start_address, value)
                break
            except IOError as error:
                if attempt <= self.tries:
                    print(error)
                    print('Write failed on device ID ', self.connection_to_server.address)
                    #      '. Trying again! Retry number: ', attempt + 1)
                    time.sleep(0.50)
                    continue
                else:
                    print(error)
                    print('Failed to write register ', attempt + 1, ' times on devise ID ',
                          self.connection_to_server.address, '.')

    def mc_write_registers(self, start_address, values):
        for attempt in range(self.tries):
            try:
                self.connection_to_server.write_registers(start_address, values)
                return
            except IOError as error:
                if attempt <= self.tries:
                    print(error)
                    print('Write failed on device ID ', self.connection_to_server.address, '\n')
                    #      '. Trying again! Retry number: ', attempt + 1)
                    time.sleep(0.50)
                    continue
                else:
                    print(error)
                    print('Failed to write register ', attempt + 1, ' times on devise ID ',
                          self.connection_to_server.address, '.\n')

    def mc_read_register(self, register_address):
        for attempt in range(self.tries):
            try:
                self.connection_to_server.read_register(register_address)
            except IOError as error:
                if attempt <= self.tries:
                    print(error)
                    print('Read failed on devise ID ', self.connection_to_server.address,
                          '. trying again! Retry number: ', attempt + 1)
                    #time.sleep(0.25)
                    continue
                else:
                    print(error)
                    print('Failed to write register ', attempt + 1, ' times on devise ID ',
                          self.connection_to_server.address, '.')


class Actuator(ModbusCommunication):
    def __init__(self, server_id, timeout, port):
        super().__init__(server_id, timeout, port)

    def move_up(self, max_PWM, mid_move_time, deceleration_step, end_move_time):
        self.move = 1  # this tells acutuator to move up
        super().mc_write_registers(0, [self.move, max_PWM, mid_move_time, deceleration_step, end_move_time])

    def move_up_single(self):
        super().mc_write_register(0, 1)

    def move_down(self, max_PWM, mid_move_time, deceleration_step, end_move_time):
        self.move = 2  # this tells actuator to move down
        super().mc_write_registers(0, [self.move, max_PWM, mid_move_time, deceleration_step, end_move_time])

    def move_down_single(self):
        super().mc_write_register(0, 2)

    def update_parameters(self, max_PWM, mid_move_time_up, mid_move_time_down, deceleration_step, end_move_time):
        super().mc_write_registers(1, [max_PWM, mid_move_time_up, mid_move_time_down, deceleration_step, end_move_time])

    def get_cycle_count(self):
        # holding register 5 on accutator has cycle count
        return super().mc_read_register(5)


class RoomLights(ModbusCommunication):
    def __init__(self, server_id, timeout, port):
        super().__init__(server_id, timeout, port)

    def turn_on(self, PWM_brightness=250):
        super().mc_write_register(0, PWM_brightness)

    def turn_off(self):
        super().mc_write_register(0, 0)

    def turn_on_IR(self, PWM_IR_brightness=250):
        super().mc_write_register(1, PWM_IR_brightness)

    def turn_off_IR(self):
        super().mc_write_register(1, 0)

    def set_brightness(self, PWM_brightness):
        super().mc_write_register(0, PWM_brightness)

    def get_brightness(self):
        return super().mc_read_register(int(0))

    def set_IR_brightness(self, PWM_IR_brightness):
        super().mc_write_register(1, PWM_IR_brightness)


class SyringePump(ModbusCommunication):
    def __init__(self, server_id, timeout, port):
        super().__init__(server_id, timeout, port)
        self.fluid_empty = False

    def deliver_reward(self, num_steps, step_back, motor_speed, accel, pulseWidth=25):
        super().mc_write_registers(0, [num_steps, step_back, motor_speed, accel, pulseWidth])

    def get_time(self):
        tc1 = super().mc_read_register(5)
        time.sleep(0.01)
        tc2 = super().mc_read_register(6)
        time.sleep(0.01)
        tc3 = super().mc_read_register(7)
        time_delivery = (tc1*10000 + tc2*100 + tc3)/1000
        return(time_delivery)


class CueLight(ModbusCommunication):
    def __init__(self, server_id, timeout, port):
        super().__init__(server_id, timeout, port)

    def turn_on_pulse(self, pulseDelay=500):
        super().mc_write_register(6, pulseDelay)
        #time.sleep(0.250)
        # value of 3 tells arduino to flash light this is combined with actuator control
        super().mc_write_register(0, 3)

    def turn_on(self):
        super().mc_write_register(0, 4)

    def turn_off(self):
        super().mc_write_register(0, 0)


class BoardLights(ModbusCommunication):
    def __init__(self, server_id, timeout, port):
        super().__init__(server_id, timeout, port)

    def turn_on(self):
        super().mc_write_register(0, 6)

    def turn_off(self):
        super().mc_write_register(0, 7)


class StimulusDisplay:

    def __init__(self):
        self.zmq_context = zmq.Context.instance()
        self.IP_DISPLAY_A = '0.0.0.0'
        self.IP_DISPLAY_B = '0.0.0.0'
        self.PORT_DISPLAY_A = '5001'
        self.PORT_DISPLAY_B = '5002'
        self.PID_display_a = 0
        self.PID_display_b = 0
        self.client_display_a = None
        self.client_display_b = None
        self.REQUEST_TIMEOUT = 2500

    def launchStimulusDisplay(self):
        self.PID_display_a = get_value_json('state_variables_ryan.json', 'PID_display_a')
        if self.PID_display_a == 0:
            cmd_a = f"ssh -f -i ~/.ssh/id_rsa pi@{self.IP_DISPLAY_A} \"sh -c 'nohup Run_StimulusDisplayRaspiZeroMQ.sh" \
                  "> ~/Python/ZMQ_output.txt 2>&1 & exit'\""
            subprocess.call(cmd_a, shell=True)
            self.client_display_a = self.zmq_context.socket(zmq.REQ)
            self.client_display_a.connect(f'tcp://{self.IP_DISPLAY_A}:{self.PORT_DISPLAY_A}')
            self.client_display_a.send_string('Start')
            self.PID_display_a = self.client_display_a.recv_string()
            update_json('state_variables_ryan.json', 'PID_display_a', self.PID_display_a)
            print(f'Display A connected and recv PID: {self.PID_display_a}')
        else:
            cmd = f"ssh -i ~/.ssh/id_rsa pi@{self.IP_DISPLAY_A} ps -p {self.PID_display_a}"
            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()

            if f'{self.PID_display_a}'.encode() in stdout:
                print(f'Screen set A is running with PID={self.PID_display_a}: Setting up connection to server')
                self.client_display_a = self.zmq_context.socket(zmq.REQ)
                self.client_display_a.connect(f'tcp://{self.IP_DISPLAY_A}:{self.PORT_DISPLAY_A}')
                self.client_display_a.send_string('1')
                a_reply = self.client_display_a.recv_string()
                print(f'Sent value=1 to monitors: monitor a reply = {a_reply}')

            else:
                print(f'Screen set A PID is not 0 and PID={self.PID_display_a} is not running. Testing Connection')
                self.client_display_a = self.zmq_context.socket(zmq.REQ)
                self.client_display_a.connect(f'tcp://{self.IP_DISPLAY_A}:{self.PORT_DISPLAY_A}')
                self.client_display_a.send_string('9')
                if (self.client_display_a.poll(self.REQUEST_TIMEOUT) & zmq.POLLIN) != 0:
                    msg = self.client_display_a.recv_string()
                    msg_sent = msg[0]
                    msg_PID = msg[2:]
                    print(f'msg value 9 and received {msg_sent}')
                    print('Display A is running saving correct PID number. Connection is running.')
                    update_json('state_variables_ryan.json', 'PID_display_a', msg_PID)
                else:
                    print('Nothing is running on Display A, launching Display A script and resetting PID')
                    self.client_display_a.setsockopt(zmq.LINGER, 0)
                    self.client_display_a.close()
                    cmd_a = f"ssh -f -i ~/.ssh/id_rsa pi@{self.IP_DISPLAY_A} \"sh -c 'nohup Run_StimulusDisplayRaspiZeroMQ.sh" \
                            "> ~/Python/ZMQ_output.txt 2>&1 & exit'\""
                    subprocess.call(cmd_a, shell=True)
                    self.client_display_a = self.zmq_context.socket(zmq.REQ)
                    self.client_display_a.connect(f'tcp://{self.IP_DISPLAY_A}:{self.PORT_DISPLAY_A}')
                    self.client_display_a.send_string('Start')
                    self.PID_display_a = self.client_display_a.recv_string()
                    update_json('state_variables_ryan.json', 'PID_display_a', self.PID_display_a)
                    print(f'Display A connected and recv PID: {self.PID_display_a}')

        self.PID_display_b = get_value_json('state_variables_ryan.json', 'PID_display_b')
        if self.PID_display_b == 0:
            cmd_b = f"ssh -f -i ~/.ssh/id_rsa pi@{self.IP_DISPLAY_B} \"sh -c 'nohup Run_StimulusDisplayRaspiZeroMQ.sh" \
                  "> ~/Python/ZMQ_output.txt 2>&1 & exit'\""
            subprocess.call(cmd_b, shell=True)
            self.client_display_b = self.zmq_context.socket(zmq.REQ)
            self.client_display_b.connect(f'tcp://{self.IP_DISPLAY_B}:{self.PORT_DISPLAY_B}')
            self.client_display_b.send_string('Start')
            self.PID_display_b = self.client_display_b.recv_string()
            update_json('state_variables_ryan.json', 'PID_display_b', self.PID_display_b)
            print(f'Display B connected and recv PID: {self.PID_display_b}')
        else:
            cmd = f"ssh -i ~/.ssh/id_rsa pi@{self.IP_DISPLAY_B} ps -p {self.PID_display_b}"
            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()

            if f'{self.PID_display_b}'.encode() in stdout:
                print(f'Screen set B is running with PID={self.PID_display_b}: Setting up connection to server')
                self.client_display_b = self.zmq_context.socket(zmq.REQ)
                self.client_display_b.connect(f'tcp://{self.IP_DISPLAY_B}:{self.PORT_DISPLAY_B}')
                self.client_display_b.send_string('1')
                b_reply = self.client_display_b.recv_string()
                print(f'Sent value=1 to monitors: monitor a reply = {b_reply}')
            else:
                print(f'Screen set B PID is not 0 and PID={self.PID_display_b} is not running. Testing Connection')
                self.client_display_b = self.zmq_context.socket(zmq.REQ)
                self.client_display_b.connect(f'tcp://{self.IP_DISPLAY_B}:{self.PORT_DISPLAY_B}')
                self.client_display_b.send_string('9')
                if (self.client_display_b.poll(self.REQUEST_TIMEOUT) & zmq.POLLIN) != 0:
                    msg = self.client_display_b.recv_string()
                    msg_sent = msg[0]
                    msg_PID = msg[2:]
                    print(f'msg value 9 and received {msg_sent}')
                    print('Display B is running saving correct PID number. Connection is running.')
                    update_json('state_variables_ryan.json', 'PID_display_b', msg_PID)
                else:
                    print('Nothing is running on Display B, launching Display B script and resetting PID')
                    self.client_display_b.setsockopt(zmq.LINGER, 0)
                    self.client_display_b.close()
                    cmd_b = f"ssh -f -i ~/.ssh/id_rsa pi@{self.IP_DISPLAY_B} \"sh -c 'nohup Run_StimulusDisplayRaspiZeroMQ.sh" \
                            "> ~/Python/ZMQ_output.txt 2>&1 & exit'\""
                    subprocess.call(cmd_b, shell=True)
                    self.client_display_b = self.zmq_context.socket(zmq.REQ)
                    self.client_display_b.connect(f'tcp://{self.IP_DISPLAY_B}:{self.PORT_DISPLAY_B}')
                    self.client_display_b.send_string('Start')
                    self.PID_display_b = self.client_display_b.recv_string()
                    update_json('state_variables_ryan.json', 'PID_display_b', self.PID_display_b)
                    print(f'Diplay B connected and recv PID: {self.PID_display_b}')

    def send_string_stimulus_display(self, value):
        self.client_display_a.send_string(value)
        self.client_display_b.send_string(value)
        a_reply = self.client_display_a.recv_string()
        b_reply = self.client_display_b.recv_string()
        print(f'Sent {value} to monitors: monitor a reply = {a_reply}, monitor b reply= {b_reply}')

    def blankDisplays(self):
        self.send_string_stimulus_display('1')

    def virtualNorthAtTrueNorth(self):
        self.send_string_stimulus_display('2')

    def virtualNorthAtTrueEast(self):
        self.send_string_stimulus_display('3')

    def virtualNorthAtTrueSouth(self):
        self.send_string_stimulus_display('4')

    def virtualNorthAtTrueWest(self):
        self.send_string_stimulus_display('5')

    def whiteDisplays(self):
        self.send_string_stimulus_display('6')

    def grey_displays(self):
        self.send_string_stimulus_display('7')

    def turn_off_signal_power(self):
        self.send_string_stimulus_display('10')

    def turn_on_signal_power(self):
        self.send_string_stimulus_display('11')

    def exitScript(self):
        self.client_display_a.send_string('8')
        a_reply = self.client_display_a.recv_string()
        self.client_display_b.send_string('8')
        b_reply = self.client_display_b.recv_string()
        print(f'Sent 8 to monitors: monitor a reply = {a_reply}, monitor b reply= {b_reply}')
        print('Exiting monitor control script')
        update_json('state_variables_ryan.json', 'PID_display_a', 0)
        update_json('state_variables_ryan.json', 'PID_display_b', 0)
        self.client_display_a.close()
        self.client_display_b.close()
