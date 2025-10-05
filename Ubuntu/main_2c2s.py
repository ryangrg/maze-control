#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 17 12:50:46 2021

@author: blairlab
"""
import zmq

import MazeControl_ZMQ as mzc

import copy
import csv
import cv2
import json
import os
import random
import subprocess
import sys
import sqlite3
import time
import numpy as np
import datetime
import traceback
import multiprocessing as mp
import pyaudio
import msgpack
import msgpack_numpy as m
m.patch()


from functools import partial
from npsocket import NPSocket
from PyQt5.QtSql import QSqlDatabase, QSqlTableModel
from PyQt5.QtCore import (Qt, QAbstractTableModel, QPoint, QDate, QMutex, QObject,
                          QThread, pyqtSignal, pyqtSlot, QVariant, QTimer)
from PyQt5.QtGui import QPixmap, QImage, QFont
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel,
                             QPushButton, QLineEdit, QFrame, QHBoxLayout, QVBoxLayout, QTabWidget, QGridLayout,
                             QTableView, QComboBox, QDateTimeEdit, QMessageBox, QDialog, QStyledItemDelegate,
                             QFormLayout, QDialogButtonBox)


# Code to stop GUI from crashing on loop errors:
# Note you should track down errors and catch them.
def my_excepthook(type, value, tback):
    sys.__excepthook__(type, value, tback)

sys.excepthook = my_excepthook

# Global Class Object: used to block variable access when multi-threading
mutex = QMutex()


# noinspection PyUnresolvedReferences
class WorkerDeviceControlThread(QObject):
    finished = pyqtSignal()
    barrier_index = pyqtSignal(int)
    cue_index = pyqtSignal(int)
    reward_index = pyqtSignal(int)
    cue_light_index = pyqtSignal(int)

    def __init__(self, action_vector, state_barrier_list, state_cue_list,
                 state_cue_light_list):
        super(WorkerDeviceControlThread, self).__init__()
        self.action_vector = action_vector
        self.state_barrier_list = state_barrier_list
        self.state_cue_list = state_cue_list
        self.state_cue_light_list = state_cue_light_list

    # Make sure video stream is on to get zone
    def run(self):
        # 0 wait for action before proceeding
        # print('Current Zone: ', WorkerVideoThread.zone)
        pass_time_trigger_zone = 0.050
        trigger_zone = self.action_vector[1]
        if trigger_zone == 0:
            zone_check = False
        else:
            zone_check = True

        while zone_check:
            # print('Current Zone: ', WorkerVideoThread.zone)
            t0 = time.time()
            while trigger_zone == WorkerVideoThread.zone:
                time_in_trigger_zone = time.time() - t0
                if time_in_trigger_zone >= pass_time_trigger_zone:
                    zone_check = False
                    break
                time.sleep(0.050)
            time.sleep(0.050)

        # 1 Check reward condition and emit signal to syringe pump control if necessary
        for i, av in enumerate(self.action_vector[23:27]):
            if av == 1:
                self.reward_index.emit(i)
                break

        # 2 Check which light if any should turn on and
        for i, av in enumerate(self.action_vector[27:31]):
            if av != self.state_cue_light_list[i]:
                self.cue_light_index.emit(i)
                break
        # 3 Check barrier states and emit signal to actuator control
        intermodbus_sleep_time = 0.250
        # Shift indexes such that barriers close right behind animal
        # when pretrial configuration (2) action happens.
        # Check if pretrial in east start arm (also this condition is ok
        # for changing barriers at any other condition, except reward
        # when barrier configuration is ignored).
        if (self.action_vector[0] == 2 and self.action_vector[1] == 15 or
                self.action_vector[0] == 0 or
                self.action_vector[0] == 1 or
                self.action_vector[0] == 3):
            print('bef:')
            print(self.state_barrier_list)
            for i in range(16):
                if self.action_vector[i + 3] != self.state_barrier_list[i]:
                    self.barrier_index.emit(i)
                    time.sleep(intermodbus_sleep_time)
            print('aft:')
            print(self.action_vector[3:19])
            print(self.state_barrier_list)
        # Check if pretrial in north start arm
        elif self.action_vector[0] == 2 and self.action_vector[1] == 12:
            indexes = [(i + 3) % 16 for i in range(16)]
            print('bef:')
            print(self.state_barrier_list)
            for i in indexes:
                if self.action_vector[i + 3] != self.state_barrier_list[i]:
                    self.barrier_index.emit(i)
                    time.sleep(intermodbus_sleep_time)
            print('aft:')
            print(indexes)
            print(self.action_vector[3:19])
            print(self.state_barrier_list)
        # Check if pretrial in east start arm
        elif self.action_vector[0] == 2 and self.action_vector[1] == 7:
            indexes = [(i + 6) % 16 for i in range(16)]
            print('bef:')
            print(self.state_barrier_list)
            for i in indexes:
                if self.action_vector[i + 3] != self.state_barrier_list[i]:
                    self.barrier_index.emit(i)
                    time.sleep(intermodbus_sleep_time)
            print('aft:')
            print(indexes)
            print(self.action_vector[3:19])
            print(self.state_barrier_list)
        # Check if pretrial in south start arm
        elif self.action_vector[0] == 2 and self.action_vector[1] == 10:
            indexes = [(i + 9) % 16 for i in range(16)]
            print('bef:')
            print(self.state_barrier_list)
            for i in indexes:
                if self.action_vector[i + 3] != self.state_barrier_list[i]:
                    self.barrier_index.emit(i)
                    time.sleep(intermodbus_sleep_time)
            print('aft:')
            print(indexes)
            print(self.action_vector[3:19])
            print(self.state_barrier_list)
        else:
            # passing on reward conditions
            pass

        # 4A check which cue if any should be displayed and set to cue_index
        for i, av in enumerate(self.action_vector[19:23]):
            if i == 0 and av == 1:
                cue_index = 0
                break
            elif i == 1 and av == 1:
                cue_index = 1
                break
            elif i == 2 and av == 1:
                cue_index = 2
                break
            elif i == 3 and av == 1:
                cue_index = 3
                break
            else:
                cue_index = 4
        # 4B Check if cue needs to be changed and if so emit signal to cue control
        if self.state_cue_list[cue_index] == 0:
            self.cue_index.emit(cue_index)

        # pause before next action vector can be processed
        time.sleep(self.action_vector[2])

        self.finished.emit()
        print('finished thd')


# noinspection PyTypeChecker
class WorkerSessionControlThread(QObject):
    finished = pyqtSignal()
    dialog_msg = pyqtSignal(list)
    update_label_action = pyqtSignal(list)
    barrier_index = pyqtSignal(int)
    cue_index = pyqtSignal(int)
    reward_index = pyqtSignal(int)
    start_reward_locations = pyqtSignal(int)
    cue_light_index = pyqtSignal(int)
    trigger_action_vector = pyqtSignal(list)
    db_session_event = pyqtSignal(list)
    db_session = pyqtSignal(list)
    db_subject_update = pyqtSignal(list)
    db_trial_update = pyqtSignal(list)
    trigger_actuators = pyqtSignal(list)
    trigger_cue = pyqtSignal(list)
    update_vector_lists = pyqtSignal(list, list)
    trigger_pause = pyqtSignal()
    trigger_IR_light = pyqtSignal(bool)
    thread_open_session = False
    pause_session = False


    # sgi: session general info
    def __init__(self, sgi, state_list, event_stream,
                 path_to_dir=None, thread_testing=False):
        super(WorkerSessionControlThread, self).__init__()
        self.general_info_dump = sgi
        self.session_id = sgi['session_id']
        self.session_type = sgi['session_type']
        self.action_vector_history = []
        self.action_vector_list = sgi['action_vector_list']
        self.action_vector_read = sgi['readable_action_vector_list']
        self.start_delay = sgi['delay']
        self.start_goal_pairs = sgi['start_goal_pairs']
        self.state_barrier_list = state_list[0]
        self.state_cue_light_list = state_list[1]
        self.state_cue_list = state_list[2]
        self.event_stream = event_stream
        self.msg = []
        self.path_to_dir = path_to_dir
        self.thread_testing = thread_testing
        self.time_start = None
        self.action_idx = 1
        self.thread_open_session = True
        self.end_action_vector = len(self.action_vector_list)
        self.goal_zones_visited = []
        if self.session_type == 'Exposure':
            self.total_trials = self.end_action_vector
        else:
            self.total_trials = self.end_action_vector/4

        if self.session_type == 'Diff LGT Cue ITI 1':
            self.time_limit = self.total_trials*60 + 480
        elif self.session_type in ['Fixed Cue 2a', 'Fixed Cue 2a Imaging', 'Fixed Cue Switch', 'Fixed No Cue',
                                   'Fixed No Cue Imaging', 'Fixed Cue Rotate', 'Dark Reverse', 'Dark Detour',
                                   'Dark Detour No Cue', 'Rotate Detour', 'Rotate Reverse', 'Rotate Detour Moving',
                                   'Fixed Cue Rotate Imaging', 'Fixed Cue Switch Imaging', 'Rotate Detour Imaging',
                                   'Rotate Detour Moving Imaging', 'Rotate Reverse Imaging','Rotate Detour 1b Moving',
                                   'Rotate Detour 1b Moving Imaging', 'Fixed Cue 2b', 'Fixed Cue 3a']:
            self.time_limit = self.total_trials*180
        elif self.session_type == 'Exposure':
            self.time_limit = self.total_trials*60-60
        else:
            self.time_limit = 60*48

        self.path_to_data_session = (
                    path_to_dir + '/' + sgi['subject_name'] + '_' + 'sess_data' + '_' + sgi['session_number'] + '_' +
                    sgi['date'].replace('/', '') + '_' + sgi['time'].replace(':', '') + '.csv')
        self.path_to_data_trial = (
                    path_to_dir + '/' + sgi['subject_name'] + '_' + 'trial_data' + '_' + sgi['session_number'] + '_' +
                    sgi['date'].replace('/', '') + '_' + sgi['time'].replace(':', '') + '.csv')
        self.total_errors = 0
        self.score_string = ''
        self.score_last_eight = [0, 0, 0, 0, 0, 0, 0, 0]
        self.reward_zone = None

    def run(self):
        event_list = []
        trial_list = []
        turns = []
        trial_number = 0
        trials_perfect = 0
        total_errors = 0
        total_switches = 0
        #past_goals = []
        if self.session_type == 'Exposure':
            goal_location = 'none'
        elif self.action_vector_list[3][23] == 1:
            goal_location = 'NE'
        elif self.action_vector_list[3][24] == 1:
            goal_location = 'SE'
        elif self.action_vector_list[3][25] == 1:
            goal_location = 'SW'
        elif self.action_vector_list[3][26] == 1:
            goal_location = 'NW'

        #past_goals.append(goal_location)
        goal_list = ['NE','SE','SW','NW']
        self.score_string += goal_location
        if self.action_vector_read[self.action_idx - 1][9] == 'Fixed Switch 1':
            trial_switch_check = 23 #random.randint(21,28)
        elif self.action_vector_read[self.action_idx - 1][9] == 'Fixed Switch N':
            trial_switch_check = 8 #random.randint(9,12)
        elif self.action_vector_read[self.action_idx - 1][9] == 'Diff LGT Switch':
            trial_switch_check = 16 
        elif self.action_vector_read[self.action_idx - 1][9] in ['Fixed Cue Switch', 'Dark Reverse', 'Rotate Reverse',
                                                                 'Fixed Cue Switch Imaging', 'Rotate Reverse Imaging']:
            trial_switch_check = 16
        else:
            trial_switch_check = 0
        print(trial_switch_check)
        if 'Imaging' in self.session_type:
            print('imaging session')
        else:
            print('This is not an imaging session')
        trial_switch_1 = False
        self.time_start = time.time()

        # session run loop
        while self.thread_open_session:
            self.pause_run()
            # Code to check if reward shifting session and if so then check if criteria to switch
            if (trial_switch_1 == False and
                self.action_vector_list[self.action_idx][0] == 1 and
                self.action_vector_read[self.action_idx - 1][9] == 'Fixed Switch 1' and
                trial_number >= trial_switch_check and
                trials_perfect/trial_number >= 0.58):
                goal_list.remove(goal_location)
                new_goal = random.choice(goal_list)
                #past_goals.append(new_goal)
                print(new_goal)
                if new_goal == 'NE':
                    trig_zone = 21
                    goal_vector_list = [1,0,0,0]
                    goal_read = 'Northeast'
                elif new_goal == 'SE':
                    trig_zone = 17
                    goal_vector_list = [0,1,0,0]
                    goal_read = 'Southeast'
                elif new_goal == 'SW':
                    trig_zone = 1
                    goal_vector_list = [0,0,1,0]
                    goal_read = 'Southwest'
                elif new_goal =='NW':
                    trig_zone = 5
                    goal_read = 'Northwest'
                    goal_vector_list = [0,0,0,1]
                #Update action vectors with new reward location
                for i, act_vec in enumerate(self.action_vector_list[self.action_idx:]):
                    self.action_vector_read[self.action_idx+i][5] = goal_read
                    if act_vec[0] == 4:
                        act_vec[1] = trig_zone
                        act_vec[23:27] = goal_vector_list
                self.update_vector_lists.emit(self.action_vector_list, self.action_vector_read)
                total_switches += 1
                trial_switch_1 = True
            elif(self.action_vector_list[self.action_idx][0] == 1 and
                 self.action_vector_read[self.action_idx - 1][9] == 'Fixed Switch N' and
                 trial_number >= trial_switch_check and
                 sum(self.score_last_eight) >= 7):
                print('switch code start')
                temp_goal = goal_location
                while goal_location == temp_goal:
                    temp_goal = random.choice(goal_list)
                print(temp_goal)
                #past_goals.append(temp_goal)
                # if past_goals.count(temp_goal) >= 2:
                #     goal_list.remove(temp_goal)
                goal_location = temp_goal
                if goal_location == 'NE':
                    trig_zone = 21
                    goal_vector_list = [1,0,0,0]
                    goal_read = 'Northeast'
                elif goal_location == 'SE':
                    trig_zone = 17
                    goal_vector_list = [0,1,0,0]
                    goal_read = 'Southeast'
                elif goal_location == 'SW':
                    trig_zone = 1
                    goal_vector_list = [0,0,1,0]
                    goal_read = 'Southwest'
                elif goal_location =='NW':
                    trig_zone = 5
                    goal_read = 'Northwest'
                    goal_vector_list = [0,0,0,1]
                for i, act_vec in enumerate(self.action_vector_list[self.action_idx:]):
                    self.action_vector_read[self.action_idx+i][5] = goal_read
                    if act_vec[0] == 4:
                        act_vec[1] = trig_zone
                        act_vec[23:27] = goal_vector_list
                self.update_vector_lists.emit(self.action_vector_list, self.action_vector_read)
                trial_switch_check = trial_number + 8
                total_switches += 1
            elif (trial_switch_1 == False and
                self.action_vector_list[self.action_idx][0] == 1 and
                self.action_vector_read[self.action_idx - 1][9] in ['Fixed Cue Switch', 'Dark Reverse',
                                                                    'Fixed Cue Switch Imaging'] and
                trial_number >= trial_switch_check):
                if goal_location == 'NE':
                    new_goal = 'SW'
                elif goal_location == 'SE':
                    new_goal = 'NW'
                elif goal_location == 'SW':
                    new_goal = 'NE'
                elif goal_location == 'NW':
                    new_goal = 'SE'
                # past_goals.append(new_goal)
                print('Switch')
                if new_goal == 'NE':
                    trig_zone = 21
                    goal_vector_list = [1, 0, 0, 0]
                    goal_read = 'Northeast'
                elif new_goal == 'SE':
                    trig_zone = 17
                    goal_vector_list = [0, 1, 0, 0]
                    goal_read = 'Southeast'
                elif new_goal == 'SW':
                    trig_zone = 1
                    goal_vector_list = [0, 0, 1, 0]
                    goal_read = 'Southwest'
                elif new_goal == 'NW':
                    trig_zone = 5
                    goal_read = 'Northwest'
                    goal_vector_list = [0, 0, 0, 1]
                # Update action vectors with new reward location
                for i, act_vec in enumerate(self.action_vector_list[self.action_idx:]):
                    self.action_vector_read[self.action_idx + i][5] = goal_read
                    if act_vec[0] == 4:
                        act_vec[1] = trig_zone
                        act_vec[23:27] = goal_vector_list
                self.update_vector_lists.emit(self.action_vector_list, self.action_vector_read)
                total_switches += 1
                trial_switch_1 = True
            elif (trial_switch_1 == False and
                  self.action_vector_list[self.action_idx][0] == 1 and
                  self.action_vector_read[self.action_idx - 1][9] in ['Diff LGT Switch', 'Rotate Reverse',
                                                                      'Rotate Reverse Imaging'] and
                  trial_number >= trial_switch_check):
                #Insert code to change rotation
                trig_zone_ne = 21
                goal_vector_list_ne = [1, 0, 0, 0]
                goal_read_ne = 'Northeast'

                trig_zone_se = 17
                goal_vector_list_se = [0, 1, 0, 0]
                goal_read_se = 'Southeast'

                trig_zone_sw = 1
                goal_vector_list_sw = [0, 0, 1, 0]
                goal_read_sw = 'Southwest'

                trig_zone_nw = 5
                goal_read_nw = 'Northwest'
                goal_vector_list_nw = [0, 0, 0, 1]
                print('Rotate Reverse')
                for i, act_vec in enumerate(self.action_vector_list[self.action_idx:]):
                        if self.action_vector_read[self.action_idx + i][5] == 'Northeast':
                            self.action_vector_read[self.action_idx + i][5] = goal_read_sw
                            if act_vec[0] == 4:
                                act_vec[1] = trig_zone_sw
                                act_vec[23:27] = goal_vector_list_sw
                        elif self.action_vector_read[self.action_idx + i][5] == 'Southeast':
                            self.action_vector_read[self.action_idx + i][5] = goal_read_nw
                            if act_vec[0] == 4:
                                act_vec[1] = trig_zone_nw
                                act_vec[23:27] = goal_vector_list_nw
                        elif self.action_vector_read[self.action_idx + i][5] == 'Southwest':
                            self.action_vector_read[self.action_idx + i][5] = goal_read_ne
                            if act_vec[0] == 4:
                                act_vec[1] = trig_zone_ne
                                act_vec[23:27] = goal_vector_list_ne
                        elif self.action_vector_read[self.action_idx + i][5] == 'Northwest':
                            self.action_vector_read[self.action_idx + i][5] = goal_read_se
                            if act_vec[0] == 4:
                                act_vec[1] = trig_zone_se
                                act_vec[23:27] = goal_vector_list_se

                self.update_vector_lists.emit(self.action_vector_list, self.action_vector_read)

                total_switches += 1
                trial_switch_1 = True

            print(self.action_vector_list[self.action_idx])
            self.update_label_action.emit(self.action_vector_list[self.action_idx])
            time_dur, error_count, turns, cue_on = self.run_action_vector(self.action_vector_list[self.action_idx])
            self.start_reward_locations.emit([self.action_vector_read[self.action_idx][4],
                                              self.action_vector_read[self.action_idx][5]])

            if self.thread_testing == False:
                event_list.append([self.action_idx, self.action_vector_read[self.action_idx][1],
                                   self.event_stream[0], self.event_stream[1], self.event_stream[4],
                                   self.event_stream[2], self.event_stream[3], time_dur,
                                   self.action_vector_read[self.action_idx][4],
                                   self.action_vector_read[self.action_idx][5],
                                   self.action_vector_read[self.action_idx][6],
                                   self.session_id])
                self.db_session_event.emit(event_list[-1])

                if self.action_vector_list[self.action_idx][0] in [4,5]:
                    if error_count == 0:
                        trials_perfect += 1
                        self.score_last_eight.pop()
                        self.score_last_eight.insert(0, 1)
                    else:
                        self.score_last_eight.pop()
                        self.score_last_eight.insert(0, 0)
                    trial_number += 1
                    total_errors += error_count
                    print(self.score_last_eight)
                    trial_list.append([trial_number,
                                       self.action_vector_read[self.action_idx][4],
                                       self.action_vector_read[self.action_idx][5],
                                       self.action_vector_read[self.action_idx][6],
                                       time_dur,
                                       error_count,
                                       self.action_vector_read[self.action_idx][9],
                                       self.session_id,
                                       trials_perfect,
                                       turns,
                                       self.goal_zones_visited,
                                       cue_on
                                       ])
                    self.db_trial_update.emit(trial_list[-1])

            self.action_idx += 1
            if (
                    ((self.action_idx % 4 == 1) and (time.time() - self.time_start) > self.time_limit) or
                    self.action_idx == len(self.action_vector_list)
            ):
                self.thread_open_session = False

        if 'Imaging' in self.session_type:
            self.trigger_pause.emit()
            time.sleep(1)
            self.pause_run()

        #Run Finished Save data
        if self.thread_testing == False:
            header_session_event = ['act_idx', 'act_type', 'frame', 'time_stamp', 'zone', 'x_cord', 'y_cord',
                                    'time_dur', 'start_arm', 'goal_loc', 'cue_ort', 'session_id']
            with open(self.path_to_data_session, 'w', encoding='UTF8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(header_session_event)
                writer.writerows(event_list)
            #print(self.action_vector_read[self.action_idx - 1][9])
            # if (self.action_vector_read[self.action_idx - 1][9] == 'Fixed LGT' or
            #         self.action_vector_read[self.action_idx - 1][9] == 'Rotating LGT 2'):
            header_trial = ['trial_number', 'start_arm', 'goal_location', 'cue_orientation', 'time', 'error_count',
                            'session_type', 'session_id']
            with open(self.path_to_data_trial, 'w', encoding='UTF8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(header_trial)
                writer.writerows(trial_list)

            total_time = time.time() - self.time_start
            if trial_number > 0:
                average_errors = total_errors / trial_number
                score = str(trials_perfect / trial_number)
            else:
                average_errors = 0
                score = 0

            self.db_session.emit([self.path_to_data_session, trial_number, trials_perfect, score, total_errors,
                                  total_switches, average_errors, total_time, self.session_id])
            time.sleep(0.250)
            self.db_subject_update.emit([self.general_info_dump['session_number'],
                                         self.general_info_dump['subject_id']])

        time.sleep(5)
        temp_action_vec = [0,0,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, 0]
        self.trigger_action_vector.emit(temp_action_vec)
        self.finished.emit()
        print('Control Session Finished')

    def run_action_vector(self, action_vector):
        # 0 wait for action before proceeding
        error_count = 0
        t0_trial_start = time.time()
        pass_time_trigger_zone = 0.100
        pass_time_reward_zone = 0.250
        trigger_zone = action_vector[1]
        last_reward_zone = self.action_vector_list[self.action_idx - 1][1]
        trial_start_arm = self.action_vector_list[self.action_idx-2][1]
        turn_1 = ''
        turn_2 = ''
        self.goal_zones_visited.clear()
        # Variables to access start goal pair information
        av_idx = self.action_vector_list[self.action_idx][31]
        if av_idx % 4 == 0:
            sgp_idx = int(av_idx / 4)
        elif av_idx % 4 == 1:
            sgp_idx = int((av_idx - 1) / 4)
        elif av_idx % 4 == 2:
            sgp_idx = int((av_idx - 2) / 4)
        elif av_idx % 4 == 3:
            sgp_idx = int((av_idx - 3) / 4)

        #Check if a cue on or cue off trial
        if (self.session_type == 'Diff LGT Cue Delay' or self.session_type == 'Diff LGT All Cue Delay' or
                self.session_type == 'Diff LGT Split Cue Delay' or self.session_type == 'Diff LGT Cue Delay 1a' or
                self.session_type == 'Diff LGT Cue Delay 1b'):
            cue_on = self.start_goal_pairs[sgp_idx][3]
        else:
            cue_on = 1

        if ((self.session_type == 'Diff LGT Cue Delay' or self.session_type == 'Diff LGT All Cue Delay' or
                self.session_type == 'Diff LGT Split Cue Delay' or self.session_type == 'Diff LGT Cue Delay 1a' or
                self.session_type == 'Diff LGT Cue Delay 1b') and
                action_vector[0] == 2):
            print(self.start_goal_pairs[sgp_idx])

        if trigger_zone == 0:
            zone_check = False
        else:
            zone_check = True



        # Zone check loop: When zone is reached the while loop breaks to make
        # maze changes happen.
        # First condition:
        # Loop check during trial (4:Trial End) that counts errors and tracks
        # first and second turn.
        # Second condition:
        # Checks for zone entrance before moving on the configuration changes
        # Zone check variables:
        if action_vector[0] == 4:
            print('Trial: Goal Zone Check Loop')
            error_count = 0
            error_zones = [1, 5, 17, 21]
            error_zones.remove(action_vector[1])
            pass_time_in_error_zone = 0.010
            pass_time_out_of_error_zone = 2
            time_out_of_error_zone_check = 0
            time_out_of_error_zone = time.time()
            turn_1_complete = False
            turn_2_complete = False

            while zone_check:
                self.pause_run()
                # Check if thread has been stopped
                if self.thread_open_session == False:
                    return time.time() - t0_trial_start, error_count, [turn_1, turn_2], cue_on

                # Check for first and second turn
                if turn_1_complete == False:
                    if trial_start_arm == 15:
                        if WorkerSessionVideoThread.zone == 12:
                            turn_1 = 'R'
                            turn_1_complete = True
                        elif WorkerSessionVideoThread.zone == 10:
                            turn_1 = 'L'
                            turn_1_complete = True
                    elif trial_start_arm == 12:
                        if WorkerSessionVideoThread.zone == 7:
                            turn_1 = 'R'
                            turn_1_complete = True
                        elif WorkerSessionVideoThread.zone == 15:
                            turn_1 = 'L'
                            turn_1_complete = True
                    elif trial_start_arm == 7:
                        if WorkerSessionVideoThread.zone == 10:
                            turn_1 = 'R'
                            turn_1_complete = True
                        elif WorkerSessionVideoThread.zone == 12:
                            turn_1 = 'L'
                            turn_1_complete = True
                    elif trial_start_arm == 10:
                        if WorkerSessionVideoThread.zone == 15:
                            turn_1 = 'R'
                            turn_1_complete = True
                        elif WorkerSessionVideoThread.zone == 7:
                            turn_1 = 'L'
                            turn_1_complete = True

                elif turn_2_complete == False and turn_1_complete == True:
                    if trial_start_arm == 15:
                        if WorkerSessionVideoThread.zone == 16 or WorkerSessionVideoThread.zone == 6:
                            turn_2 = 'R'
                            turn_2_complete = True
                        elif WorkerSessionVideoThread.zone == 14 or WorkerSessionVideoThread.zone == 8:
                            turn_2 = 'L'
                            turn_2_complete = True
                    if trial_start_arm == 12:
                        if WorkerSessionVideoThread.zone == 18 or WorkerSessionVideoThread.zone == 4:
                            turn_2 = 'R'
                            turn_2_complete = True
                        elif WorkerSessionVideoThread.zone == 20 or WorkerSessionVideoThread.zone == 2:
                            turn_2 = 'L'
                            turn_2_complete = True
                    if trial_start_arm == 7:
                        if WorkerSessionVideoThread.zone == 16 or WorkerSessionVideoThread.zone == 6:
                            turn_2 = 'R'
                            turn_2_complete = True
                        elif WorkerSessionVideoThread.zone == 14 or WorkerSessionVideoThread.zone == 8:
                            turn_2 = 'L'
                            turn_2_complete = True
                    if trial_start_arm == 10:
                        if WorkerSessionVideoThread.zone == 18 or WorkerSessionVideoThread.zone == 4:
                            turn_2 = 'R'
                            turn_2_complete = True
                        elif WorkerSessionVideoThread.zone == 20 or WorkerSessionVideoThread.zone == 2:
                            turn_2 = 'L'
                            turn_2_complete = True


                # Check if in an error_zone for more than set time in seconds if so set in_error_zone = True
                # So error_count doesn't count multiple times
                in_error_zone = False
                tez0 = time.time()
                while (WorkerSessionVideoThread.zone == error_zones[0] or
                       WorkerSessionVideoThread.zone == error_zones[1] or
                       WorkerSessionVideoThread.zone == error_zones[2]):
                    if in_error_zone:
                        time_out_of_error_zone = time.time()
                    else:
                        time_out_of_error_zone_check = time.time() - time_out_of_error_zone
                    time_in_error_zone = time.time() - tez0
                    #print(time_in_error_zone, time_out_of_error_zone_check, time_out_of_error_zone, in_error_zone)
                    if ((time_in_error_zone >= pass_time_in_error_zone) and
                            (in_error_zone == False) and
                            (time_out_of_error_zone_check >= pass_time_out_of_error_zone)):
                        error_count += 1
                        self.goal_zones_visited.append(WorkerSessionVideoThread.zone)
                        time_out_of_error_zone = time.time()
                        in_error_zone = True
                        #print(time_in_error_zone)
                    self.pause_run()
                    if self.thread_open_session == False:
                        return time.time() - t0_trial_start, error_count, [turn_1, turn_2], cue_on
                    time.sleep(0.010)

                in_trigger_zone = False
                tz0 = time.time()
                while trigger_zone == WorkerSessionVideoThread.zone:
                    time_in_trigger_zone = time.time() - tz0
                    self.pause_run()
                    if self.thread_open_session == False:
                        return time.time() - t0_trial_start, error_count, [turn_1, turn_2], cue_on
                    if time_in_trigger_zone >= pass_time_reward_zone:
                        zone_check = False
                        self.goal_zones_visited.append(WorkerSessionVideoThread.zone)
                        print('Trial: Exiting Zone Check Loop')
                        break
                    in_trigger_zone = True
                    time.sleep(0.010)

                if in_trigger_zone == False:
                    time.sleep(0.010)

        elif self.session_type == 'Exposure' and action_vector[0] == 5:
            print('Waiting to enter zone')
            trigger_zone = [1, 5, 21, 17]
            temp_trigger_zone = trigger_zone.copy()
            if self.reward_zone != None:
                temp_trigger_zone.remove(self.reward_zone)
            zone_check = True
            while zone_check:
                self.pause_run()
                # Check if thread has been stopped
                if self.thread_open_session == False:
                    return time.time() - t0_trial_start, error_count, [turn_1, turn_2], cue_on

                in_trigger_zone = False
                tz0 = time.time()
                while WorkerSessionVideoThread.zone in temp_trigger_zone:
                    self.reward_zone = WorkerSessionVideoThread.zone.copy()
                    time_in_trigger_zone = time.time() - tz0
                    self.pause_run()
                    if self.thread_open_session == False:
                        return time.time() - t0_trial_start, error_count, [turn_1, turn_2], cue_on
                    if time_in_trigger_zone >= pass_time_reward_zone:
                        print(f'Reward zone {self.reward_zone} entered: Time out for {action_vector[2]} secs')
                        zone_check = False
                        break
                    in_trigger_zone = True
                    time.sleep(0.010)

                if in_trigger_zone == False:
                    time.sleep(0.010)

        else:
            # If Trial Start display cue for Diff LGT Cue ITI and wait 10 seconds before running zone check for
            if action_vector[0] == 3 and self.session_type == 'Diff LGT Cue ITI 1':
                self.trigger_cue.emit(action_vector)
                time.sleep(10)

            while zone_check:
                self.pause_run()
                if self.thread_open_session == False:
                    return time.time() - t0_trial_start, error_count, [turn_1, turn_2], cue_on
                elif (
                        ((time.time() - self.time_start) > self.time_limit) and
                        (action_vector[0] == 2)
                ):
                    self.thread_open_session = False
                in_trigger_zone = False
                tz0 = time.time()
                while trigger_zone == WorkerSessionVideoThread.zone:
                    time_in_trigger_zone = time.time() - tz0
                    self.pause_run()
                    if self.thread_open_session == False:
                        return time.time() - t0_trial_start, error_count, [turn_1, turn_2], cue_on
                    elif (
                            ((time.time() - self.time_start) > self.time_limit) and
                            (action_vector[0] == 2)
                    ):
                        self.thread_open_session = False
                    if time_in_trigger_zone >= pass_time_trigger_zone:
                        zone_check = False
                        break
                    in_trigger_zone = True
                    time.sleep(0.025)
                if in_trigger_zone == False:
                    time.sleep(0.025)

        # Condition 1:
        # ITI Barrier recongifuration to prevent rat from wandering around maze
        # Rat is prevented from going back to a section away from the entry arm
        # raise adjacent barriers to start-arm when close to reward zone during the ITI phase
        # otherwise wait to configure maze until near start arm to raise trap barriers
        # Run typical maze change specified by action vector
        if action_vector[0] == 1 and self.action_idx > 2:
            if self.action_vector_list[self.action_idx][7] == 0:
                next_start_arm = 12
            elif self.action_vector_list[self.action_idx][4] == 0:
                next_start_arm = 15
            elif self.action_vector_list[self.action_idx][13] == 0:
                next_start_arm = 10
            elif self.action_vector_list[self.action_idx][10] == 0:
                next_start_arm = 7
            else:
                next_start_arm = 0

            #next_start_arm = self.action_vector_list[self.action_idx + 1][1]
            #time.sleep(2)
            # print(f'Last: {last_reward_zone}/nstart: {next_start_arm}')
            # Close ITI conditions
            if last_reward_zone == 5 and (next_start_arm == 12 or next_start_arm == 7):
                #print('checking zone close (rwz 5)')
                if next_start_arm == 12:
                    temp_action_vec = action_vector.copy()
                    temp_action_vec[3:19] = [0, 1, 0, 1, 0, 0, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1]
                    self.trigger_action_vector.emit(temp_action_vec)
                if next_start_arm == 7:
                    temp_action_vec = action_vector.copy()
                    temp_action_vec[3:19] = [0, 1, 0, 1, 1, 0, 0, 0, 1, 0, 1, 0, 1, 0, 1, 0]
                    self.trigger_action_vector.emit(temp_action_vec)

            elif last_reward_zone == 21 and (next_start_arm == 15 or next_start_arm == 12):
                #print('checking zone close (rwz 21)')
                if next_start_arm == 15:
                    temp_action_vec = action_vector.copy()
                    temp_action_vec[3:19] = [1, 0, 0, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0]
                    self.trigger_action_vector.emit(temp_action_vec)
                if next_start_arm == 12:
                    temp_action_vec = action_vector.copy()
                    temp_action_vec[3:19] = [1, 1, 0, 0, 0, 1, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1]
                    self.trigger_action_vector.emit(temp_action_vec)

            elif last_reward_zone == 17 and (next_start_arm == 10 or next_start_arm == 15):
                #print('checking zone close (rwz 17)')
                if next_start_arm == 10:
                    temp_action_vec = action_vector.copy()
                    temp_action_vec[3:19] = [0, 1, 1, 0, 1, 0, 0, 1, 0, 1, 0, 0, 0, 1, 0, 1]
                    self.trigger_action_vector.emit(temp_action_vec)
                if next_start_arm == 15:
                    temp_action_vec = action_vector.copy()
                    temp_action_vec[3:19] = [0, 0, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0]
                    self.trigger_action_vector.emit(temp_action_vec)

            elif last_reward_zone == 1 and (next_start_arm == 7 or next_start_arm == 10):
                #print('checking zone close (rwz 1)')
                if next_start_arm == 7:
                    temp_action_vec = action_vector.copy()
                    temp_action_vec[3:19] = [0, 1, 0, 0, 1, 0, 1, 0, 0, 0, 1, 1, 1, 0, 1, 0]
                    self.trigger_action_vector.emit(temp_action_vec)
                if next_start_arm == 10:
                    temp_action_vec = action_vector.copy()
                    temp_action_vec[3:19] = [0, 1, 0, 0, 1, 0, 1, 1, 0, 0, 0, 1, 0, 1, 0, 1]
                    self.trigger_action_vector.emit(temp_action_vec)
            # Far ITI conditions
            elif last_reward_zone == 5 and (next_start_arm == 10 or next_start_arm == 15):
                #print('checking zone far (rwz 5)')
                self.trigger_action_vector.emit(action_vector)
                if next_start_arm == 10:
                    trigger_sub_zone = [2, 18]
                    while True:
                        self.pause_run()
                        if self.thread_open_session == False:
                            return time.time() - t0_trial_start, error_count, [turn_1, turn_2], cue_on
                        elif (time.time() - self.time_start) > self.time_limit:
                            self.thread_open_session = False
                        if trigger_sub_zone[0] == WorkerSessionVideoThread.zone:
                            self.trigger_actuators.emit([6, 11])
                            break
                        elif trigger_sub_zone[1] == WorkerSessionVideoThread.zone:
                            self.trigger_actuators.emit([2, 9])
                            break
                        time.sleep(0.05)
                elif next_start_arm == 15:
                    trigger_sub_zone = [14, 16]
                    while True:
                        self.pause_run()
                        if self.thread_open_session == False:
                            return time.time() - t0_trial_start, error_count, [turn_1, turn_2], cue_on
                        elif (time.time() - self.time_start) > self.time_limit:
                            self.thread_open_session = False
                        if trigger_sub_zone[0] == WorkerSessionVideoThread.zone:
                            self.trigger_actuators.emit([9, 2])
                            break
                        elif trigger_sub_zone[1] == WorkerSessionVideoThread.zone:
                            self.trigger_actuators.emit([5, 0])
                            break
                        time.sleep(0.05)

            elif last_reward_zone == 21 and (next_start_arm == 7 or next_start_arm == 10):
                #print('checking zone far (rwz 21)')
                self.trigger_action_vector.emit(action_vector)
                if next_start_arm == 7:
                    trigger_sub_zone = [6, 8]
                    while True:
                        self.pause_run()
                        if self.thread_open_session == False:
                            return time.time() - t0_trial_start, error_count, [turn_1, turn_2], cue_on
                        elif (time.time() - self.time_start) > self.time_limit:
                            self.thread_open_session = False

                        if trigger_sub_zone[0] == WorkerSessionVideoThread.zone:
                            self.trigger_actuators.emit([11, 6])
                            break
                        elif trigger_sub_zone[1] == WorkerSessionVideoThread.zone:
                            self.trigger_actuators.emit([3, 8])
                            break
                        time.sleep(0.05)
                elif next_start_arm == 10:
                    trigger_sub_zone = [2, 18]
                    while True:
                        self.pause_run()
                        if self.thread_open_session == False:
                            return time.time() - t0_trial_start, error_count, [turn_1, turn_2], cue_on
                        elif (time.time() - self.time_start) > self.time_limit:
                            self.thread_open_session = False

                        if trigger_sub_zone[0] == WorkerSessionVideoThread.zone:
                            self.trigger_actuators.emit([6, 11])
                            break
                        elif trigger_sub_zone[1] == WorkerSessionVideoThread.zone:
                            self.trigger_actuators.emit([2, 9])
                            break
                        time.sleep(0.05)

            elif last_reward_zone == 17 and (next_start_arm == 7 or next_start_arm == 12):
                #print('checking zone far (rwz 17)')
                self.trigger_action_vector.emit(action_vector)
                if next_start_arm == 7:
                    trigger_sub_zone = [6, 8]
                    while True:
                        self.pause_run()
                        if self.thread_open_session == False:
                            return time.time() - t0_trial_start, error_count, [turn_1, turn_2], cue_on
                        elif (time.time() - self.time_start) > self.time_limit:
                            self.thread_open_session = False

                        if trigger_sub_zone[0] == WorkerSessionVideoThread.zone:
                            self.trigger_actuators.emit([11, 6])
                            break
                        elif trigger_sub_zone[1] == WorkerSessionVideoThread.zone:
                            self.trigger_actuators.emit([3, 8])
                            break
                        time.sleep(0.05)
                elif next_start_arm == 12:
                    trigger_sub_zone = [4, 20]
                    while True:
                        self.pause_run()
                        if self.thread_open_session == False:
                            return time.time() - t0_trial_start, error_count, [turn_1, turn_2], cue_on
                        elif (time.time() - self.time_start) > self.time_limit:
                            self.thread_open_session = False

                        if trigger_sub_zone[0] == WorkerSessionVideoThread.zone:
                            self.trigger_actuators.emit([8, 3])
                            break
                        elif trigger_sub_zone[1] == WorkerSessionVideoThread.zone:
                            self.trigger_actuators.emit([0, 5])
                            break
                        time.sleep(0.05)

            elif last_reward_zone == 1 and (next_start_arm == 12 or next_start_arm == 15):
                #print('checking zone far (rwz 1)')
                self.trigger_action_vector.emit(action_vector)
                if next_start_arm == 12:
                    trigger_sub_zone = [4, 20]
                    while True:
                        self.pause_run()
                        if self.thread_open_session == False:
                            return time.time() - t0_trial_start, error_count, [turn_1, turn_2], cue_on
                        elif (time.time() - self.time_start) > self.time_limit:
                            self.thread_open_session = False

                        if trigger_sub_zone[0] == WorkerSessionVideoThread.zone:
                            self.trigger_actuators.emit([8, 3])
                            break
                        elif trigger_sub_zone[1] == WorkerSessionVideoThread.zone:
                            self.trigger_actuators.emit([0, 5])
                            break
                        time.sleep(0.05)
                if next_start_arm == 15:
                    trigger_sub_zone = [14, 16]
                    while True:
                        self.pause_run()
                        if self.thread_open_session == False:
                            return time.time() - t0_trial_start, error_count, [turn_1, turn_2], cue_on
                        elif (time.time() - self.time_start) > self.time_limit:
                            self.thread_open_session = False

                        if trigger_sub_zone[0] == WorkerSessionVideoThread.zone:
                            self.trigger_actuators.emit([9, 2])
                            break
                        elif trigger_sub_zone[1] == WorkerSessionVideoThread.zone:
                            self.trigger_actuators.emit([5, 0])
                            break
                        time.sleep(0.05)
        # Case: Pretrial for dark test
        elif action_vector[0] == 2 and self.session_type in ['Fixed No Cue', 'Dark Train', 'Dark Detour No Cue',
                                                             'Dark Reverse', 'Fixed No Cue Imaging']:
            temp_action_vec = action_vector.copy()
            temp_action_vec[19:23] = [0, 0, 0, 0]
            self.trigger_action_vector.emit(temp_action_vec)
        # Case: Trial Start
        elif action_vector[0] == 3:
            temp_action_vec = action_vector.copy()
            if temp_action_vec[1] == 19:
                while WorkerSessionVideoThread.zone != 15:
                    self.pause_run()
                    if self.thread_open_session == False:
                        return time.time() - t0_trial_start, error_count, [turn_1, turn_2], cue_on
                    time.sleep(0.100)
            elif temp_action_vec[1] == 9:
                while WorkerSessionVideoThread.zone != 10:
                    self.pause_run()
                    if self.thread_open_session == False:
                        return time.time() - t0_trial_start, error_count, [turn_1, turn_2], cue_on
                    time.sleep(0.100)
            elif temp_action_vec[1] == 3:
                while WorkerSessionVideoThread.zone != 7:
                    self.pause_run()
                    if self.thread_open_session == False:
                        return time.time() - t0_trial_start, error_count, [turn_1, turn_2], cue_on
                    time.sleep(0.100)
            elif temp_action_vec[1] == 13:
                while WorkerSessionVideoThread.zone != 12:
                    self.pause_run()
                    if self.thread_open_session == False:
                        return time.time() - t0_trial_start, error_count, [turn_1, turn_2], cue_on
                    time.sleep(0.100)
            time.sleep(int(self.start_delay))
            # turn cue off in trialstart if cue off trial or if it is testing rats in dark with monitor
            # backlight on to match cue off conditions.
            if cue_on == 0 or self.session_type in ['Fixed No Cue', 'Dark Train', 'Dark Detour No Cue', 'Dark Reverse',
                                                    'Fixed No Cue Imaging']:
                temp_action_vec[19:23] = [0, 0, 0, 0]
            self.trigger_action_vector.emit(temp_action_vec)
        # Check that turns cue off durring working memory version of behavior
        elif ((self.session_type == 'Diff LGT Cue Delay' or self.session_type == 'Diff LGT All Cue Delay' or
                self.session_type == 'Diff LGT Split Cue Delay' or self.session_type == 'Diff LGT Cue Delay 1a' or
               self.session_type == 'Diff LGT Cue Delay 1b') and action_vector[0] == 4 and cue_on == 0):
            temp_action_vec = action_vector.copy()
            temp_action_vec[19:23] = [0, 0, 0, 0]
            self.trigger_action_vector.emit(temp_action_vec)
        # Keep monitors of in Dark Test
        elif (self.session_type in ['Fixed No Cue', 'Dark Train', 'Dark Detour No Cue', 'Dark Reverse',
                                    'Fixed No Cue Imaging'] and
              action_vector[0] == 4):
            temp_action_vec = action_vector.copy()
            temp_action_vec[19:23] = [0, 0, 0, 0]
            self.trigger_action_vector.emit(temp_action_vec)
        # Just do what it says to do
        elif self.session_type == 'Exposure' and action_vector[0] == 5:
            print(f'Reward given at zone {self.reward_zone}')
            if self.reward_zone == 21:
                reward_list = [1, 0, 0, 0]
            elif self.reward_zone == 17:
                reward_list = [0, 1, 0, 0]
            elif self.reward_zone == 1:
                reward_list = [0, 0, 1, 0]
            elif self.reward_zone == 5:
                reward_list = [0, 0, 0, 1]
            else:
                reward_list = [0,0,0,0]
            temp_action_vec = action_vector.copy()
            temp_action_vec[23:27] = reward_list
            self.trigger_action_vector.emit(temp_action_vec)
        else:
            self.trigger_action_vector.emit(action_vector)


        # pause and check before next action vector can be processed
        if action_vector[2] != 0:
            t0_pause = time.time()
            td_pause = time.time() - t0_pause
            while td_pause < action_vector[2]:
                self.pause_run()
                if self.thread_open_session == False:
                    return time.time() - t0_trial_start, error_count, [turn_1, turn_2], cue_on
                elif (
                        ((time.time() - self.time_start) > self.time_limit) and
                        (action_vector[0] == 2)
                ):
                    self.thread_open_session = False
                td_pause = time.time() - t0_pause
                time.sleep(0.010)

        if action_vector[0] == 4:
            return (time.time() - t0_trial_start) - td_pause, error_count, [turn_1, turn_2], cue_on
        else:
            return time.time() - t0_trial_start, error_count, [turn_1, turn_2], cue_on

    def pause_run(self):
        if self.pause_session:
            pause_time_start = time.time()
            while self.pause_session:
                time.sleep(0.050)
            pause_time_total = time.time() - pause_time_start
            self.time_limit += pause_time_total


# noinspection PyTypeChecker
class WorkerSessionVideoThread(QObject):
    finished = pyqtSignal()
    update_coordinates = pyqtSignal(str, int, int, int, int, int)
    update_image = pyqtSignal(np.ndarray, int, int, int)
    db_session_video = pyqtSignal(list)
    session_video_offset_time = 0
    thread_running = False
    zone = 0

    # gsi: general_session_info
    def __init__(self, sgi, fps=10, shutter_speed=4000, iso=4000, varThreshold=10,
                 path_to_dir=None, thread_testing=False):
        super(WorkerSessionVideoThread, self).__init__()
        self.HOST = '0.0.0.0'
        self.PORT_REQ = 5101
        self.PORT_SUB = 5102
        self.fps = fps
        self.shutter_speed = shutter_speed
        self.iso = iso
        self.varThreshold = varThreshold
        self.resolution = (480, 480)
        self.date_time = str(datetime.datetime.now()).replace(' ', '_').replace(':', '_').\
            replace('.', '_').replace('-', '_')
        self.time_stamp_backup = 0
        self.step_backup = 0

        if not thread_testing:
            self.path_to_video = (
                        path_to_dir + '/' + sgi['subject_name'] + '_' + 'vid' + '_' + str(sgi['session_number']) + '_' +
                        sgi['date'].replace('/', '') + '_' + sgi['time'].replace(':', '') + '.avi')
            self.path_to_data = (path_to_dir + '/' + sgi['subject_name'] + '_' + 'cord_data' + '_' + str(
                sgi['session_number']) + '_' +
                                 sgi['date'].replace('/', '') + '_' + sgi['time'].replace(':', '') + '.csv')
        self.session_id = sgi['session_id']

    def run(self):
        self.thread_running = True
        zone = 0
        image_frame = np.ndarray((480, 480, 3), dtype=np.uint8)
        prv_image_frame = np.ndarray((480, 480, 3), dtype=np.uint8)
        zmq_context = zmq.Context.instance()  # Using the context available from the MazeControl class
        client_req = zmq_context.socket(zmq.REQ)
        client_req.connect(f'tcp://{self.HOST}:{self.PORT_REQ}')
        client_sub = zmq_context.socket(zmq.SUB)
        client_sub.connect(f'tcp://{self.HOST}:{self.PORT_SUB}')
        client_sub.setsockopt_string(zmq.SUBSCRIBE, '')
        data_list = []
        step_correct = 0
        timestamp_correct = 0
        resolution = (480, 480)
        # Launch image server on raspi
        cmd = f"ssh -f raspberrypi-d@{self.HOST} \"sh -c \'nohup python3 ~/Code/MotionTrack_ZeroMQ_picam2_mwb.py" \
              f" {self.fps} {self.varThreshold} {self.resolution[0]} {self.resolution[0]} {self.iso}" \
              f" {self.shutter_speed} > ~/Code/Logs/ryan_camera_output_{self.date_time}.txt 2>&1 & exit\'\""
        subprocess.call(cmd, shell=True)
        # Let server get going before trying to connect to it
        time.sleep(7)

        fourcc = cv2.VideoWriter_fourcc(*'FFV1')
        out_file = cv2.VideoWriter(self.path_to_video, fourcc, self.fps, resolution)

        # Start sending frames
        client_req.send_string('Start')
        msg = client_req.recv_string()
        print('Video PID: ', msg)

        # Connect to server
        while self.thread_running:
            try:
                encoded_data = client_sub.recv()
                image_frame = msgpack.unpackb(encoded_data, object_hook=m.decode)
                np.copyto(prv_image_frame, image_frame)
            except Exception as exp:
                print('Exception occurred: ', exp)
                traceback.print_exception(type(exp), exp, exp.__traceback__)
                image_frame = copy.deepcopy(prv_image_frame)

            s1 = image_frame[0, 0, 0]
            s2 = image_frame[1, 0, 0]
            s3 = image_frame[2, 0, 0]
            s4 = image_frame[3, 0, 0]
            step = int(s4 * 1e6 + s3 * 1e4 + s2 * 1e2 + s1) + step_correct
            ts1 = image_frame[4, 0, 0]
            ts2 = image_frame[5, 0, 0]
            ts3 = image_frame[6, 0, 0]
            ts4 = image_frame[7, 0, 0]
            time_stamp = int(ts4 * 1e6 + ts3 * 1e4 + ts2 * 1e2 + ts1) + timestamp_correct
            pixel_coordinate_x = image_frame[8, 0, 0]
            pixel_coordinate_y = image_frame[9, 0, 0]
            WorkerSessionVideoThread.zone = image_frame[10, 0, 0]

            data_list.append([step, time_stamp, pixel_coordinate_x, pixel_coordinate_y,
                              WorkerSessionVideoThread.zone])
            self.update_coordinates.emit('Running',
                                         step,
                                         time_stamp,
                                         pixel_coordinate_x,
                                         pixel_coordinate_y,
                                         WorkerSessionVideoThread.zone)
            self.session_video_offset_time = time_stamp
            self.update_image.emit(image_frame,
                                   pixel_coordinate_x,
                                   pixel_coordinate_y,
                                   WorkerSessionVideoThread.zone)
            image_frame = cv2.rotate(image_frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
            out_file.write(image_frame)


        out_file.release()
        # Save coordinate data to csv file
        header = ['step', 'time_stamp', 'cord_x', 'cord_y', 'zone']
        with open(self.path_to_data, 'w', encoding='UTF8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(data_list)
        # Save paths to files in db
        self.db_session_video.emit([self.path_to_data, self.path_to_video, self.session_id])

        client_req.send_string('Stop')
        msg = client_req.recv_string()
        print(msg)
        client_sub.close()
        client_req.close()
        self.finished.emit()


class WorkerVideoThread(QObject):
    finished = pyqtSignal()
    updated_image = pyqtSignal(np.ndarray, int, int, int)
    update_button = pyqtSignal()
    thread_open_video = False
    zone = 0

    def __init__(self, fps=10, shutter_speed=4000, iso=4000, varThreshold=10):
        super(WorkerVideoThread, self).__init__()
        self.HOST = '0.0.0.0'
        self.PORT_REQ = 5101
        self.PORT_SUB = 5102
        self.fps = fps
        self.shutter_speed = shutter_speed
        self.iso = iso
        self.varThreshold = varThreshold
        self.resolution = (480, 480)
        self.date_time = str(datetime.datetime.now()).replace(' ', '_').replace(':', '_').\
            replace('.', '_').replace('-', '_')
        self.thread_open_video = True



    # Streams video only without running a behavior session
    def run(self):
        zone = 0
        image_frame = np.ndarray((480, 480, 3), dtype=np.uint8)
        prv_image_frame = np.ndarray((480,480, 3), dtype=np.uint8)
        zmq_context = zmq.Context.instance()  # Using the context available from the MazeControl class
        client_req = zmq_context.socket(zmq.REQ)
        client_req.connect(f'tcp://{self.HOST}:{self.PORT_REQ}')
        client_sub = zmq_context.socket(zmq.SUB)
        client_sub.connect(f'tcp://{self.HOST}:{self.PORT_SUB}')
        client_sub.setsockopt_string(zmq.SUBSCRIBE, '')

        # Launch image server on raspi
        cmd = f"ssh -f raspberrypi-d@{self.HOST} \"sh -c \'nohup python3 ~/Code/MotionTrack_ZeroMQ_picam2_mwb.py" \
              f" {self.fps} {self.varThreshold} {self.resolution[0]} {self.resolution[0]} {self.iso}" \
              f" {self.shutter_speed} > ~/Code/Logs/ryan_camera_output_{self.date_time}.txt 2>&1 & exit\'\""
        subprocess.call(cmd, shell=True)
        # Let server get going before trying to connect to it
        time.sleep(3)

        # Start sending frames
        client_req.send_string('Start')
        msg = client_req.recv_string()
        print('Video PID: ', msg)

        while self.thread_open_video:
            try:
                encoded_data = client_sub.recv()
                image_frame = msgpack.unpackb(encoded_data, object_hook=m.decode)
                np.copyto(prv_image_frame, image_frame)
            except Exception as exp:
                print('Exception occurred: ', exp)
                traceback.print_exception(type(exp), exp, exp.__traceback__)
                image_frame = copy.deepcopy(prv_image_frame)

            pixel_coordinate_x = image_frame[8, 0, 0]
            pixel_coordinate_y = image_frame[9, 0, 0]
            WorkerVideoThread.zone = image_frame[10, 0, 0]

            self.updated_image.emit(image_frame,
                                    pixel_coordinate_x,
                                    pixel_coordinate_y,
                                    WorkerVideoThread.zone)

        client_req.send_string('Stop')
        msg = client_req.recv_string()
        print(msg)
        client_sub.close()
        client_req.close()
        self.update_button.emit()
        self.finished.emit()
        print('Socket Client Disconnected')


class TableStaticModel(QAbstractTableModel):
    def __init__(self, header, data):
        super(TableStaticModel, self).__init__()
        self._data = data
        self.header = header

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            return self._data[index.row()][index.column()]

        if role == Qt.TextAlignmentRole:
            # value = self._data[index.row()][index.column()]
            return Qt.AlignCenter

    def rowCount(self, index):
        return len(self._data)

    def columnCount(self, index):
        return len(self._data[0])

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return QVariant(self.header[col])
        return QVariant()

    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled


class TableEditModel(QAbstractTableModel):
    def __init__(self, header, data):
        super(TableEditModel, self).__init__()
        self._data = data
        self.header = header

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            if role == Qt.DisplayRole or role == Qt.EditRole:
                value = self._data[index.row()][index.column()]
                if index.column() == 0:
                    return str(value)
                else:
                    return int(value)
            if role == Qt.TextAlignmentRole:
                value = self._data[index.row()][index.column()]
                return Qt.AlignCenter

    def rowCount(self, index):
        return len(self._data)

    def columnCount(self, index):
        return len(self._data[0])

    def setData(self, index, value, role):
        if role == Qt.EditRole:
            if index.column() != 0:
                self._data[index.row()][index.column()] = int(value)
                return True
            else:
                self._data[index.row()][index.column()] = value
                return True
        return False

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return QVariant(self.header[col])
        return QVariant()

    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable


class TrialModel:
    def __init__(self):
        self.model = self._create_model()

    @staticmethod
    def _create_model():
        table_model = QSqlTableModel()
        table_model.setTable('trial')
        table_model.setEditStrategy(QSqlTableModel.OnFieldChange)
        table_model.select()
        subjects_model_header = ('No.', 'start', 'goal', 'cue', 'time', 'errors', 'typ', '', '')
        for column_idx, header in enumerate(subjects_model_header):
            table_model.setHeaderData(column_idx, Qt.Horizontal, header)
        return table_model


class SubjectsModel:
    def __init__(self):
        self.model = self._create_model()

    @staticmethod
    def _create_model():
        table_model = QSqlTableModel()
        table_model.setTable('subjects')
        table_model.setEditStrategy(QSqlTableModel.OnFieldChange)
        table_model.select()
        subjects_model_header = ('ID', 'name', 'sex', 'current behavior', 'last\nsess', 'conf', 'typ', 'active','',
                                 'rew vol')
        for column_idx, header in enumerate(subjects_model_header):
            table_model.setHeaderData(column_idx, Qt.Horizontal, header)
        return table_model

    def add_subject(self, data):
        rows = self.model.rowCount()
        self.model.insertRows(rows, 1)
        for column, field in enumerate(data[:6]):
            self.model.setData(self.model.index(rows, column + 1), field)
        self.model.setData(self.model.index(rows, 9), data[6])
        self.model.submitAll()
        self.model.select()

    def num_rows(self):
        return self.model.rowCount()


class SessionModel:
    def __init__(self):
        self.model = self._create_model()

    @staticmethod
    def _create_model():
        table_model = QSqlTableModel()
        table_model.setTable('session')
        table_model.setEditStrategy(QSqlTableModel.OnFieldChange)
        subjects_model_header = ('', 'No', 'date', 'time', 'behavior', 'conf', 'typ', '', '', '', '', '', '')
        for column_idx, header in enumerate(subjects_model_header):
            table_model.setHeaderData(column_idx, Qt.Horizontal, header)
        table_model.select()

        return table_model


class AddSubjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle('Add Subject')
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.data = None
        self.setupUI()

    def setupUI(self):
        self.name_field = QLineEdit()
        self.name_field.setObjectName('name')

        self.list_sex = ['F', 'M']
        combo_box_sex = QComboBox()
        combo_box_sex.addItems(self.list_sex)
        self.sex_field = QLineEdit()
        self.sex_field.setObjectName('sex')
        combo_box_sex.setLineEdit(self.sex_field)

        self.list_behavior = ['Landmark Guided Task',
                              'Discriminative Stimulus Guided Task',
                              'Path Integration Guided Task',
                              'Path Discrimination Guided Task']
        combo_box_behavior = QComboBox()
        combo_box_behavior.addItems(self.list_behavior)
        self.behavior_field = QLineEdit()
        self.behavior_field.setObjectName('behavior')
        combo_box_behavior.setLineEdit(self.behavior_field)

        self.list_cue_reward_orientation = ['N/NE',
                                            'N/SE',
                                            'N/SW',
                                            'N/NW']
        combo_box_cue_reward_orientation = QComboBox()
        combo_box_cue_reward_orientation.addItems(self.list_cue_reward_orientation)
        self.cue_goal_field = QLineEdit()
        self.cue_goal_field.setObjectName('cue_goal_orientation')
        combo_box_cue_reward_orientation.setLineEdit(self.cue_goal_field)

        # retained cue defined by amount of separation between cue/goal indexes
        self.list_session_type_cue = ['Exposure', 'LGTOM', 'Fixed LGT', 'Rotating LGT 2', 'Rotating LGT 4', 'RDT Task', 'None']
        combo_box_session_type = QComboBox()
        combo_box_session_type.addItems(self.list_session_type_cue)
        self.session_type_field = QLineEdit()
        self.session_type_field.setObjectName('session_type')
        combo_box_session_type.setLineEdit(self.session_type_field)

        self.list_reward_volume = ['50', '100', '150', '200', '250', '300']
        combo_box_reward_volume = QComboBox()
        combo_box_reward_volume.addItems(self.list_reward_volume)
        self.reward_volume_field = QLineEdit()
        self.reward_volume_field.setObjectName('reward_volume')
        combo_box_reward_volume.setLineEdit(self.reward_volume_field)

        layout = QFormLayout()
        layout.addRow('Name:', self.name_field)
        layout.addRow('Sex:', combo_box_sex)
        layout.addRow('Behavior:', combo_box_behavior)
        layout.addRow('Cue/Goal:', combo_box_cue_reward_orientation)
        layout.addRow('Session Type:', combo_box_session_type)
        layout.addRow('Reward Volume:', combo_box_reward_volume)
        self.layout.addLayout(layout)

        # Dialog box buttons
        self.button_box = QDialogButtonBox(self)
        self.button_box.setOrientation(Qt.Horizontal)
        self.button_box.setStandardButtons(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def accept(self):
        self.data = []
        if not self.name_field.text():
            QMessageBox.critical(
                self,
                'Error!',
                'You must provide subject\'s name.',
            )
            self.data = None
            return
        self.data.append(self.name_field.text())

        if (self.sex_field.text() == self.list_sex[0] or
                self.sex_field.text() == self.list_sex[1]):
            self.data.append(self.sex_field.text())
        else:
            QMessageBox.critical(
                self,
                'Error!',
                f'Subject\'s sex empty or improperly entered',
            )
            self.data = None
            return

        if (self.behavior_field.text() == self.list_behavior[0] or
                self.behavior_field.text() == self.list_behavior[1] or
                self.behavior_field.text() == self.list_behavior[2] or
                self.behavior_field.text() == self.list_behavior[3]):
            self.data.append(self.behavior_field.text())
        else:
            QMessageBox.critical(
                self,
                'Error!',
                f'Subject\'s behavior empty or improperly entered',
            )
            self.data = None
            return

        # Insert last session of none here
        self.data.append('None')

        if (self.cue_goal_field.text() == self.list_cue_reward_orientation[0] or
                self.cue_goal_field.text() == self.list_cue_reward_orientation[1] or
                self.cue_goal_field.text() == self.list_cue_reward_orientation[2] or
                self.cue_goal_field.text() == self.list_cue_reward_orientation[3]):

            self.data.append(self.cue_goal_field.text())
        else:
            QMessageBox.critical(
                self,
                'Error!',
                f'Subject\'s behavior cue/goal data empty or improperly entered',
            )
            self.data = None
            return

        if (self.session_type_field.text() == self.list_session_type_cue[0] or
            self.session_type_field.text() == self.list_session_type_cue[1] or
            self.session_type_field.text() == self.list_session_type_cue[2] or
            self.session_type_field.text() == self.list_session_type_cue[3] or
            self.session_type_field.text() == self.list_session_type_cue[4]):

            self.data.append(self.session_type_field.text())
        else:
            QMessageBox.critical(
                self,
                'Error!',
                f'Subject\'s cue retained empty or improperly entered',
            )
            self.data = None
            return

        if (self.reward_volume_field.text() == self.list_reward_volume[0] or
                self.reward_volume_field.text() == self.list_reward_volume[1] or
                self.reward_volume_field.text() == self.list_reward_volume[2] or
                self.reward_volume_field.text() == self.list_reward_volume[3] or
                self.reward_volume_field.text() == self.list_reward_volume[4] or
                self.reward_volume_field.text() == self.list_reward_volume[5]):
            self.data.append(self.reward_volume_field.text())
        else:
            QMessageBox.critical(
                self,
                'Error!',
                f'Subject\'s reward volume empty or improperly entered',
            )
            self.data = None
            return
        #Set delay to 0
        self.data.append('0')

        if not self.data:
            return

        super().accept()


class AlignCenterDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super(AlignCenterDelegate, self).initStyleOption(option, index)
        option.displayAlignment = Qt.AlignCenter


class QHLine(QFrame):
    def __init__(self):
        super(QHLine, self).__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Plain)


class SoundControl:
    def __init__(self):
        self.sound_type = mp.Value('i', 0)
        self.sound_process_running = mp.Value('b', False)
        self.volume = 90
        self.p_sound = None

    def player(self):
        os.system(f"amixer -D pulse sset Master {self.volume}%")
        sampling_freq = 192000
        secs = 0.1
        p = pyaudio.PyAudio()
        # find the correct index
        deviceFlag = False
        for device in range(p.get_default_host_api_info()['defaultOutputDevice']):
            curname = p.get_device_info_by_index(device)['name']
            if 'DH80S' in curname:
                stream = p.open(rate=sampling_freq, channels=2, format=pyaudio.paFloat32,
                                output=True, output_device_index=device,
                                frames_per_buffer=int(sampling_freq * secs),
                                stream_callback=self.callback_maker(sampling_freq, secs), )
                deviceFlag = True
                break
        if not deviceFlag:
            print('Cannot find the sound dac&amp!')
        else:
            print('Sound start ' + str(stream.is_active()))
            # close stream if leave the loop
            while stream.is_active():
                time.sleep(0.1)
            stream.stop_stream()
            stream.close()
        p.terminate()
        print('Sound ended')

    def callback_maker(self, sampling_freq, secs):
        def make_sound(in_data, frame_count, time_info, status):
            mean_WN = 0
            std_WN = 1
            if self.sound_process_running.value:
                if self.sound_type.value == 0:
                    samples = np.zeros(int(secs * sampling_freq))
                elif self.sound_type.value == 1:
                    samples = np.random.normal(mean_WN, std_WN, size=int(secs * sampling_freq))

                # make the signal stereo (two columns)
                samples = samples[:, np.newaxis]
                samples = np.hstack((samples, samples))
                sound = samples.astype(np.float32).tobytes()
                return sound, pyaudio.paContinue
            else:
                samples = np.zeros(int(secs * sampling_freq))
                samples = samples[:, np.newaxis]
                samples = np.hstack((samples, samples))
                sound = samples.astype(np.float32).tobytes()
                return sound, pyaudio.paComplete

        return make_sound

    def start_player(self):
        self.sound_process_running.value = True
        self.p_sound = mp.Process(target=self.player)
        self.p_sound.start()

    def stop_player(self):
        self.sound_process_running.value = False

    def play_sound(self, sound_type):
        self.sound_type.value = int(sound_type)

    def set_volume(self, volume):
        os.system(f"amixer -D pulse sset Master {volume}%")


# noinspection PyUnresolvedReferences,PyArgumentList
class MainWindow(QMainWindow):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.set_window_right()
        self.init_shared_objects()
        self.setup_main_Window()
        self.show()
        self.control_connect_display()
        self.control_room_lights_bright_off()

    def set_window_right(self):
        self.move(QPoint(0, 0))

    def init_shared_objects(self):
        # Any pyqt objects that are shared across functions will be created where they are used in the layout
        # DATABASE CONNECTION
        self.db_connection = QSqlDatabase.addDatabase('QSQLITE')
        self.db_connection.setDatabaseName('MazeControl.db')
        self.db_conn_dir = sqlite3.connect("/home/blairlab/PycharmProjects/MazeControl/MazeControl.db")
        self.db_cursor = self.db_conn_dir.cursor()

        # Create a SoundControl Class Instance
        self.sound_control = SoundControl()

        # MODBUS CLASSES
        timeout_arduino_modbus = 0.05
        timeout_raspi_modbus = 0.25
        self.modbus_actuator_list = []
        modbus_actuator_id = [1, 2, 3, 5, 6, 7, 9, 10, 11, 13, 14, 15, 18, 19, 20, 17]
        for i in modbus_actuator_id:
            self.modbus_actuator_list.append(mzc.Actuator(i, timeout_arduino_modbus, 1))

        self.modbus_syringe_pump_list = []
        modbus_syringe_pump_id = [4, 16, 12, 8]
        for i in modbus_syringe_pump_id:
            self.modbus_syringe_pump_list.append(mzc.SyringePump(i, timeout_arduino_modbus, 1))

        self.modbus_cue_light_list = []
        modbus_cue_light_id = [2, 6, 10, 14]
        for i in modbus_cue_light_id:
            self.modbus_cue_light_list.append(mzc.CueLight(i, timeout_arduino_modbus, 1))

        self.modbus_room_lights = mzc.RoomLights(21, timeout_arduino_modbus, 1)

        self.monitor_cue = mzc.StimulusDisplay()

        # Add saved variables from json file
        with open('actuator_parameters.json', ) as f:
            self.actuator_parameters = json.load(f)
        with open('syringe_pump_parameters_list_30ml.json', ) as f:
            self.syringe_pump_parameters_list = json.load(f)
        self.syringe_pump_parameters = self.syringe_pump_parameters_list[2]
        #
        rat_table_headers = ['name', 'sex', 'behavior', 'cue/goal', 'state', 'last session']
        # FUNCTION VARIABLES
        # State variables that represent states of different components in maze
        # Binary list of barrier states index key [0:1, 1:2, ...]
        self.state_barrier_list = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        # 0: Off, 1: On index key[0:1, 1:2,...]
        self.state_cue_light_list = [0, 0, 0, 0]
        # 0: Off, 1: On index key[0:North, 1:East, 2:South, 3:West, 4:None]
        # TODO: Add state of lights being on

        self.state_cue_list = [0, 0, 0, 0, 0]

        # 0: Off, 1: On
        self.state_cue_display = [0]

        # 0: Black screen & Lights Off, 1: White screen & Lights On, 2: Grey screen & Lights Off
        self.state_room_lights = [0]

        self.state_IR_lights = [0]
        # 0: Not running, 1: running

        self.state_session = [0]
        self.state_session_video = [0]
        self.state_session_control = [0]
        # Monitors video only state and passed WorkerVideoThread in __init__
        self.state_video = [0]

        # List of state variables to pass by reference to threads
        self.state_list = [self.state_barrier_list, self.state_cue_light_list, self.state_cue_list,
                           self.state_cue_display, self.state_room_lights, self.state_session,
                           self.state_session_video, self.state_session_control, self.state_video,
                           self.state_IR_lights]

        # index value pairing for LMGT is as follows
        # 0: Action-type (0: Presession, 1: ITI, 2: Pretrial, 3: Trial start,
        #   4: trial end)
        # 1: trigger zone on maze that causes configuration. Note: button
        # press for pretrial
        # 2: delay-period, used to delay time until trigger zone causes action.
        # primarly used for pause period during reward consumption while cue
        # stay on briefly.
        # 3-18: Barrier state 0 for down and 1 for up 3 is B1 and 4 is B2 ....
        # 19-22: Cue config index key [20:N, 21:E, 22:S, 23:W]
        # 23-26: reward config, index key [0:NE, 1:SE, 2:SW, 3:NW]
        # 27-30: light-config, index [0:UV1, 1:UV2, 2:UV3, 3:UV4]
        # 31: index in action vector list
        # LMGT: Landmark guided task
        # 0: presesion start arm
        presession_n_vec_LMGT = [0,0,0, 0,0,0,1,0,1,0,0,0,0,0,0,0,1,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        presession_e_vec_LMGT = [0,0,0, 1,0,1,0,0,0,0,0,0,0,0,0,1,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        presession_s_vec_LMGT = [0,0,0, 0,0,0,0,0,0,0,0,0,1,0,1,0,0,0,1, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        presession_w_vec_LMGT = [0,0,0, 0,0,0,0,0,0,1,0,1,0,0,0,0,0,1,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        # 1 ITI start arm
        iti_n_vec_LMGT = [1,0,0, 0,1,0,0,0,0,0,1,0,0,1,0,0,1,0,1, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        iti_e_vec_LMGT = [1,0,0, 0,0,0,0,1,0,0,1,0,0,1,0,1,0,1,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        iti_s_vec_LMGT = [1,0,0, 0,1,0,0,1,0,0,1,0,0,0,0,0,1,0,1, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        iti_w_vec_LMGT = [1,0,0, 0,1,0,0,1,0,0,0,0,0,1,0,1,0,1,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        # 2: pretrial action vectors start arm and cue orientations
        # north start arm (Note changing delay time 0 from 1)
        pretrial_n_n_vec_LMGT = [2,12,10, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,1, 1,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_n_e_vec_LMGT = [2,12,10, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,1, 0,1,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_n_s_vec_LMGT = [2,12,10, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,1, 0,0,1,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_n_w_vec_LMGT = [2,12,10, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,1, 0,0,0,1, 0,0,0,0, 0,0,0,0, -1]
        # east start arm
        pretrial_e_n_vec_LMGT = [2,15,10, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,1,0, 1,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_e_e_vec_LMGT = [2,15,10, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,1,0, 0,1,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_e_s_vec_LMGT = [2,15,10, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,1,0, 0,0,1,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_e_w_vec_LMGT = [2,15,10, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,1,0, 0,0,0,1, 0,0,0,0, 0,0,0,0, -1]
        # south start arm
        pretrial_s_n_vec_LMGT = [2,10,10, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,1, 1,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_s_e_vec_LMGT = [2,10,10, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,1, 0,1,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_s_s_vec_LMGT = [2,10,10, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,1, 0,0,1,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_s_w_vec_LMGT = [2,10,10, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,1, 0,0,0,1, 0,0,0,0, 0,0,0,0, -1]
        # west start arm
        pretrial_w_n_vec_LMGT = [2,7,10, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,1,0, 1,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_w_e_vec_LMGT = [2,7,10, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,1,0, 0,1,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_w_s_vec_LMGT = [2,7,10, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,1,0, 0,0,1,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_w_w_vec_LMGT = [2,7,10, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,1,0, 0,0,0,1, 0,0,0,0, 0,0,0,0, -1]

        # 3:trial start action vectors startarm and cue orientations
        # north start arm
        trialstart_n_n_vec_LMGT = [3,13,0, 0,0,0,1,0,1,0,0,0,1,0,1,0,0,0,1, 1,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_n_e_vec_LMGT = [3,13,0, 0,0,0,1,0,1,0,0,0,1,0,1,0,0,0,1, 0,1,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_n_s_vec_LMGT = [3,13,0, 0,0,0,1,0,1,0,0,0,1,0,1,0,0,0,1, 0,0,1,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_n_w_vec_LMGT = [3,13,0, 0,0,0,1,0,1,0,0,0,1,0,1,0,0,0,1, 0,0,0,1, 0,0,0,0, 0,0,0,0, -1]
        # east start arm
        trialstart_e_n_vec_LMGT = [3,19,0, 1,0,1,0,0,0,1,0,1,0,0,0,0,0,1,0, 1,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_e_e_vec_LMGT = [3,19,0, 1,0,1,0,0,0,1,0,1,0,0,0,0,0,1,0, 0,1,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_e_s_vec_LMGT = [3,19,0, 1,0,1,0,0,0,1,0,1,0,0,0,0,0,1,0, 0,0,1,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_e_w_vec_LMGT = [3,19,0, 1,0,1,0,0,0,1,0,1,0,0,0,0,0,1,0, 0,0,0,1, 0,0,0,0, 0,0,0,0, -1]
        # south start arm
        trialstart_s_n_vec_LMGT = [3,9,0, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,0, 1,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_s_e_vec_LMGT = [3,9,0, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,0, 0,1,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_s_s_vec_LMGT = [3,9,0, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,0, 0,0,1,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_s_w_vec_LMGT = [3,9,0, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,0, 0,0,0,1, 0,0,0,0, 0,0,0,0, -1]
        # west start arm
        trialstart_w_n_vec_LMGT = [3,3,0, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,0,0, 1,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_w_e_vec_LMGT = [3,3,0, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,0,0, 0,1,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_w_s_vec_LMGT = [3,3,0, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,0,0, 0,0,1,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_w_w_vec_LMGT = [3,3,0, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,0,0, 0,0,0,1, 0,0,0,0, 0,0,0,0, -1]
        # 4 trial end (reward): action vectors reward and cue orientation
        # northeast goal
        trialend_ne_n_vec_LGMT = [4,21,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 1,0,0,0, 1,0,0,0, 0,0,0,0, -1]
        trialend_ne_e_vec_LGMT = [4,21,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,1,0,0, 1,0,0,0, 0,0,0,0, -1]
        trialend_ne_s_vec_LGMT = [4,21,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,1,0, 1,0,0,0, 0,0,0,0, -1]
        trialend_ne_w_vec_LGMT = [4,21,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,1, 1,0,0,0, 0,0,0,0, -1]
        # southeast goal
        trialend_se_n_vec_LGMT = [4,17,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 1,0,0,0, 0,1,0,0, 0,0,0,0, -1]
        trialend_se_e_vec_LGMT = [4,17,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,1,0,0, 0,1,0,0, 0,0,0,0, -1]
        trialend_se_s_vec_LGMT = [4,17,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,1,0, 0,1,0,0, 0,0,0,0, -1]
        trialend_se_w_vec_LGMT = [4,17,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,1, 0,1,0,0, 0,0,0,0, -1]
        # southwest goal
        trialend_sw_n_vec_LGMT = [4,1,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 1,0,0,0, 0,0,1,0, 0,0,0,0, -1]
        trialend_sw_e_vec_LGMT = [4,1,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,0, -1]
        trialend_sw_s_vec_LGMT = [4,1,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,1,0, 0,0,1,0, 0,0,0,0, -1]
        trialend_sw_w_vec_LGMT = [4,1,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,1, 0,0,1,0, 0,0,0,0, -1]
        # northwest goal
        trialend_nw_n_vec_LGMT = [4,5,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 1,0,0,0, 0,0,0,1, 0,0,0,0, -1]
        trialend_nw_e_vec_LGMT = [4,5,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,1,0,0, 0,0,0,1, 0,0,0,0, -1]
        trialend_nw_s_vec_LGMT = [4,5,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,1,0, 0,0,0,1, 0,0,0,0, -1]
        trialend_nw_w_vec_LGMT = [4,5,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,1, 0,0,0,1, 0,0,0,0, -1]

        # action states matrix LGMT
        # matrix of predefined action vectors
        self.action_states_matrix_LMGT = [
            [presession_n_vec_LMGT, presession_e_vec_LMGT, presession_s_vec_LMGT, presession_w_vec_LMGT],
            [iti_n_vec_LMGT, iti_e_vec_LMGT, iti_s_vec_LMGT, iti_w_vec_LMGT],
            [[pretrial_n_n_vec_LMGT, pretrial_n_e_vec_LMGT, pretrial_n_s_vec_LMGT, pretrial_n_w_vec_LMGT],
             [pretrial_e_n_vec_LMGT, pretrial_e_e_vec_LMGT, pretrial_e_s_vec_LMGT, pretrial_e_w_vec_LMGT],
             [pretrial_s_n_vec_LMGT, pretrial_s_e_vec_LMGT, pretrial_s_s_vec_LMGT, pretrial_s_w_vec_LMGT],
             [pretrial_w_n_vec_LMGT, pretrial_w_e_vec_LMGT, pretrial_w_s_vec_LMGT, pretrial_w_w_vec_LMGT]
             ],
            [[trialstart_n_n_vec_LMGT, trialstart_n_e_vec_LMGT, trialstart_n_s_vec_LMGT, trialstart_n_w_vec_LMGT],
             [trialstart_e_n_vec_LMGT, trialstart_e_e_vec_LMGT, trialstart_e_s_vec_LMGT, trialstart_e_w_vec_LMGT],
             [trialstart_s_n_vec_LMGT, trialstart_s_e_vec_LMGT, trialstart_s_s_vec_LMGT, trialstart_s_w_vec_LMGT],
             [trialstart_w_n_vec_LMGT, trialstart_w_e_vec_LMGT, trialstart_w_s_vec_LMGT, trialstart_w_w_vec_LMGT]
             ],
            [[trialend_ne_n_vec_LGMT, trialend_ne_e_vec_LGMT, trialend_ne_s_vec_LGMT, trialend_ne_w_vec_LGMT],
             [trialend_se_n_vec_LGMT, trialend_se_e_vec_LGMT, trialend_se_s_vec_LGMT, trialend_se_w_vec_LGMT],
             [trialend_sw_n_vec_LGMT, trialend_sw_e_vec_LGMT, trialend_sw_s_vec_LGMT, trialend_sw_w_vec_LGMT],
             [trialend_nw_n_vec_LGMT, trialend_nw_e_vec_LGMT, trialend_nw_s_vec_LGMT, trialend_nw_w_vec_LGMT]
             ]
        ]

        # Landmark Guided Task Open Maze LMGTOM: Start is the entire middle of the maze.
        # Same comments on indexing as for LMGT just different configurations for each part of the session
        # 0 PRESESSION
        presession_n_vec_LMGTOM = [0,0,0, 0,1,0,0,1,0,0,1,0,0,1,0,0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        presession_e_vec_LMGTOM = [0,0,0, 0,1,0,0,1,0,0,1,0,0,1,0,0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        presession_s_vec_LMGTOM = [0,0,0, 0,1,0,0,1,0,0,1,0,0,1,0,0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        presession_w_vec_LMGTOM = [0,0,0, 0,1,0,0,1,0,0,1,0,0,1,0,0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]

        # 1 ITI
        iti_n_vec_LMGTOM = [1,0,0, 0,1,0,0,0,0,0,1,0,0,1,0,0,0,0,0, 0,0,0,0, 0,0,0,0, 0,1,0,0, -1]
        iti_e_vec_LMGTOM = [1,0,0, 0,0,0,0,1,0,0,1,0,0,1,0,0,0,0,0, 0,0,0,0, 0,0,0,0, 1,0,0,0, -1]
        iti_s_vec_LMGTOM = [1,0,0, 0,1,0,0,1,0,0,1,0,0,0,0,0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,1, -1]
        iti_w_vec_LMGTOM = [1,0,0, 0,1,0,0,1,0,0,0,0,0,1,0,0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,1,0, -1]

        # 2 PRETRIAL
        # entering north start arm
        pretrial_n_n_vec_LMGTOM = [2,11,10, 0,1,0,0,1,0,0,1,0,0,1,0,0,0,0,0, 1,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_n_e_vec_LMGTOM = [2,11,10, 0,1,0,0,1,0,0,1,0,0,1,0,0,0,0,0, 0,1,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_n_s_vec_LMGTOM = [2,11,10, 0,1,0,0,1,0,0,1,0,0,1,0,0,0,0,0, 0,0,1,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_n_w_vec_LMGTOM = [2,11,10, 0,1,0,0,1,0,0,1,0,0,1,0,0,0,0,0, 0,0,0,1, 0,0,0,0, 0,0,0,0, -1]
        # entering east start arm
        pretrial_e_n_vec_LMGTOM = [2,11,10, 0,1,0,0,1,0,0,1,0,0,1,0,0,0,0,0, 1,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_e_e_vec_LMGTOM = [2,11,10, 0,1,0,0,1,0,0,1,0,0,1,0,0,0,0,0, 0,1,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_e_s_vec_LMGTOM = [2,11,10, 0,1,0,0,1,0,0,1,0,0,1,0,0,0,0,0, 0,0,1,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_e_w_vec_LMGTOM = [2,11,10, 0,1,0,0,1,0,0,1,0,0,1,0,0,0,0,0, 0,0,0,1, 0,0,0,0, 0,0,0,0, -1]
        # entering south start arm
        pretrial_s_n_vec_LMGTOM = [2,11,10, 0,1,0,0,1,0,0,1,0,0,1,0,0,0,0,0, 1,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_s_e_vec_LMGTOM = [2,11,10, 0,1,0,0,1,0,0,1,0,0,1,0,0,0,0,0, 0,1,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_s_s_vec_LMGTOM = [2,11,10, 0,1,0,0,1,0,0,1,0,0,1,0,0,0,0,0, 0,0,1,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_s_w_vec_LMGTOM = [2,11,10, 0,1,0,0,1,0,0,1,0,0,1,0,0,0,0,0, 0,0,0,1, 0,0,0,0, 0,0,0,0, -1]
        # entering west start arm
        pretrial_w_n_vec_LMGTOM = [2,11,10, 0,1,0,0,1,0,0,1,0,0,1,0,0,0,0,0, 1,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_w_e_vec_LMGTOM = [2,11,10, 0,1,0,0,1,0,0,1,0,0,1,0,0,0,0,0, 0,1,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_w_s_vec_LMGTOM = [2,11,10, 0,1,0,0,1,0,0,1,0,0,1,0,0,0,0,0, 0,0,1,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_w_w_vec_LMGTOM = [2,11,10, 0,1,0,0,1,0,0,1,0,0,1,0,0,0,0,0, 0,0,0,1, 0,0,0,0, 0,0,0,0, -1]

        # 3 TRIAL START
        trialstart_n_n_vec_LMGTOM = [3,11,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 1,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_n_e_vec_LMGTOM = [3,11,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,1,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_n_s_vec_LMGTOM = [3,11,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,1,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_n_w_vec_LMGTOM = [3,11,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,1, 0,0,0,0, 0,0,0,0, -1]

        trialstart_e_n_vec_LMGTOM = [3,11,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 1,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_e_e_vec_LMGTOM = [3,11,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,1,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_e_s_vec_LMGTOM = [3,11,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,1,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_e_w_vec_LMGTOM = [3,11,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,1, 0,0,0,0, 0,0,0,0, -1]

        trialstart_s_n_vec_LMGTOM = [3,11,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 1,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_s_e_vec_LMGTOM = [3,11,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,1,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_s_s_vec_LMGTOM = [3,11,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,1,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_s_w_vec_LMGTOM = [3,11,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,1, 0,0,0,0, 0,0,0,0, -1]

        trialstart_w_n_vec_LMGTOM = [3,11,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 1,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_w_e_vec_LMGTOM = [3,11,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,1,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_w_s_vec_LMGTOM = [3,11,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,1,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_w_w_vec_LMGTOM = [3,11,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,1, 0,0,0,0, 0,0,0,0, -1]

        # 4 TRIAL END
        # northeast goal
        trialend_ne_n_vec_LMGTOM = [4,21,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 1,0,0,0, 1,0,0,0, 0,0,0,0, -1]
        trialend_ne_e_vec_LMGTOM = [4,21,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,1,0,0, 1,0,0,0, 0,0,0,0, -1]
        trialend_ne_s_vec_LMGTOM = [4,21,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,1,0, 1,0,0,0, 0,0,0,0, -1]
        trialend_ne_w_vec_LMGTOM = [4,21,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,1, 1,0,0,0, 0,0,0,0, -1]
        # southeast goal
        trialend_se_n_vec_LMGTOM = [4,17,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 1,0,0,0, 0,1,0,0, 0,0,0,0, -1]
        trialend_se_e_vec_LMGTOM = [4,17,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,1,0,0, 0,1,0,0, 0,0,0,0, -1]
        trialend_se_s_vec_LMGTOM = [4,17,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,1,0, 0,1,0,0, 0,0,0,0, -1]
        trialend_se_w_vec_LMGTOM = [4,17,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,1, 0,1,0,0, 0,0,0,0, -1]
        # southwest goal
        trialend_sw_n_vec_LMGTOM = [4,1,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 1,0,0,0, 0,0,1,0, 0,0,0,0, -1]
        trialend_sw_e_vec_LMGTOM = [4,1,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,0, -1]
        trialend_sw_s_vec_LMGTOM = [4,1,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,1,0, 0,0,1,0, 0,0,0,0, -1]
        trialend_sw_w_vec_LMGTOM = [4,1,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,1, 0,0,1,0, 0,0,0,0, -1]
        # northwest goal
        trialend_nw_n_vec_LMGTOM = [4,5,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 1,0,0,0, 0,0,0,1, 0,0,0,0, -1]
        trialend_nw_e_vec_LMGTOM = [4,5,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,1,0,0, 0,0,0,1, 0,0,0,0, -1]
        trialend_nw_s_vec_LMGTOM = [4,5,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,1,0, 0,0,0,1, 0,0,0,0, -1]
        trialend_nw_w_vec_LMGTOM = [4,5,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,1, 0,0,0,1, 0,0,0,0, -1]

        self.action_states_matrix_LMGTOM = [
            [presession_n_vec_LMGTOM, presession_e_vec_LMGTOM, presession_s_vec_LMGTOM, presession_w_vec_LMGTOM],
            [iti_n_vec_LMGTOM, iti_e_vec_LMGTOM, iti_s_vec_LMGTOM, iti_w_vec_LMGTOM],
            [[pretrial_n_n_vec_LMGTOM, pretrial_n_e_vec_LMGTOM, pretrial_n_s_vec_LMGTOM, pretrial_n_w_vec_LMGTOM],
             [pretrial_e_n_vec_LMGTOM, pretrial_e_e_vec_LMGTOM, pretrial_e_s_vec_LMGTOM, pretrial_e_w_vec_LMGTOM],
             [pretrial_s_n_vec_LMGTOM, pretrial_s_e_vec_LMGTOM, pretrial_s_s_vec_LMGTOM, pretrial_s_w_vec_LMGTOM],
             [pretrial_w_n_vec_LMGTOM, pretrial_w_e_vec_LMGTOM, pretrial_w_s_vec_LMGTOM, pretrial_w_w_vec_LMGTOM]
             ],
            [[trialstart_n_n_vec_LMGTOM, trialstart_n_e_vec_LMGTOM, trialstart_n_s_vec_LMGTOM, trialstart_n_w_vec_LMGTOM],
             [trialstart_e_n_vec_LMGTOM, trialstart_e_e_vec_LMGTOM, trialstart_e_s_vec_LMGTOM, trialstart_e_w_vec_LMGTOM],
             [trialstart_s_n_vec_LMGTOM, trialstart_s_e_vec_LMGTOM, trialstart_s_s_vec_LMGTOM, trialstart_s_w_vec_LMGTOM],
             [trialstart_w_n_vec_LMGTOM, trialstart_w_e_vec_LMGTOM, trialstart_w_s_vec_LMGTOM, trialstart_w_w_vec_LMGTOM]
             ],
            [[trialend_ne_n_vec_LMGTOM, trialend_ne_e_vec_LMGTOM, trialend_ne_s_vec_LMGTOM, trialend_ne_w_vec_LMGTOM],
             [trialend_se_n_vec_LMGTOM, trialend_se_e_vec_LMGTOM, trialend_se_s_vec_LMGTOM, trialend_se_w_vec_LMGTOM],
             [trialend_sw_n_vec_LMGTOM, trialend_sw_e_vec_LMGTOM, trialend_sw_s_vec_LMGTOM, trialend_sw_w_vec_LMGTOM],
             [trialend_nw_n_vec_LMGTOM, trialend_nw_e_vec_LMGTOM, trialend_nw_s_vec_LMGTOM, trialend_nw_w_vec_LMGTOM]
             ]
        ]

        #PATH INTEGRATION GUIDED TASK
        # index value pairing for PIGT is as follows
        # 0: Action-type (0: Presession, 1: ITI, 2: Pretrial, 3: Trial start,
        #   4: trial end)
        # 1: trigger zone on maze that causes configuration. Note: button
        # press for pretrial
        # 2: delay-period, used to delay time until trigger zone causes action.
        # primarly used for pause period during reward consumption while cue
        # stay on briefly.
        # 3-18: Barrier state 0 for down and 1 for up 3 is B1 and 4 is B2 ....
        # 19-22: Cue config index key [20:N, 21:E, 22:S, 23:W]
        # 23-27: reward config, index key [0:NE, 1:SE, 2:SW, 3:NW]
        # 28-31: light-config, index [0:UV1, 1:UV2, 2:UV3, 3:UV4]
        # 32: index in action vector list
        # PIGT: Landmark guided task
        # 0: presesion start arm
        presession_n_vec_PIGT = [0,0,0, 0,0,0,1,0,1,0,0,0,0,0,0,0,1,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        presession_e_vec_PIGT = [0,0,0, 1,0,1,0,0,0,0,0,0,0,0,0,1,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        presession_s_vec_PIGT = [0,0,0, 0,0,0,0,0,0,0,0,0,1,0,1,0,0,0,1, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        presession_w_vec_PIGT = [0,0,0, 0,0,0,0,0,0,1,0,1,0,0,0,0,0,1,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        # 1 ITI start arm
        iti_n_vec_PIGT = [1,0,0, 0,1,0,0,0,0,0,1,0,0,1,0,0,1,0,1, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        iti_e_vec_PIGT = [1,0,0, 0,0,0,0,1,0,0,1,0,0,1,0,1,0,1,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        iti_s_vec_PIGT = [1,0,0, 0,1,0,0,1,0,0,1,0,0,0,0,0,1,0,1, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        iti_w_vec_PIGT = [1,0,0, 0,1,0,0,1,0,0,0,0,0,1,0,1,0,1,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        # 2: pretrial action vectors start arm and cue orientations
        # north start arm
        pretrial_n_n_vec_PIGT = [2,12,10, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,1, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_n_e_vec_PIGT = [2,12,10, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,1, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_n_s_vec_PIGT = [2,12,10, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,1, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_n_w_vec_PIGT = [2,12,10, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,1, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        # east start arm
        pretrial_e_n_vec_PIGT = [2,15,10, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,1,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_e_e_vec_PIGT = [2,15,10, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,1,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_e_s_vec_PIGT = [2,15,10, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,1,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_e_w_vec_PIGT = [2,15,10, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,1,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        # south start arm
        pretrial_s_n_vec_PIGT = [2,10,10, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,1, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_s_e_vec_PIGT = [2,10,10, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,1, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_s_s_vec_PIGT = [2,10,10, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,1, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_s_w_vec_PIGT = [2,10,10, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,1, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        # west start arm
        pretrial_w_n_vec_PIGT = [2,7,10, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,1,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_w_e_vec_PIGT = [2,7,10, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,1,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_w_s_vec_PIGT = [2,7,10, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,1,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        pretrial_w_w_vec_PIGT = [2,7,10, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,1,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]

        # 3:trial start action vectors startarm and cue orientations
        # north start arm
        trialstart_n_n_vec_PIGT = [3,13,0, 0,0,0,1,0,1,0,0,0,1,0,1,0,0,0,1, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_n_e_vec_PIGT = [3,13,0, 0,0,0,1,0,1,0,0,0,1,0,1,0,0,0,1, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_n_s_vec_PIGT = [3,13,0, 0,0,0,1,0,1,0,0,0,1,0,1,0,0,0,1, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_n_w_vec_PIGT = [3,13,0, 0,0,0,1,0,1,0,0,0,1,0,1,0,0,0,1, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        # east start arm
        trialstart_e_n_vec_PIGT = [3,19,0, 1,0,1,0,0,0,1,0,1,0,0,0,0,0,1,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_e_e_vec_PIGT = [3,19,0, 1,0,1,0,0,0,1,0,1,0,0,0,0,0,1,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_e_s_vec_PIGT = [3,19,0, 1,0,1,0,0,0,1,0,1,0,0,0,0,0,1,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_e_w_vec_PIGT = [3,19,0, 1,0,1,0,0,0,1,0,1,0,0,0,0,0,1,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        # south start arm
        trialstart_s_n_vec_PIGT = [3,9,0, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_s_e_vec_PIGT = [3,9,0, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_s_s_vec_PIGT = [3,9,0, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_s_w_vec_PIGT = [3,9,0, 0,0,0,1,0,1,0,0,0,1,0,1,0,1,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        # west start arm
        trialstart_w_n_vec_PIGT = [3,3,0, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_w_e_vec_PIGT = [3,3,0, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_w_s_vec_PIGT = [3,3,0, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        trialstart_w_w_vec_PIGT = [3,3,0, 1,0,1,0,0,0,1,0,1,0,0,0,1,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, -1]
        # 4 trial end (reward): action vectors reward and cue orientation
        # northeast goal
        trialend_ne_n_vec_PIGT = [4,21,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0, 1,0,0,0, 0,0,0,0, -1]
        trialend_ne_e_vec_PIGT = [4,21,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0, 1,0,0,0, 0,0,0,0, -1]
        trialend_ne_s_vec_PIGT = [4,21,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0, 1,0,0,0, 0,0,0,0, -1]
        trialend_ne_w_vec_PIGT = [4,21,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0, 1,0,0,0, 0,0,0,0, -1]
        # southeast goal
        trialend_se_n_vec_PIGT = [4,17,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0, 0,1,0,0, 0,0,0,0, -1]
        trialend_se_e_vec_PIGT = [4,17,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0, 0,1,0,0, 0,0,0,0, -1]
        trialend_se_s_vec_PIGT = [4,17,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0, 0,1,0,0, 0,0,0,0, -1]
        trialend_se_w_vec_PIGT = [4,17,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0, 0,1,0,0, 0,0,0,0, -1]
        # southwest goal
        trialend_sw_n_vec_PIGT = [4,1,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0, 0,0,1,0, 0,0,0,0, -1]
        trialend_sw_e_vec_PIGT = [4,1,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0, 0,0,1,0, 0,0,0,0, -1]
        trialend_sw_s_vec_PIGT = [4,1,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0, 0,0,1,0, 0,0,0,0, -1]
        trialend_sw_w_vec_PIGT = [4,1,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0, 0,0,1,0, 0,0,0,0, -1]
        # northwest goal
        trialend_nw_n_vec_PIGT = [4,5,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0, 0,0,0,1, 0,0,0,0, -1]
        trialend_nw_e_vec_PIGT = [4,5,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0, 0,0,0,1, 0,0,0,0, -1]
        trialend_nw_s_vec_PIGT = [4,5,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0, 0,0,0,1, 0,0,0,0, -1]
        trialend_nw_w_vec_PIGT = [4,5,1, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0, 0,0,0,1, 0,0,0,0, -1]

        # action states matrix PIGT
        # matrix of predefined action vectors
        self.action_states_matrix_PIGT = [
            [presession_n_vec_PIGT, presession_e_vec_PIGT, presession_s_vec_PIGT, presession_w_vec_PIGT],
            [iti_n_vec_PIGT, iti_e_vec_PIGT, iti_s_vec_PIGT, iti_w_vec_PIGT],
            [[pretrial_n_n_vec_PIGT, pretrial_n_e_vec_PIGT, pretrial_n_s_vec_PIGT, pretrial_n_w_vec_PIGT],
             [pretrial_e_n_vec_PIGT, pretrial_e_e_vec_PIGT, pretrial_e_s_vec_PIGT, pretrial_e_w_vec_PIGT],
             [pretrial_s_n_vec_PIGT, pretrial_s_e_vec_PIGT, pretrial_s_s_vec_PIGT, pretrial_s_w_vec_PIGT],
             [pretrial_w_n_vec_PIGT, pretrial_w_e_vec_PIGT, pretrial_w_s_vec_PIGT, pretrial_w_w_vec_PIGT]
             ],
            [[trialstart_n_n_vec_PIGT, trialstart_n_e_vec_PIGT, trialstart_n_s_vec_PIGT, trialstart_n_w_vec_PIGT],
             [trialstart_e_n_vec_PIGT, trialstart_e_e_vec_PIGT, trialstart_e_s_vec_PIGT, trialstart_e_w_vec_PIGT],
             [trialstart_s_n_vec_PIGT, trialstart_s_e_vec_PIGT, trialstart_s_s_vec_PIGT, trialstart_s_w_vec_PIGT],
             [trialstart_w_n_vec_PIGT, trialstart_w_e_vec_PIGT, trialstart_w_s_vec_PIGT, trialstart_w_w_vec_PIGT]
             ],
            [[trialend_ne_n_vec_PIGT, trialend_ne_e_vec_PIGT, trialend_ne_s_vec_PIGT, trialend_ne_w_vec_PIGT],
             [trialend_se_n_vec_PIGT, trialend_se_e_vec_PIGT, trialend_se_s_vec_PIGT, trialend_se_w_vec_PIGT],
             [trialend_sw_n_vec_PIGT, trialend_sw_e_vec_PIGT, trialend_sw_s_vec_PIGT, trialend_sw_w_vec_PIGT],
             [trialend_nw_n_vec_PIGT, trialend_nw_e_vec_PIGT, trialend_nw_s_vec_PIGT, trialend_nw_w_vec_PIGT]
             ]
        ]

        self.action_vector_idx = [0]
        self.zone = [0]
        # action vector holds trigger of event for different states and
        # binary values and base-10 values which serve as function inputs
        # that configure the maze state, this vector is created when the
        # session stats and is dependent on rat set cue-reward config and
        # session history.
        self.action_vector_list = []

        # readable list of action vector pairs for table view. These are set
        # for use in table prior to data being generated
        self.action_vector_list_readable_header = ['IDX', 'type', 'zone', 'delay', 'start', 'goal', 'cue',
                                                   'reward', 'light cue', '']
        self.action_vector_list_readable = [['', '', '', '', '', '', '', '', '', ''] for i in range(64)]

        # self.action_vector_list_readable = [['','','','','','']]
        # session_general_info hold general session information rat, session no, etc
        # index order: subject_name, subject_id, session_number, date, time, behavior, cue_conf, session_type, seed,
        #              start_goal_pairs, cue_goal_index, cue_index, action_vector_list,
        #              readable_action_vector_list
        self.session_general_info = {}

        # Session lists
        # session_start_goal_pairs is stores a shuffled list of 16 start arm
        # goal pairs. This determins order sequence of action vector.
        self.session_start_goal_pairs = []

        # stores action vector which holds the trigger event and list
        # of values that determine how the maze should configure itself
        # also stores readable description and metadata for the action-
        # vector
        self.session_event_history_LGT_header = ['act id', 'act type', 'frame', 'time',
                                                 'duration', 'zone', 'x-pos', 'y-pos', 'goal', 'cue']
        self.session_event_history_LGT = [[], [], [], [], [], [], [], [], [], []]
        # Captures data from video stream to pass to session control
        self.session_event_stream_LGT = [0, 0, 0, 0, 0]
        self.video_coordinate_stream = [0, 0, 0]

        self.trial_history_LGT_header = ['subject', 'frame', 'start time', 'end time',
                                         'total time', 'start zone', 'reward zone']
        self.trial_history_LGT = [[], [], [], [], [], [], []]

        self.session_start_time_offset = 0

    def setup_main_Window(self):
        self.setWindowTitle('Maze Control: Main Window')

        # QLabel to display video
        self.label_video_display = QLabel()
        self.label_video_display.setObjectName('Behavior Room: Raspi Cam')

        # Create Layout
        video_display_box = QVBoxLayout()
        video_display_box.addWidget(self.label_video_display, 1, alignment=Qt.AlignTop)
        video_display_frame = QFrame()
        video_display_frame.setMinimumSize(700, 900)
        video_display_frame.setLayout(video_display_box)

        device_control_box = QVBoxLayout()
        device_control_box.addWidget(self.device_control_UI())
        device_control_box.setSpacing(0)
        device_control_box.setContentsMargins(0, 0, 0, 0)
        device_control_frame = QFrame()
        device_control_frame.setMinimumSize(530, 900)
        device_control_frame.setLayout(device_control_box)

        tab_box = QTabWidget()
        tab_box.addTab(self.session_control_tab_UI(), 'Session Control')
        tab_box.addTab(self.subjects_tab_UI(), 'Subjects')
        tab_box.setMinimumSize(600, 900)

        main_h_box = QHBoxLayout()
        main_h_box.addWidget(video_display_frame)
        main_h_box.addWidget(device_control_frame)
        main_h_box.addWidget(tab_box)
        container = QWidget()
        container.setLayout(main_h_box)
        self.setCentralWidget(container)

    # noinspection PyArgumentList
    def device_control_UI(self):
        # WIDGETS
        button_sz = 50
        # syringe pump buttons
        button_reward_list = []
        button_reward_label = ['R1', 'R4', 'R3', 'R2']
        for i in range(4):
            button_reward_list.append(QPushButton(button_reward_label[i]))
            button_reward_list[i].setFixedSize(button_sz, button_sz)
            button_reward_list[i].setStyleSheet('background-color: Lightgreen')
            button_reward_list[i].clicked.connect(lambda state, var=i: self.control_syringe_pump(var))

        # Barrier buttons
        self.button_barrier_list = []
        for i in range(16):
            self.button_barrier_list.append(QPushButton(f'A{i + 1}\nDWN'))
            self.button_barrier_list[i].setFixedSize(button_sz, button_sz)
            self.button_barrier_list[i].setStyleSheet('background-color: khaki')
            self.button_barrier_list[i].clicked.connect(lambda state, var=i: self.control_actuator(var))

        # UV Light buttons
        self.button_cue_light_list = []
        for i in range(4):
            self.button_cue_light_list.append(QPushButton(f'UV{i + 1}\nOFF'))
            self.button_cue_light_list[i].setFixedSize(button_sz, button_sz)
            self.button_cue_light_list[i].setStyleSheet('background-color: Thistle')
            self.button_cue_light_list[i].clicked.connect(lambda state, var=i: self.control_cue_light(var))

        # Cue Display
        cue_label = ['N', 'E', 'S', 'W']
        self.button_cue_list = []
        for i in range(4):
            self.button_cue_list.append(QPushButton(f'{cue_label[i]} CUE\nOFF'))
            self.button_cue_list[i].setFixedSize(button_sz, button_sz)
            self.button_cue_list[i].setStyleSheet('background-color: Azure')
            self.button_cue_list[i].clicked.connect(lambda state, var=i: self.control_cue(var))

        # Video control labels, buttons and fields
        label_video = QLabel('Video Control: ')
        self.button_open_video = QPushButton('Open Video')
        self.button_open_video.clicked.connect(self.thread_run_video)
        self.button_close_video = QPushButton('Close Video')
        self.button_close_video.setEnabled(False)
        self.button_close_video.clicked.connect(self.thread_close_video)
        self.label_state_video = QLabel('Idle')
        label_host = QLabel('HOST')
        self.line_edit_host = QLineEdit()
        self.line_edit_host.setText('54321')
        label_fps = QLabel('fps:')
        self.line_edit_fps = QLineEdit()
        self.line_edit_fps.setText('30')
        label_shutter_speed = QLabel('SS:')
        self.line_edit_shutter_speed = QLineEdit()
        self.line_edit_shutter_speed.setText('4000')
        label_iso = QLabel('ISO:')
        self.line_edit_iso = QLineEdit()
        self.line_edit_iso.setText('4000')
        label_varThreshold = QLabel('Var')
        self.line_edit_varThreshold = QLineEdit()
        self.line_edit_varThreshold.setText('1000')
        # Cue display connection labels
        label_display_connection = QLabel()
        label_display_connection.setText('Cue Display')
        # Cue display Connection Buttons
        self.button_signal_on_display = QPushButton('On')
        self.button_signal_on_display.clicked.connect(self.control_display_power_on)
        self.button_signal_off_display = QPushButton('Off')
        self.button_signal_off_display.clicked.connect(self.control_display_power_off)
        self.button_connect_display = QPushButton('CONNECT DISPLAYS')
        self.button_connect_display.clicked.connect(self.control_connect_display)
        self.button_disconnect_display = QPushButton('DISCONNECT DISPLAYS')
        self.button_disconnect_display.clicked.connect(self.control_disconnect_display)
        self.button_disconnect_display.setEnabled(False)
        # light connection labels
        label_room_lights = QLabel()
        label_room_lights.setText('Room Lights')
        self.line_edit_lights = QLineEdit()
        self.line_edit_lights.setText('255')
        # Overhead Light Buttons
        self.button_room_lights_ON = QPushButton('LIGHTS ON')
        self.button_room_lights_ON.clicked.connect(self.control_room_lights_bright_on)
        self.button_room_lights_OFF = QPushButton('LIGHTS OFF')
        self.button_room_lights_OFF.clicked.connect(self.control_room_lights_bright_off)
        self.button_room_lights_OFF.setEnabled(False)
        self.button_dim_lights_ON = QPushButton('DIM ON')
        self.button_dim_lights_ON.clicked.connect(self.control_room_lights_dim_on)
        self.button_dim_lights_OFF = QPushButton('DIM OFF')
        self.button_dim_lights_OFF.clicked.connect(self.control_room_lights_dim_off)
        self.button_dim_lights_OFF.setEnabled(False)
        #IR Lights
        label_IR_lights = QLabel()
        label_IR_lights.setText('IR Lights')
        self.line_edit_IR_lights = QLineEdit()
        self.line_edit_IR_lights.setText('255')
        self.button_IR_lights_ON = QPushButton('IR ON')
        self.button_IR_lights_ON.clicked.connect(self.control_IR_lights_on)
        self.button_IR_lights_OFF = QPushButton('IR OFF')
        self.button_IR_lights_OFF.clicked.connect(self.control_IR_lights_off)
        self.button_IR_lights_OFF.setEnabled(False)

        # Syringe Pump Table Widget label
        label_syringe_pump_table = QLabel()
        label_syringe_pump_table.setText('Syringe Pump Parameters')
        label_reward_volume = QLabel()
        label_reward_volume.setText('Reward Vol (uL):')
        self.list_reward_volume = ['50', '100', '150', '200', '250', '300']
        combo_box_reward_volume = QComboBox()
        combo_box_reward_volume.addItems(self.list_reward_volume)
        self.line_edit_reward_volume = QLineEdit()
        combo_box_reward_volume.setLineEdit(self.line_edit_reward_volume)
        self.line_edit_reward_volume.setText('100')
        self.line_edit_reward_volume.textChanged.connect(self.update_syringe_pump_table)
        # Actuator Table label
        label_actuator_table = QLabel()
        label_actuator_table.setText('Actuator Parameters')
        # simultaneous barrier control
        self.button_all_barriers_up = QPushButton('All Barriers UP')
        self.button_all_barriers_up.clicked.connect(lambda: self.all_barriers('up'))
        self.button_all_barriers_down = QPushButton('All Barriers DOWN')
        self.button_all_barriers_down.clicked.connect(lambda: self.all_barriers('down'))
        # Play Sound
        self.button_play_sound = QPushButton('Play Sound')
        self.button_play_sound.clicked.connect(self.button_mp_play_sound)
        self.line_edit_sound = QLineEdit()
        self.line_edit_sound.setText('1')

        # LAYOUT
        button_grid = QGridLayout()
        # first row
        button_grid.addWidget(button_reward_list[3], 0, 0)
        button_grid.addWidget(self.button_barrier_list[5], 0, 3)
        button_grid.addWidget(self.button_cue_light_list[1], 0, 4)
        button_grid.addWidget(self.button_barrier_list[3], 0, 5)
        button_grid.addWidget(button_reward_list[0], 0, 8)
        # second row
        button_grid.addWidget(self.button_barrier_list[4], 1, 4)
        # third row
        button_grid.addWidget(self.button_cue_list[0], 2, 4)
        # fourth row
        button_grid.addWidget(self.button_barrier_list[6], 3, 0)
        button_grid.addWidget(self.button_barrier_list[13], 3, 4)
        button_grid.addWidget(self.button_barrier_list[2], 3, 8)
        # fifth row
        button_grid.addWidget(self.button_cue_light_list[2], 4, 0)
        button_grid.addWidget(self.button_barrier_list[7], 4, 1)
        button_grid.addWidget(self.button_cue_list[3], 4, 2)
        button_grid.addWidget(self.button_barrier_list[14], 4, 3)
        button_grid.addWidget(self.button_barrier_list[12], 4, 5)
        button_grid.addWidget(self.button_cue_list[1], 4, 6)
        button_grid.addWidget(self.button_barrier_list[1], 4, 7)
        button_grid.addWidget(self.button_cue_light_list[0], 4, 8)
        # sixth row
        button_grid.addWidget(self.button_barrier_list[8], 5, 0)
        button_grid.addWidget(self.button_barrier_list[15], 5, 4)
        button_grid.addWidget(self.button_barrier_list[0], 5, 8)
        # seventh row
        button_grid.addWidget(self.button_cue_list[2], 6, 4)
        # eigth row
        button_grid.addWidget(self.button_barrier_list[10], 7, 4)
        # ninth row
        button_grid.addWidget(button_reward_list[2], 8, 0)
        button_grid.addWidget(self.button_barrier_list[9], 8, 3)
        button_grid.addWidget(self.button_cue_light_list[3], 8, 4)
        button_grid.addWidget(self.button_barrier_list[11], 8, 5)
        button_grid.addWidget(button_reward_list[1], 8, 8)
        button_grid_frame = QFrame()
        button_grid_frame.setFixedSize(500, 500)
        button_grid_frame.setStyleSheet('QFrame{border: 1px solid rgb(150,150,150);}')
        button_grid_frame.setLayout(button_grid)

        lower_left_grid = QGridLayout()
        lower_left_grid.addWidget(label_video, 0, 0, 1, 6)
        lower_left_grid.addWidget(self.label_state_video, 0, 6, 1, 8)

        lower_left_grid.addWidget(self.button_open_video, 1, 0, 1, 16)

        lower_left_grid.addWidget(self.button_close_video, 2, 0, 1, 16)

        lower_left_grid.addWidget(label_host, 3, 0, 1, 3)
        lower_left_grid.addWidget(self.line_edit_host, 3, 3, 1, 4)
        lower_left_grid.addWidget(label_varThreshold, 3, 7, 1, 2)
        lower_left_grid.addWidget(self.line_edit_varThreshold, 3, 9, 1, 4)

        lower_left_grid.addWidget(label_fps, 4, 0, 1, 2)
        lower_left_grid.addWidget(self.line_edit_fps, 4, 2, 1, 2)
        lower_left_grid.addWidget(label_shutter_speed, 4, 4, 1, 2)
        lower_left_grid.addWidget(self.line_edit_shutter_speed, 4, 6, 1, 3)
        lower_left_grid.addWidget(label_iso, 4, 9, 1, 2)
        lower_left_grid.addWidget(self.line_edit_iso, 4, 11, 1, 5)

        lower_left_grid.addWidget(label_display_connection, 5, 0, 1, 5)
        lower_left_grid.addWidget(self.button_signal_on_display, 5, 5, 1, 3)
        lower_left_grid.addWidget(self.button_signal_off_display, 5, 8, 1, 3)

        lower_left_grid.addWidget(self.button_connect_display, 6, 0, 1, 16)

        lower_left_grid.addWidget(self.button_disconnect_display, 7, 0, 1, 16)

        lower_left_grid.addWidget(label_room_lights, 8, 0, 1, 8)
        lower_left_grid.addWidget(self.line_edit_lights, 8, 8, 1, 8)

        lower_left_grid.addWidget(self.button_room_lights_ON, 9, 0, 1, 8)
        lower_left_grid.addWidget(self.button_dim_lights_ON, 9, 8, 1, 8)

        lower_left_grid.addWidget(self.button_room_lights_OFF, 10, 0, 1, 8)
        lower_left_grid.addWidget(self.button_dim_lights_OFF, 10, 8, 1, 8)

        lower_left_grid.addWidget(label_IR_lights, 11, 0, 1, 4)
        lower_left_grid.addWidget(self.line_edit_IR_lights, 11, 4, 1, 12)

        lower_left_grid.addWidget(self.button_IR_lights_ON, 12, 0, 1, 8)
        lower_left_grid.addWidget(self.button_IR_lights_OFF, 12, 8, 1, 8)

        lower_left_grid.addWidget(self.button_all_barriers_up, 13, 0, 1, 16)

        lower_left_grid.addWidget(self.button_all_barriers_down, 14, 0, 1, 16)

        lower_left_grid.addWidget(self.button_play_sound, 15, 0, 1, 8)
        lower_left_grid.addWidget(self.line_edit_sound, 15, 8, 1, 8)

        lower_left_grid_frame = QFrame()
        lower_left_grid_frame.setFixedWidth(220)
        lower_left_grid_frame.setStyleSheet('QFrame{margin:0px;}')
        lower_left_grid_frame.setLayout(lower_left_grid)

        actuator_table = QTableView(
            selectionMode=QTableView.SingleSelection,
            selectionBehavior=QTableView.SelectRows,
        )
        actuator_table_header = ['No.', 'Up Time', 'Down Time']
        actuator_table_model = TableEditModel(actuator_table_header, self.actuator_parameters)
        actuator_table.setModel(actuator_table_model)
        actuator_table.setSelectionBehavior(actuator_table.SelectRows)
        actuator_table.resizeRowsToContents()
        actuator_table.setColumnWidth(0, 40)

        self.syringe_pump_table = QTableView(
            selectionMode=QTableView.SingleSelection,
            selectionBehavior=QTableView.SelectRows,
        )
        self.syringe_pump_table.setMaximumHeight(130)
        self.syringe_pump_table_header = ['No.', 'Fwd', 'Bkwd', 'Spd', 'Acl']
        self.syringe_pump_table_model = TableEditModel(self.syringe_pump_table_header, self.syringe_pump_parameters)
        self.syringe_pump_table.setModel(self.syringe_pump_table_model)
        self.syringe_pump_table.setSelectionBehavior(self.syringe_pump_table.SelectRows)
        self.syringe_pump_table.resizeRowsToContents()
        self.syringe_pump_table.setColumnWidth(0, 41)
        self.syringe_pump_table.setColumnWidth(1, 54)
        self.syringe_pump_table.setColumnWidth(2, 54)
        self.syringe_pump_table.setColumnWidth(3, 54)
        self.syringe_pump_table.setColumnWidth(4, 54)

        lower_right_grid = QGridLayout()
        lower_right_grid.addWidget(label_actuator_table, 0, 0, 1, 8)
        lower_right_grid.addWidget(actuator_table, 1, 0, 8, 8)
        lower_right_grid.addWidget(label_syringe_pump_table, 9, 0, 1, 4)
        lower_right_grid.addWidget(label_reward_volume, 10, 0, 1, 3)
        lower_right_grid.addWidget(combo_box_reward_volume, 10, 3, 1, 2)
        lower_right_grid.addWidget(self.syringe_pump_table, 11, 0, 1, 8)
        lower_right_grid_frame = QFrame()
        lower_right_grid_frame.setFixedWidth(280)
        lower_right_grid_frame.setStyleSheet('QFrame{margin:0px;}')
        lower_right_grid_frame.setLayout(lower_right_grid)

        # lower_right_v_box = QVBoxLayout()
        # lower_right_v_box.addWidget(label_actuator_table)
        # lower_right_v_box.addWidget(actuator_table)
        # lower_right_v_box.addWidget(label_syringe_pump_table)
        # lower_right_v_box.addWidget(syringe_pump_table)
        # lower_right_v_frame = QFrame()
        # lower_right_v_frame.setFixedWidth(280)
        # lower_right_v_frame.setLayout(lower_right_v_box)

        table_h_box = QHBoxLayout()
        table_h_box.setAlignment(Qt.AlignCenter)
        table_h_box.addWidget(lower_left_grid_frame, alignment=Qt.AlignTop | Qt.AlignLeft)
        table_h_box.addWidget(lower_right_grid_frame, alignment=Qt.AlignTop | Qt.AlignLeft)
        table_h_frame = QFrame()
        table_h_frame.setMinimumSize(510, 300)
        # table_h_frame.setStyleSheet('QFrame{border: 1px solid rgb(0,0,0);}')
        table_h_frame.setLayout(table_h_box)

        v_box = QVBoxLayout()
        # v_box.setAlignment(Qt.AlignCenter)
        v_box.addWidget(button_grid_frame, alignment=Qt.AlignCenter)
        v_box.addWidget(table_h_frame)

        device_control = QWidget()
        device_control.setLayout(v_box)
        return device_control

    def update_syringe_pump_table(self):
        reward_volume = self.line_edit_reward_volume.text()
        if reward_volume == '50':
            self.syringe_pump_parameters = self.syringe_pump_parameters_list[0]
        elif reward_volume == '100':
            self.syringe_pump_parameters = self.syringe_pump_parameters_list[1]
        elif reward_volume == '150':
            self.syringe_pump_parameters = self.syringe_pump_parameters_list[2]
        elif reward_volume == '200':
            self.syringe_pump_parameters = self.syringe_pump_parameters_list[3]
        elif reward_volume == '250':
            self.syringe_pump_parameters = self.syringe_pump_parameters_list[4]
        elif reward_volume == '300':
            self.syringe_pump_parameters = self.syringe_pump_parameters_list[5]

        self.syringe_pump_table_header = ['No.', 'Fwd', 'Bkwd', 'Spd', 'Acl']
        self.syringe_pump_table_model = TableEditModel(self.syringe_pump_table_header, self.syringe_pump_parameters)
        self.syringe_pump_table.setModel(self.syringe_pump_table_model)

    def all_barriers(self, direction):
        dur = 0
        idx = [i for i in range(16)]
        #random.shuffle(idx)
        if direction == 'up':
            for i in idx:
                if self.state_barrier_list[i] == 0:
                    self.control_actuator(i)
                    time.sleep(dur)
        elif direction == 'down':
            for i in idx:
                if self.state_barrier_list[i] == 1:
                    self.control_actuator(i)
                    time.sleep(dur)
        else:
            pass

    def session_control_tab_UI(self):
        label_subject_info = QLabel('Subject Info')
        label_subject_info.setFont(QFont('Ariel', 12))
        label_subject_id = QLabel('ID:')
        label_subject_id.setAlignment(Qt.AlignRight | Qt.AlignCenter)
        label_subject_id.setFont(QFont('Sans Serif', weight=QFont.Medium))
        self.label_subject_id_data = QLabel('')
        self.label_subject_id_data.setFont(QFont('Sans Serif', weight=QFont.Normal))
        label_subject_name = QLabel('Subject:')
        label_subject_name.setAlignment(Qt.AlignRight | Qt.AlignCenter)
        label_subject_name.setFont(QFont('Sans Serif', weight=QFont.Medium))
        self.label_subject_name_data = QLabel('')
        self.label_subject_name_data.setFont(QFont('Sans Serif', weight=QFont.Normal))
        label_sex = QLabel('Sex:')
        label_sex.setAlignment(Qt.AlignRight | Qt.AlignCenter)
        label_sex.setFont(QFont('Sans Serif', weight=QFont.Medium))
        self.label_sex_data = QLabel('')
        self.label_sex_data.setFont(QFont('Sans Serif', weight=QFont.Normal))

        label_last_session = QLabel('Last Sess:')
        label_last_session.setAlignment(Qt.AlignRight | Qt.AlignCenter)
        label_last_session.setFont(QFont('Sans Serif', weight=QFont.Medium))
        self.label_last_session_data = QLabel('')
        self.label_last_session_data.setFont(QFont('Sans Serif', weight=QFont.Normal))

        label_delay = QLabel('Delay:')
        label_delay.setAlignment(Qt.AlignRight | Qt.AlignCenter)
        label_delay.setFont(QFont('Sans Serif', weight=QFont.Medium))
        self.label_delay_data = QLabel('')
        self.label_delay_data.setFont(QFont('Sans Serif', weight=QFont.Normal))

        label_behavior = QLabel('Behavior:')
        label_behavior.setAlignment(Qt.AlignLeft | Qt.AlignCenter)
        label_behavior.setFont(QFont('Sans Serif', weight=QFont.Medium))
        self.label_behavior_data = QLabel('')
        self.label_behavior_data.setFont(QFont('Sans Serif', weight=QFont.Normal))
        label_cue_conf = QLabel('Cue Conf:')
        label_cue_conf.setAlignment(Qt.AlignRight | Qt.AlignCenter)
        label_cue_conf.setFont(QFont('Sans Serif', weight=QFont.Medium))
        self.label_cue_conf_data = QLabel('')
        self.label_cue_conf_data.setFont(QFont('Sans Serif', weight=QFont.Normal))
        label_session_type = QLabel('Sess Type:')
        label_session_type.setAlignment(Qt.AlignRight | Qt.AlignCenter)
        label_session_type.setFont(QFont('Sans Serif', weight=QFont.Medium))
        self.label_session_type_data = QLabel('')
        self.label_session_type_data.setFont(QFont('Sans Serif', weight=QFont.Normal))

        label_session = QLabel('Session General Info')
        label_session.setFont(QFont('Ariel', 12))

        label_session_number = QLabel('Sess No:')
        label_session_number.setAlignment(Qt.AlignLeft | Qt.AlignCenter)
        label_session_number.setFont(QFont('Sans Serif', weight=QFont.Medium))
        self.label_session_number_data = QLabel('')
        self.label_session_number_data.setFont(QFont('Sans Serif', weight=QFont.Normal))
        label_session_date = QLabel('Date:')
        label_session_date.setAlignment(Qt.AlignRight | Qt.AlignCenter)
        label_session_date.setFont(QFont('Sans Serif', weight=QFont.Medium))
        self.label_session_date_data = QLabel('')
        self.label_session_date_data.setFont(QFont('Sans Serif', weight=QFont.Normal))
        label_session_time = QLabel('Time:')
        label_session_time.setAlignment(Qt.AlignRight | Qt.AlignCenter)
        label_session_time.setFont(QFont('Sans Serif', weight=QFont.Medium))
        self.label_session_time_data = QLabel('')
        self.label_session_time_data.setFont(QFont('Sans Serif', weight=QFont.Normal))
        label_session_seed = QLabel('Seed:')
        label_session_seed.setAlignment(Qt.AlignRight | Qt.AlignCenter)
        label_session_seed.setFont(QFont('Sans Serif', weight=QFont.Medium))
        self.label_session_seed_data = QLabel('')
        self.label_session_seed_data.setFont(QFont('Sans Serif', weight=QFont.Normal))
        label_session_behavior = QLabel('Behavior:')
        label_session_behavior.setAlignment(Qt.AlignLeft | Qt.AlignCenter)
        label_session_behavior.setFont(QFont('Sans Serif', weight=QFont.Medium))
        self.label_session_behavior_data = QLabel('')
        self.label_session_behavior_data.setFont(QFont('Sans Serif', weight=QFont.Normal))
        label_session_cue_conf = QLabel('Cue Conf:')
        label_session_cue_conf.setAlignment(Qt.AlignRight | Qt.AlignCenter)
        label_session_cue_conf.setFont(QFont('Sans Serif', weight=QFont.Medium))
        self.label_session_cue_conf_data = QLabel('')
        self.label_session_cue_conf_data.setFont(QFont('Sans Serif', weight=QFont.Normal))
        label_session_session_type = QLabel('Cue Ret:')
        label_session_session_type.setAlignment(Qt.AlignRight | Qt.AlignCenter)
        label_session_session_type.setFont(QFont('Sans Serif', weight=QFont.Medium))
        self.label_session_type = QLabel('')
        self.label_session_type.setFont(QFont('Sans Serif', weight=QFont.Normal))

        # Table to display vector in readable form
        label_action_vector_table = QLabel('Action Vector Table')
        label_action_vector_table.setFont(QFont('Ariel', 11))

        # Initialize data and create action vector list button
        self.button_initialize_session_data = QPushButton('Reinitialize Data')
        self.button_initialize_session_data.clicked.connect(self.init_session_data)

        # noinspection PyArgumentList
        self.action_vec_table = QTableView(
            selectionMode=QTableView.SingleSelection,
            selectionBehavior=QTableView.SelectRows,
        )
        self.action_vec_table_model = TableStaticModel(
            self.action_vector_list_readable_header,
            self.action_vector_list_readable
        )
        self.action_vec_table.setModel(self.action_vec_table_model)
        self.action_vec_table.selectionModel().selectionChanged.connect(self.get_action_vector_idx)
        self.action_vec_table.horizontalHeader().setStretchLastSection(True)
        self.action_vec_table.verticalHeader().hide()
        self.action_vec_table.horizontalHeader().setFont(QFont('Sans Serif', 10))
        self.action_vec_table.resizeRowsToContents()
        self.action_vec_table.setColumnWidth(0, 30)
        self.action_vec_table.setColumnWidth(1, 90)
        self.action_vec_table.setColumnWidth(2, 50)
        self.action_vec_table.setColumnWidth(3, 50)
        self.action_vec_table.setColumnWidth(4, 60)
        self.action_vec_table.setColumnWidth(5, 90)
        self.action_vec_table.setColumnWidth(6, 70)
        self.action_vec_table.setColumnWidth(7, 70)
        self.action_vec_table.setColumnWidth(8, 40)
        self.action_vec_table.setColumnHidden(9, True)
        # Label to display action vector program language
        # Data for label
        self.label_action_vector_contents = QLabel('Action Vec: []')
        self.button_test_action_vector = QPushButton('Test Action Vector')
        self.button_test_action_vector.clicked.connect(self.test_action_vector_thd)
        self.button_test_action_vector.setEnabled(False)
        # Stream control buttons and labels for session
        self.button_pause_session = QPushButton('Pause Session')
        self.button_pause_session.clicked.connect(self.pause_session_dialog)
        self.button_pause_session.setEnabled(False)
        # self.button_advance_action = QPushButton('Advance Action')
        # self.button_advance_action.clicked.connect(self.advance_action_vector)
        # self.button_advance_action.setEnabled(False)
        self.button_open_stream_session = QPushButton('Start Session')
        self.button_open_stream_session.clicked.connect(lambda: self.thread_run_session(False))
        self.button_open_stream_session.setEnabled(False)
        self.button_close_stream_session = QPushButton('End Session')
        self.button_close_stream_session.setEnabled(False)
        self.button_close_stream_session.clicked.connect(self.thread_close_session)
        self.label_stream_session = QLabel(
            """Session: Idle | Step: None | Time: None | Pixel Cordinates: (None, None) | Zone: None""")
        self.label_current_action = QLabel('Curr Act: []')

        # Session Tracking Widgets
        label_video_tracking_info = QLabel('Video Tracking Info')
        label_video_tracking_info.setFont(QFont('Ariel', 12))
        label_session_tracking_info = QLabel('Session Tracking Info')
        label_session_tracking_info.setFont(QFont('Ariel', 12))

        # Session Trial Widgets
        label_session_trial_info = QLabel('Session Trial Info')
        label_session_trial_info.setFont(QFont('Ariel', 12))
        self.label_trial_info = QLabel('Session Info\n\nTrial Info')

        # Form data top of layout
        data_session_grid = QGridLayout()
        # Row 0
        data_session_grid.addWidget(label_subject_info, 0, 0, 1, 100)
        # Row 1
        data_session_grid.addWidget(label_subject_id, 1, 0, 1, 4)
        data_session_grid.addWidget(self.label_subject_id_data, 1, 4, 1, 4)
        data_session_grid.addWidget(label_subject_name, 1, 8, 1, 10)
        data_session_grid.addWidget(self.label_subject_name_data, 1, 18, 1, 11)
        data_session_grid.addWidget(label_sex, 1, 29, 1, 6)
        data_session_grid.addWidget(self.label_sex_data, 1, 35, 1, 10)
        data_session_grid.addWidget(label_last_session, 1, 45, 1, 12)
        data_session_grid.addWidget(self.label_last_session_data, 1, 57, 1, 13)
        data_session_grid.addWidget(label_delay, 1, 70, 1, 10)
        data_session_grid.addWidget(self.label_delay_data, 1, 80, 1, 20)
        # Row 2
        data_session_grid.addWidget(label_behavior, 2, 0, 1, 10)
        data_session_grid.addWidget(self.label_behavior_data, 2, 10, 1, 30)
        data_session_grid.addWidget(label_cue_conf, 2, 40, 1, 12)
        data_session_grid.addWidget(self.label_cue_conf_data, 2, 52, 1, 10)
        data_session_grid.addWidget(label_session_type, 2, 62, 1, 10)
        data_session_grid.addWidget(self.label_session_type_data, 2, 72, 1, 28)
        # Row 3
        H_line_light = QHLine()
        H_line_light.setFrameShadow(QFrame.Sunken)
        data_session_grid.addWidget(H_line_light, 3, 0, 1, 100)
        # Row 4
        data_session_grid.addWidget(label_session, 4, 0, 1, 80)
        data_session_grid.addWidget(self.button_initialize_session_data, 4, 70, 1, 30)
        # Row 5
        data_session_grid.addWidget(label_session_number, 5, 0, 1, 10)
        data_session_grid.addWidget(self.label_session_number_data, 5, 10, 1, 7)
        data_session_grid.addWidget(label_session_date, 5, 17, 1, 5)
        data_session_grid.addWidget(self.label_session_date_data, 5, 22, 1, 10)
        data_session_grid.addWidget(label_session_time, 5, 32, 1, 5)
        data_session_grid.addWidget(self.label_session_time_data, 5, 37, 1, 10)
        data_session_grid.addWidget(label_session_seed, 5, 47, 1, 10)
        data_session_grid.addWidget(self.label_session_seed_data, 5, 57, 1, 43)
        # Row 6
        data_session_grid.addWidget(label_session_behavior, 6, 0, 1, 10)
        data_session_grid.addWidget(self.label_session_behavior_data, 6, 10, 1, 35)
        data_session_grid.addWidget(label_session_cue_conf, 6, 45, 1, 10)
        data_session_grid.addWidget(self.label_session_cue_conf_data, 6, 55, 1, 10)
        data_session_grid.addWidget(label_session_session_type, 6, 65, 1, 15)
        data_session_grid.addWidget(self.label_session_type, 6, 80, 1, 20)
        # Row 7
        H_line_light = QHLine()
        H_line_light.setFrameShadow(QFrame.Sunken)
        data_session_grid.addWidget(H_line_light, 7, 0, 1, 100)
        # Row 8
        data_session_grid.addWidget(label_action_vector_table, 8, 0, 1, 30)
        data_session_grid.addWidget(self.button_test_action_vector, 8, 65, 1, 35)
        # Row 9-12
        data_session_grid.addWidget(self.action_vec_table, 9, 0, 4, 100)
        # Row 13
        data_session_grid.addWidget(self.label_action_vector_contents, 13, 0, 1, 100)
        # Row 14
        H_line_light = QHLine()
        H_line_light.setFrameShadow(QFrame.Sunken)
        data_session_grid.addWidget(H_line_light, 3, 0, 1, 100)
        # Row 15
        data_session_grid.addWidget(self.button_pause_session, 15, 0, 1, 15)
        #data_session_grid.addWidget
        data_session_grid.addWidget(self.button_open_stream_session, 15, 70, 1, 15)
        data_session_grid.addWidget(self.button_close_stream_session, 15, 85, 1, 15)
        # Row 16
        data_session_grid.addWidget(label_video_tracking_info, 16, 0, 1, 40)
        # Row 17
        data_session_grid.addWidget(self.label_stream_session, 17, 0, 1, 100)
        # Row 18
        data_session_grid.addWidget(self.label_current_action, 18, 0, 1, 100)
        # Row 19
        H_line_dark = QHLine()
        H_line_dark.setLineWidth(1)
        data_session_grid.addWidget(H_line_dark, 19, 0, 1, 100)
        # Row 20
        data_session_grid.addWidget(label_session_trial_info, 20, 0, 1, 100)
        # Row 21
        data_session_grid.addWidget(self.label_trial_info, 21, 0, 1, 100)

        data_session_frame = QFrame()
        # data_session_frame.setMaximumSize(600,200)
        data_session_frame.setLayout(data_session_grid)

        tab_V_box = QVBoxLayout()
        tab_V_box.setSpacing(0)
        tab_V_box.setContentsMargins(0, 0, 0, 0)
        tab_V_box.setAlignment(Qt.AlignTop)
        tab_V_box.addWidget(data_session_frame)

        session_control_tab = QWidget()
        session_control_tab.setLayout(tab_V_box)
        # Make the things that does the stuff
        return session_control_tab

    def subjects_tab_UI(self):
        label_subjects_tab = QLabel('Subjects Manager')
        label_subjects_tab.setFont(QFont('Ariel', 12))

        # Create Subjects Table object
        self.subjects_model = SubjectsModel()
        self.subjects_table = QTableView(
            selectionMode=QTableView.SingleSelection,
            selectionBehavior=QTableView.SelectRows,
        )
        self.subjects_table.setModel(self.subjects_model.model)
        self.subjects_table.selectionModel().selectionChanged.connect(self.get_subject_idx)
        self.subjects_table.resizeColumnsToContents()
        self.subjects_table.resizeRowsToContents()
        self.subjects_table.horizontalHeader().setStretchLastSection(True)
        self.subjects_table.horizontalHeader().setFont(QFont('Ariel', 10))
        self.subjects_table.verticalHeader().setVisible(False)
        self.subjects_table.setColumnHidden(7, True)
        self.subjects_table.setColumnHidden(8, True)
        delegate_align_center = AlignCenterDelegate(self.subjects_table)
        for i in range(10):
            self.subjects_table.setItemDelegateForColumn(i, delegate_align_center)
        column_widths = (30, 60, 40, 230, 40, 50, 100)
        for idx, column_widths in enumerate(column_widths[:7]):
            self.subjects_table.setColumnWidth(idx, column_widths)
        # list_session_type_cue = ['Exposure', 'Fixed LGT', 'Rotating LGT 2', 'None']
        # combo_box_session_type = QComboBox()
        # combo_box_session_type.addItems(list_session_type_cue)
        # print(self.subjects_model.num_rows())
        # for row in range(self.subjects_model.num_rows()):
        #     idx = self.subjects_table.model().index(row, 6)
        #     self.subjects_table.setIndexWidget(idx, combo_box_session_type)

        # Session data label
        label_session_info = QLabel('Session Information')
        label_session_info.setFont(QFont('Ariel', 12))

        button_add_subject = QPushButton('Add')
        button_add_subject.clicked.connect(self.open_add_subject_dialog)

        button_set_session_data = QPushButton('Add To Session')
        button_set_session_data.clicked.connect(self.add_subject_to_session)

        # Create Session table
        # Create Subjects Table object
        self.session_subject_header = ['No', 'date', 'behavior', 'type', 'durr', 'trials', 'Num per', 'score',
                                       'tot err', 'id']
        session_subject_list = [['', '', '', '', '', '', '', '', '']]
        self.session_subject_table = QTableView(
            selectionMode=QTableView.SingleSelection,
            selectionBehavior=QTableView.SelectRows,
        )
        self.session_subject_table_model = TableStaticModel(
            self.session_subject_header,
            session_subject_list
        )
        self.session_subject_table.setModel(self.session_subject_table_model)
        # self.session_subject_table.selectionModel().selectionChanged.connect(self.get_action_vector_idx)
        self.session_subject_table.horizontalHeader().setStretchLastSection(True)
        self.session_subject_table.verticalHeader().hide()
        self.session_subject_table.horizontalHeader().setFont(QFont('Sans Serif', 6))
        self.session_subject_table.setFont(QFont('Sans Serif', 6))
        self.session_subject_table.resizeRowsToContents()
        self.session_subject_table.setColumnWidth(0, 30)
        self.session_subject_table.setColumnWidth(1, 90)
        self.session_subject_table.setColumnWidth(2, 150)
        self.session_subject_table.setColumnWidth(3, 90)
        self.session_subject_table.setColumnWidth(4, 60)
        self.session_subject_table.setColumnWidth(5, 50)
        self.session_subject_table.setColumnWidth(6, 50)
        self.session_subject_table.setColumnWidth(7, 50)
        self.session_subject_table.setColumnWidth(8, 50)

        label_trial_info = QLabel('Trial Information')
        label_trial_info.setFont(QFont('Ariel', 12))

        subjects_grid = QGridLayout()
        # Row 0
        subjects_grid.addWidget(label_subjects_tab, 0, 0, 1, 9)
        subjects_grid.addWidget(button_add_subject, 0, 9, 1, 2)
        # Row 1
        subjects_grid.addWidget(self.subjects_table, 1, 0, 4, 11)
        # Row 5
        subjects_grid.addWidget(button_set_session_data, 5, 0, 1, 3)
        # Row 6
        H_line_dark_1 = QHLine()
        H_line_dark_1.setLineWidth(1)
        subjects_grid.addWidget(H_line_dark_1, 6, 0, 1, 11)
        # Row 7
        subjects_grid.addWidget(label_session_info, 7, 0, 1, 11)
        # Row 8
        subjects_grid.addWidget(self.session_subject_table, 8, 0, 6, 11)
        # Row 16
        H_line_dark_2 = QHLine()
        H_line_dark_2.setLineWidth(1)
        subjects_grid.addWidget(H_line_dark_2, 16, 0, 1, 11)
        # Row 17
        subjects_grid.addWidget(label_trial_info, 17, 0, 1, 11)

        subjects_grid_frame = QFrame()
        subjects_grid_frame.setLayout(subjects_grid)

        tab_V_box = QVBoxLayout()
        tab_V_box.setSpacing(0)
        tab_V_box.setContentsMargins(0, 0, 0, 0)
        tab_V_box.setAlignment(Qt.AlignTop)
        tab_V_box.addWidget(subjects_grid_frame)

        subjects_control_tab = QWidget()
        subjects_control_tab.setLayout(tab_V_box)
        return subjects_control_tab

    def get_subject_idx(self):
        idx = self.subjects_table.selectionModel().currentIndex()
        subject_id = idx.sibling(idx.row(), 0).data()
        value = -1 if subject_id == '' else int(subject_id)
        self.db_cursor.execute(
            f'''
                SELECT session_number, date, behavior, session_type, session_duration, total_trials, total_perfect, 
                       score, total_errors
                FROM session WHERE subject_id = {subject_id};
            ''')
        session_subject_data = self.db_cursor.fetchall()
        self.db_conn_dir.commit()
        if value >= 0 and len(session_subject_data) > 0:
            del self.session_subject_table_model
            self.session_subject_table_model = TableStaticModel(
                self.session_subject_header,
                session_subject_data)
            self.session_subject_table.setModel(self.session_subject_table_model)
            # self.session_subject_table.selectionModel().selectionChanged.connect(self.get_action_vector_idx)
            self.session_subject_table.horizontalHeader().setStretchLastSection(True)
            self.session_subject_table.verticalHeader().hide()
            self.session_subject_table.horizontalHeader().setFont(QFont('Sans Serif', 6))
            self.session_subject_table.setFont(QFont('Sans Serif', 6))
            self.session_subject_table.resizeRowsToContents()
            # self.session_subject_table.setColumnWidth(0, 30)
            # self.session_subject_table.setColumnWidth(1, 90)
            # self.session_subject_table.setColumnWidth(2, 150)
            # self.session_subject_table.setColumnWidth(3, 90)
            # self.session_subject_table.setColumnWidth(4, 60)
            # self.session_subject_table.setColumnWidth(5, 50)
            # self.session_subject_table.setColumnWidth(6, 50)
            # self.session_subject_table.setColumnWidth(7, 50)
            # self.session_subject_table.setColumnWidth(8, 50)
        else:
            del self.session_subject_table_model
            self.session_subject_table_model = TableStaticModel(
                self.session_subject_header,
                [['', '', '', '', '', '', '', '', '']])
            self.session_subject_table.setModel(self.session_subject_table_model)

    def open_add_subject_dialog(self):
        # TODO: Add zero value to delay
        dialog = AddSubjectDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.subjects_model.add_subject(dialog.data)
            self.subjects_table.resizeRowsToContents()

    def add_subject_to_session(self):
        data = []
        idx = self.subjects_table.selectionModel().currentIndex()
        if idx.sibling(idx.row(), idx.column()).data() == None:
            print('A Subject has not been selected')
            return

        for i in range(7):
            data.append(idx.sibling(idx.row(), i).data())
        data.append(idx.sibling(idx.row(), 9).data())
        data.append(idx.sibling(idx.row(), 10).data())

        self.label_subject_id_data.setText(str(data[0]))
        self.label_subject_name_data.setText(data[1])
        self.label_sex_data.setText(data[2])
        self.label_behavior_data.setText(data[3])
        self.label_last_session_data.setText(str(data[4]))
        self.label_cue_conf_data.setText(data[5])
        self.label_session_type_data.setText(data[6])
        self.label_delay_data.setText(str(data[8]))

        reward_value = {'50', '100', '150', '200', '250', '300'}
        if str(data[7]) in reward_value:
            self.line_edit_reward_volume.setText(str(data[7]))
        else:
            self.line_edit_reward_volume.setText('150')

        self.init_session_data()

    def set_session_data(self):
        #data hold subject data
        data = []
        idx = self.subjects_table.selectionModel().currentIndex()
        if idx.sibling(idx.row(), idx.column()).data() == None:
            print('A Subject has not been selected')
            return

        for i in range(8):
            data.append(idx.sibling(idx.row(), i).data())

        self.label_subject_id_data.setText(str(data[0]))
        self.label_subject_name_data.setText(data[1])
        self.label_sex_data.setText(data[2])
        self.label_behavior_data.setText(data[3])
        sess_num = None
        if data[4] == 'None':
            sess_num = '0'
            self.label_session_number_data.setText(sess_num)
        else:
            sess_num += int(data[4])
            self.label_session_number_data.setText(str(sess_num))

        self.label_cue_conf_data.setText(data[5])
        dt_date = datetime.datetime.today()
        current_date = str(dt_date.month) + '/' + str(dt_date.day) + '/' + str(dt_date.year)
        self.label_session_date_data.setText(current_date)
        self.label_seed_data.setText(self.add_seed(sess_num, current_date))
        self.label_session_type_data.setText(data[6])

        reward_value = {'50','100','150','200','250','300'}
        if data[7] in reward_value:
            self.line_edit_reward_volume.setText(data[7])
        else:
            self.line_edit_reward_volume.setText('150')

    def add_seed(self, session_number, date):
        seed = str(session_number)
        seed += date.replace('/', '')
        t = time.localtime()
        seed += time.strftime('%H%M%S', t)
        return seed

    def get_action_vector_idx(self):
        idx = self.action_vec_table.selectionModel().currentIndex()
        self.action_vector_idx[0] = idx.sibling(idx.row(), 0).data()
        value = -1 if self.action_vector_idx[0] == '' else int(self.action_vector_idx[0])
        if value < 0:
            self.label_action_vector_contents.setText('Action Vec:\n[]')
        else:
            vec_str = str(self.action_vector_list[value])
            # vec_str = vec_str[:8] + '  |  ' + vec_str[10:56] +'  |  ' + vec_str[58:68] + '  |  ' + vec_str[70:80] + '  |  ' + vec_str[82:92] + '  |  ' + vec_str[94:97]
            self.label_action_vector_contents.setText(f'Act Vec: {vec_str}')

    def generate_start_goal_pairs(self, _seed, pair_type=None, cue_goal_index=None, goal_location=None):
        # function for running all cue presentations
        def generate_sg_pairs_1(sg_idx_):
            processing = True
            while processing:
                random.shuffle(sg_idx_)
                sg_pairs_list = [[(i, (i + j) % 4) for i in range(4)] for j in range(4)]
                sg_pairs_used = []
                start_list = []
                goal_list = []

                # First pull from sg_pair_list
                sg_pairs_used.append(sg_pairs_list[sg_idx_[0]].pop(random.randint(0, 3)))
                start_list.append(sg_pairs_used[0][0])
                goal_list.append(sg_pairs_used[0][1])

                # Second pull from sg_pair_list
                sg_pairs_temp = [
                    sgp
                    for sgp in sg_pairs_list[sg_idx_[1]]
                    if sgp[0] not in set(start_list)
                ]
                sg_pairs_temp_len = len(sg_pairs_temp)
                if sg_pairs_temp_len == 0:
                    continue
                elif sg_pairs_temp_len == 1:
                    sg_pairs_used.append(sg_pairs_temp[0])
                else:
                    sg_pairs_used.append(sg_pairs_temp[random.randint(0, sg_pairs_temp_len - 1)])
                sg_pairs_list[sg_idx_[1]].remove(sg_pairs_used[1])
                start_list.append(sg_pairs_used[1][0])
                goal_list.append(sg_pairs_used[1][1])

                # Third pull from sg_pair_list
                sg_pairs_temp = [
                    sgp
                    for sgp in sg_pairs_list[sg_idx_[2]]
                    if sgp[0] not in set(start_list) and sgp[1] not in set(goal_list)
                ]
                sg_pairs_temp_len = len(sg_pairs_temp)
                if sg_pairs_temp_len == 0:
                    continue
                elif sg_pairs_temp_len == 1:
                    sg_pairs_used.append(sg_pairs_temp[0])
                else:
                    sg_pairs_used.append(sg_pairs_temp[random.randint(0, sg_pairs_temp_len - 1)])
                sg_pairs_list[sg_idx_[2]].remove(sg_pairs_used[2])
                start_list.append(sg_pairs_used[2][0])
                goal_list.append(sg_pairs_used[2][1])

                # Fourth pull from sg_pair_list
                sg_pairs_temp = [
                    sgp
                    for sgp in sg_pairs_list[sg_idx_[3]]
                    if sgp[0] not in set(start_list) and sgp[1] not in set(goal_list)
                ]
                sg_pairs_temp_len = len(sg_pairs_temp)
                if sg_pairs_temp_len == 0:
                    continue
                elif sg_pairs_temp_len == 1:
                    sg_pairs_used.append(sg_pairs_temp[0])
                else:
                    sg_pairs_used.append(sg_pairs_temp[random.randint(0, sg_pairs_temp_len - 1)])
                sg_pairs_list[sg_idx_[3]].remove(sg_pairs_used[3])
                start_list.append(sg_pairs_used[3][0])
                goal_list.append(sg_pairs_used[3][1])

                # made it!
                processing = False
            return sg_pairs_list, sg_pairs_used, start_list, goal_list

        def generate_sg_pairs_2(sg_idx_, _sg_pairs_list, _sg_pairs_used, _start_list, _goal_list):
            process_atempts = 0
            processing = True
            while processing:
                random.shuffle(sg_idx_)
                sg_pairs_list = copy.deepcopy(_sg_pairs_list)
                sg_pairs_used = copy.deepcopy(_sg_pairs_used)
                start_list = copy.deepcopy(_start_list)
                goal_list = copy.deepcopy(_goal_list)

                # First pull from sg_pair_list
                sg_pairs_temp = [
                    sgp
                    for sgp in sg_pairs_list[sg_idx_[0]]
                    if goal_list.count(sgp[1]) < 2
                ]
                sg_pairs_temp_len = len(sg_pairs_temp)
                if sg_pairs_temp_len == 0:
                    process_atempts += 1
                    if process_atempts > 24:
                        return False, None, None
                    else:
                        continue
                elif sg_pairs_temp_len == 1:
                    sg_pairs_used.append(sg_pairs_temp[0])
                else:
                    sg_pairs_used.append(sg_pairs_temp[random.randint(0, sg_pairs_temp_len - 1)])
                sg_pairs_list[sg_idx_[0]].remove(sg_pairs_used[4])
                start_list.append(sg_pairs_used[4][0])
                goal_list.append(sg_pairs_used[4][1])

                # Second pull from sg_pair_list
                sg_pairs_temp = [
                    sgp
                    for sgp in sg_pairs_list[sg_idx_[1]]
                    if (start_list.count(sgp[0]) < 2 and
                        goal_list.count(sgp[1]) < 2)
                ]
                sg_pairs_temp_len = len(sg_pairs_temp)
                if sg_pairs_temp_len == 0:
                    process_atempts += 1
                    if process_atempts > 24:
                        return False, None, None
                    else:
                        continue
                elif sg_pairs_temp_len == 1:
                    sg_pairs_used.append(sg_pairs_temp[0])
                else:
                    sg_pairs_used.append(sg_pairs_temp[random.randint(0, sg_pairs_temp_len - 1)])
                sg_pairs_list[sg_idx_[1]].remove(sg_pairs_used[5])
                start_list.append(sg_pairs_used[5][0])
                goal_list.append(sg_pairs_used[5][1])

                # Third pull from sg_pair_list
                sg_pairs_temp = [
                    sgp
                    for sgp in sg_pairs_list[sg_idx_[2]]
                    if (start_list.count(sgp[0]) < 2 and
                        goal_list.count(sgp[1]) < 2)
                ]
                sg_pairs_temp_len = len(sg_pairs_temp)
                if sg_pairs_temp_len == 0:
                    process_atempts += 1
                    if process_atempts > 24:
                        return False, None, None
                    else:
                        continue
                elif sg_pairs_temp_len == 1:
                    sg_pairs_used.append(sg_pairs_temp[0])
                else:
                    sg_pairs_used.append(sg_pairs_temp[random.randint(0, sg_pairs_temp_len - 1)])
                sg_pairs_list[sg_idx_[2]].remove(sg_pairs_used[6])
                start_list.append(sg_pairs_used[6][0])
                goal_list.append(sg_pairs_used[6][1])

                # Fourth pull from sg_pair_list
                sg_pairs_temp = [
                    sgp
                    for sgp in sg_pairs_list[sg_idx_[3]]
                    if (start_list.count(sgp[0]) < 2 and
                        goal_list.count(sgp[1]) < 2)
                ]
                sg_pairs_temp_len = len(sg_pairs_temp)
                if sg_pairs_temp_len == 0:
                    process_atempts += 1
                    if process_atempts > 24:
                        return False, None, None
                    else:
                        continue
                elif sg_pairs_temp_len == 1:
                    sg_pairs_used.append(sg_pairs_temp[0])
                else:
                    sg_pairs_used.append(sg_pairs_temp[random.randint(0, sg_pairs_temp_len - 1)])
                sg_pairs_list[sg_idx_[3]].remove(sg_pairs_used[7])
                start_list.append(sg_pairs_used[7][0])
                goal_list.append(sg_pairs_used[7][1])

                processing = False
            return True, sg_pairs_list, sg_pairs_used

        def generate_sg_pairs_3(sg_idx_):
            processing = True
            while processing:
                sg_pairs_unused, sg_pairs_used, start_list, goal_list = generate_sg_pairs_1(sg_idx_)
                sg_pairs_used = swap_adjacent_matches_1(sg_pairs_used)
                process_state, sg_pairs_unused, sg_pairs_used = generate_sg_pairs_2(sg_idx_, sg_pairs_unused,
                                                                                    sg_pairs_used,
                                                                                    start_list, goal_list)
                if process_state == False:
                    continue
                else:
                    sg_pairs_used = swap_adjacent_matches_2(sg_pairs_used)
                    sg_pairs_unused = [sgpu[i] for sgpu in sg_pairs_unused for i in range(2)]
                    sg_pairs_list = sg_pairs_used + sg_pairs_unused
                    sg_pairs_list = swap_adjacent_matches_3(sg_pairs_list)
                    return sg_pairs_list

        def swap_adjacent_matches_1(sg_pairs):
            random.shuffle(sg_pairs)
            for i in range(1, 4):
                if sg_pairs[i - 1][0] == sg_pairs[i][0] or sg_pairs[i - 1][1] == sg_pairs[i][1]:
                    sg_pairs[i], sg_pairs[(i + 1) % 4] = sg_pairs[(i + 1) % 4], sg_pairs[i]
            return sg_pairs

        def swap_adjacent_matches_2(sg_pairs):
            sg_pairs_a = sg_pairs[:4]
            sg_pairs_b = sg_pairs[4:]
            random.shuffle(sg_pairs_b)
            sg_pairs = sg_pairs_a + sg_pairs_b
            processing = True
            swapped = False
            while processing:
                idx = [4, 5, 6, 7]
                swapped = False
                for i in range(4, 8):
                    if sg_pairs[i - 1][0] == sg_pairs[i][0] or sg_pairs[i - 1][1] == sg_pairs[i][1]:
                        idx.remove(i)
                        random.shuffle(idx)
                        sg_pairs[i], sg_pairs[idx[0]] = sg_pairs[idx[0]], sg_pairs[i]
                        swapped = True
                        break
                if swapped == False:
                    processing = False
            return sg_pairs

        def swap_adjacent_matches_3(sg_pairs):
            sg_pairs_a = sg_pairs[:8]
            sg_pairs_b = sg_pairs[8:]
            random.shuffle(sg_pairs_b)
            sg_pairs = sg_pairs_a + sg_pairs_b
            processing = True
            swapped = False
            while processing:
                idx = [8, 9, 10, 11, 12, 13, 14, 15]
                swapped = False
                for i in range(8, 16):
                    if (sg_pairs[i - 1][0] == sg_pairs[i][0] or
                            sg_pairs[i - 1][1] == sg_pairs[i][1]):
                        idx.remove(i)
                        random.shuffle(idx)
                        sg_pairs[i], sg_pairs[idx[0]] = sg_pairs[idx[0]], sg_pairs[i]
                        swapped = True
                        break
                if swapped == False:
                    processing = False
            return sg_pairs

        # functions for retained condition
        def generate_sg_pairs_retained_1(sg_idx_, pair_type):
            processing = True
            while processing:
                sg_pairs_list = [[(i, (i + j) % 4) for i in range(4)] for j in range(4)]
                del sg_pairs_list[pair_type]
                random.shuffle(sg_idx_)
                sg_pairs_used = []
                start_list = []
                goal_list = []

                # First pull from sg_pair_list
                rd = random.randint(0, 3)
                sg_pairs_used.append(sg_pairs_list[sg_idx_[0]].pop(rd))
                start_list.append(sg_pairs_used[0][0])
                goal_list.append(sg_pairs_used[0][1])

                # Second pull from sg_pair_list
                sg_pairs_temp = [
                    sgp
                    for sgp in sg_pairs_list[sg_idx_[1]]
                    if sgp[0] not in set(start_list) and sgp[1] not in set(goal_list)
                ]
                sg_pairs_temp_len = len(sg_pairs_temp)
                if sg_pairs_temp_len == 0:
                    sg_pairs_list.clear()
                    continue
                elif sg_pairs_temp_len == 1:
                    sg_pairs_used.append(sg_pairs_temp[0])
                else:
                    sg_pairs_used.append(sg_pairs_temp[random.randint(0, sg_pairs_temp_len - 1)])
                sg_pairs_list[sg_idx_[1]].remove(sg_pairs_used[1])
                start_list.append(sg_pairs_used[1][0])
                goal_list.append(sg_pairs_used[1][1])

                # Third pull from sg_pair_list
                sg_pairs_temp = [
                    sgp
                    for sgp in sg_pairs_list[sg_idx_[2]]
                    if sgp[0] not in set(start_list) and sgp[1] not in set(goal_list)
                ]
                sg_pairs_temp_len = len(sg_pairs_temp)
                if sg_pairs_temp_len == 0:
                    sg_pairs_list.clear()
                    continue
                elif sg_pairs_temp_len == 1:
                    sg_pairs_used.append(sg_pairs_temp[0])
                else:
                    sg_pairs_used.append(sg_pairs_temp[random.randint(0, sg_pairs_temp_len - 1)])
                sg_pairs_list[sg_idx_[2]].remove(sg_pairs_used[2])
                start_list.append(sg_pairs_used[2][0])
                goal_list.append(sg_pairs_used[2][1])
                # made it!
                processing = False
            return sg_pairs_list, sg_pairs_used, start_list, goal_list

        def generate_sg_pairs_retained_2(sg_idx_, _sg_pairs_list, _sg_pairs_used, _start_list, _goal_list):
            process_atempts = 0
            processing = True
            while processing:
                random.shuffle(sg_idx_)
                __sg_pairs_list = copy.deepcopy(_sg_pairs_list)
                sg_pairs_used = copy.deepcopy(_sg_pairs_used)
                start_list = copy.deepcopy(_start_list)
                goal_list = copy.deepcopy(_goal_list)

                # First pull from sg_pair_list
                sg_pairs_temp = [
                    sgp
                    for sgp in __sg_pairs_list[sg_idx_[0]]
                    if goal_list.count(sgp[1]) < 2
                ]
                sg_pairs_temp_len = len(sg_pairs_temp)
                if sg_pairs_temp_len == 0:
                    process_atempts += 1
                    if process_atempts > 24:
                        return False, None, None
                    else:
                        continue
                elif sg_pairs_temp_len == 1:
                    sg_pairs_used.append(sg_pairs_temp[0])
                else:
                    sg_pairs_used.append(sg_pairs_temp[random.randint(0, sg_pairs_temp_len - 1)])
                __sg_pairs_list[sg_idx_[0]].remove(sg_pairs_used[3])
                start_list.append(sg_pairs_used[3][0])
                goal_list.append(sg_pairs_used[3][1])

                # Second pull from sg_pair_list
                sg_pairs_temp = [
                    sgp
                    for sgp in __sg_pairs_list[sg_idx_[1]]
                    if (start_list.count(sgp[0]) < 2 and
                        goal_list.count(sgp[1]) < 2)
                ]
                sg_pairs_temp_len = len(sg_pairs_temp)
                if sg_pairs_temp_len == 0:
                    process_atempts += 1
                    if process_atempts > 24:
                        return False, None, None
                    else:
                        continue
                elif sg_pairs_temp_len == 1:
                    sg_pairs_used.append(sg_pairs_temp[0])
                else:
                    sg_pairs_used.append(sg_pairs_temp[random.randint(0, sg_pairs_temp_len - 1)])
                __sg_pairs_list[sg_idx_[1]].remove(sg_pairs_used[4])
                start_list.append(sg_pairs_used[4][0])
                goal_list.append(sg_pairs_used[4][1])

                # Third pull from sg_pair_list
                sg_pairs_temp = [
                    sgp
                    for sgp in __sg_pairs_list[sg_idx_[2]]
                    if (start_list.count(sgp[0]) < 2 and
                        goal_list.count(sgp[1]) < 2)
                ]
                sg_pairs_temp_len = len(sg_pairs_temp)
                if sg_pairs_temp_len == 0:
                    process_atempts += 1
                    if process_atempts > 24:
                        return False, None, None
                    else:
                        continue
                elif sg_pairs_temp_len == 1:
                    sg_pairs_used.append(sg_pairs_temp[0])
                else:
                    sg_pairs_used.append(sg_pairs_temp[random.randint(0, sg_pairs_temp_len - 1)])
                __sg_pairs_list[sg_idx_[2]].remove(sg_pairs_used[5])
                start_list.append(sg_pairs_used[5][0])
                goal_list.append(sg_pairs_used[5][1])

                processing = False
            return True, __sg_pairs_list, sg_pairs_used

        def generate_sg_pairs_retained_3(sg_idx_, pair_type):
            processing = True
            while processing:
                sg_pairs_unused, sg_pairs_used, start_list, goal_list = generate_sg_pairs_retained_1(sg_idx_,
                                                                                                     pair_type)
                process_state, sg_pairs_unused, sg_pairs_used = generate_sg_pairs_retained_2(sg_idx_, sg_pairs_unused,
                                                                                             sg_pairs_used,
                                                                                             start_list, goal_list)
                if process_state == False:
                    continue
                else:
                    sg_pairs_used = swap_adjacent_matches_retained_2(sg_pairs_used)
                    sg_pairs_unused = [sgpu[i] for sgpu in sg_pairs_unused for i in range(2)]
                    sg_pairs_list = sg_pairs_used + sg_pairs_unused
                    sg_pairs_list = swap_adjacent_matches_retained_3(sg_pairs_list)
                    return sg_pairs_list

        def swap_adjacent_matches_retained_2(sg_pairs):
            sg_pairs_a = sg_pairs[:3]
            sg_pairs_b = sg_pairs[3:]
            random.shuffle(sg_pairs_b)
            sg_pairs = sg_pairs_a + sg_pairs_b
            processing = True
            while processing:
                idx = [3, 4, 5]
                swapped = False
                for i in range(3, 6):
                    if sg_pairs[i - 1][0] == sg_pairs[i][0]:
                        idx.remove(i)
                        random.shuffle(idx)
                        sg_pairs[i], sg_pairs[idx[0]] = sg_pairs[idx[0]], sg_pairs[i]
                        swapped = True
                        break
                if swapped == False:
                    processing = False
            return sg_pairs

        def swap_adjacent_matches_retained_3(sg_pairs):
            sg_pairs_a = sg_pairs[:6]
            sg_pairs_b = sg_pairs[6:]
            random.shuffle(sg_pairs_b)
            sg_pairs = sg_pairs_a + sg_pairs_b
            processing = True
            swapped = False
            while processing:
                idx = [6, 7, 8, 9, 10, 11]
                swapped = False
                for i in range(6, 12):
                    if (sg_pairs[i - 1][0] == sg_pairs[i][0] or
                            sg_pairs[i - 1][1] == sg_pairs[i][1]):
                        idx.remove(i)
                        random.shuffle(idx)
                        sg_pairs[i], sg_pairs[idx[0]] = sg_pairs[idx[0]], sg_pairs[i]
                        swapped = True
                        break
                if swapped == False:
                    processing = False
            return sg_pairs

        def generate_sg_training(list_size):
            sg_pairs_list = [[(i, j) for i in range(4)] for j in range(4)]
            sg_idx = [0, 1, 2, 3]
            idx = random.choice(sg_idx)
            sg_pairs = []
            for _ in range(list_size):
                sg_pairs_temp = sg_pairs_list[idx].copy()
                random.shuffle(sg_pairs_temp)
                sg_pairs += sg_pairs_temp
            return sg_pairs

        def generate_sg_rotating_4A(list_size):
            sg_pairs = []
            sg_pairs_list = [[(i, j) for i in range(4)] for j in range(4)]
            sg_idx = [0, 1, 2, 3]
            random.shuffle(sg_idx)

            for i in sg_idx:
                for _ in range(list_size):
                    sg_pairs_temp = sg_pairs_list[i].copy()
                    random.shuffle(sg_pairs_temp)
                    sg_pairs += sg_pairs_temp
            return sg_pairs

        def generate_sg_rotating_2(list_size):
            sg_pairs_list = [[(i, j) for i in range(4)] for j in range(4)]
            # print(sg_pairs_list,'\n')
            sg_idx = [[0, 1], [0, 2], [1, 2], [1, 3], [2, 3], [2, 0], [3, 0], [3, 1]]
            sg_idx_pair = random.choice(sg_idx)

            sg_pairs = []
            for _ in range(list_size):
                sg_pairs_temp_1 = sg_pairs_list[sg_idx_pair[0]].copy()
                sg_pairs_temp_2 = sg_pairs_list[sg_idx_pair[1]].copy()
                sg_pairs_temp_3 = sg_pairs_temp_1 + sg_pairs_temp_2
                random.shuffle(sg_pairs_temp_3)
                processing = True
                while processing:
                    idx = [i for i in range(8)]
                    swapped = False
                    for i in range(2, 8):
                        if (sg_pairs_temp_3[i - 1][1] == sg_pairs_temp_3[i][1] and
                                sg_pairs_temp_3[i - 2][1] == sg_pairs_temp_3[i][1]):
                            idx.remove(i)
                            idx.remove(i - 1)
                            idx.remove(i - 2)
                            rnd_idx = random.choice(idx)
                            sg_pairs_temp_3[i], sg_pairs_temp_3[rnd_idx] = sg_pairs_temp_3[rnd_idx], sg_pairs_temp_3[i]
                            swapped = True
                            break
                    if swapped == False:
                        processing = False
                sg_pairs += sg_pairs_temp_3

            return sg_pairs

        def generate_sg_differentiate_1(list_size, ort):
            # Third index is tell if reward is to the right or to the left.
            print(ort)
            # Determine the orientation and create the initial sg_pairs_list based on the orientation
            if ort == 'N/NE' or ort == 'N/SW':
                print('NE or SW')
                sg_pairs_list = [(i, (i + 1) % 4, 0) for i in range(4)] + [(i, (i - 1) % 4, 1) for i in range(4)]
            else:
                print('SE or NW')
                sg_pairs_list = [(i, i, 0) for i in range(4)] + [(i, (i + 2) % 4, 1) for i in range(4)]

            sg_pairs = []
            # Shuffle and copy sg_pairs_list to sg_pairs list_size times
            for _ in range(list_size):
                random.shuffle(sg_pairs_list)
                sg_pairs += sg_pairs_list.copy()

            passed = False
            check = 0
            # Ensure no four consecutive elements in sg_pairs have the same first or third element
            while not passed:
                passed = True
                for i, sgp in enumerate(sg_pairs[0:-3]):
                    if ((sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0] and sgp[0] == sg_pairs[i + 3][0]) or
                        (sgp[2] == 1 and sg_pairs[i + 1][2] == 1 and sg_pairs[i + 2][2] == 1 and sg_pairs[i + 3][2] == 1) or
                        (sgp[2] == 0 and sg_pairs[i + 1][2] == 0 and sg_pairs[i + 2][2] == 0 and sg_pairs[i + 3][2] == 0)):  
                        # If a sequence of four is found, swap the current element with a random element
                        if i < 2:
                            rand_idx = random.randint(i + 4, list_size * 8 - 1)
                        elif i < list_size * 8 - 4:
                            rand_idx_list = [random.randint(0, i - 1), random.randint(i + 4, list_size * 8 - 1)]
                            rand_idx = random.choice(rand_idx_list)
                        else:
                            rand_idx = random.randint(0, i - 1)
                        sg_pairs[i], sg_pairs[rand_idx] = sg_pairs[rand_idx], sg_pairs[i]

                        passed = False
                check += 1
            return sg_pairs

        def generate_sg_differentiate_2a(list_size, ort):
            if ort == 'N/NE' or ort == 'N/SW':
                print('NE or SW')
                sg_pairs_list_warmup = [(i, (i + 1) % 4, 0) for i in range(4)] + [(i, (i - 1) % 4, 1) for i in range(4)]
            else:
                print('SE or NW')
                sg_pairs_list_warmup = [(i, i, 0) for i in range(4)] + [(i, (i + 2) % 4, 1) for i in range(4)]

            if ort == 'N/NW':
                # Third index: LL = 0, LR = 1, RL =2
                sg_pairs_list_test = [(i, (j + i) % 4, j) for i in range(4) for j in range(3)]
            elif ort == 'N/NE':
                # Third index:  LR= 0, RL = 1, RR =2
                sg_pairs_list_test = [(i, (j + i + 1) % 4, j) for i in range(4) for j in range(3)]
            elif ort == 'N/SE':
                # Third index:  RL= 0, RR = 1, LL =2
                sg_pairs_list_test = [(i, (j + i + 2) % 4, j) for i in range(4) for j in range(3)]
            elif ort == 'N/SW':
                # Third index:  RR= 0, LL = 1, LR =2
                sg_pairs_list_test = [(i, (j + i + 3) % 4, j) for i in range(4) for j in range(3)]

            start_repeat_limit = 3
            goal_repeat_limit = 3
            route_repeat_limit = 3
            start_threepeat = 0
            goal_threepeat = 0
            route_threepeat = 0
            start_fourpeat = 0
            goal_fourpeat = 0
            route_fourpeat = 0
            route_repeat_loc = []
            goal_repeat_loc = []
            start_repeat_loc = []
            sg_pairs = []
            passed = False
            fails = 0
            while not passed:
                passed = True
                sg_pairs.clear()
                for i in range(list_size):
                    if i < 2:
                        random.shuffle(sg_pairs_list_warmup)
                        sg_pairs += sg_pairs_list_warmup.copy()
                    else:
                        random.shuffle(sg_pairs_list_test)
                        sg_pairs += sg_pairs_list_test.copy()
                for i, sgp in enumerate(sg_pairs[0:-3]):
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2] and sgp[2] == sg_pairs[i + 3][2]:
                        route_fourpeat += 1
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1] and sgp[1] == sg_pairs[i + 3][1]:
                        goal_fourpeat += 1
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0] and sgp[0] == sg_pairs[i + 3][0]:
                        start_fourpeat += 1
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2]:
                        route_threepeat += 1
                        route_repeat_loc.append(i)
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1]:
                        goal_threepeat += 1
                        goal_repeat_loc.append(i)
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0]:
                        start_threepeat += 1
                        start_repeat_loc.append(i)
                # Catch four repeats or over threepeat limit
                if (route_fourpeat > 0 or goal_fourpeat > 0 or start_fourpeat > 0 or
                        route_threepeat > route_repeat_limit or
                        goal_threepeat > goal_repeat_limit or
                        start_threepeat > start_repeat_limit):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(route_repeat_loc) == 3 and (route_repeat_loc[1] - route_repeat_loc[0] < 16) or
                        (len(route_repeat_loc) == 2 and route_repeat_loc[1] - route_repeat_loc[0] < 16)):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(route_repeat_loc) == 3 and (route_repeat_loc[2] - route_repeat_loc[1] < 16):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(goal_repeat_loc) == 3 and (goal_repeat_loc[1] - goal_repeat_loc[0] < 16) or
                        (len(goal_repeat_loc) == 2 and goal_repeat_loc[1] - goal_repeat_loc[0] < 16)):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(goal_repeat_loc) == 3 and (goal_repeat_loc[2] - goal_repeat_loc[1] < 16):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(start_repeat_loc) == 3 and (start_repeat_loc[1] - start_repeat_loc[0] < 16) or
                        (len(start_repeat_loc) == 2 and start_repeat_loc[1] - start_repeat_loc[0] < 16)):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(start_repeat_loc) == 3 and (start_repeat_loc[2] - start_repeat_loc[1] < 16):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
            # return sg_pairs, fails, [(start_threepeat, start_repeat_loc), (goal_threepeat, goal_repeat_loc),
            #                          (route_threepeat, route_repeat_loc)]
            return sg_pairs

        def generate_sg_differentiate_2b(list_size, ort):
            if ort == 'N/NW':
                # Third index: LL = 0, LR = 1, RL =2
                sg_pairs_list = [(i, (j + i) % 4, j) for i in range(4) for j in range(3)]
            elif ort == 'N/NE':
                # Third index:  LR= 0, RL = 1, RR =2
                sg_pairs_list = [(i, (j + i + 1) % 4, j) for i in range(4) for j in range(3)]
            elif ort == 'N/SE':
                # Third index:  RL= 0, RR = 1, LL =2
                sg_pairs_list = [(i, (j + i + 2) % 4, j) for i in range(4) for j in range(3)]
            elif ort == 'N/SW':
                # Third index:  RR= 0, LL = 1, LR =2
                sg_pairs_list = [(i, (j + i + 3) % 4, j) for i in range(4) for j in range(3)]

            start_repeat_limit = 3
            goal_repeat_limit = 3
            route_repeat_limit = 3
            start_threepeat = 0
            goal_threepeat = 0
            route_threepeat = 0
            start_fourpeat = 0
            goal_fourpeat = 0
            route_fourpeat = 0
            route_repeat_loc = []
            goal_repeat_loc = []
            start_repeat_loc = []
            sg_pairs = []
            passed = False
            fails = 0
            while not passed:
                passed = True
                sg_pairs.clear()
                for _ in range(list_size):
                    random.shuffle(sg_pairs_list)
                    sg_pairs += sg_pairs_list.copy()
                for i, sgp in enumerate(sg_pairs[0:-3]):
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2] and sgp[2] == sg_pairs[i + 3][2]:
                        route_fourpeat += 1
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1] and sgp[1] == sg_pairs[i + 3][1]:
                        goal_fourpeat += 1
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0] and sgp[0] == sg_pairs[i + 3][0]:
                        start_fourpeat += 1
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2]:
                        route_threepeat += 1
                        route_repeat_loc.append(i)
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1]:
                        goal_threepeat += 1
                        goal_repeat_loc.append(i)
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0]:
                        start_threepeat += 1
                        start_repeat_loc.append(i)
                # Catch four repeats or over threepeat limit
                if (route_fourpeat > 0 or goal_fourpeat > 0 or start_fourpeat > 0 or
                        route_threepeat > route_repeat_limit or
                        goal_threepeat > goal_repeat_limit or
                        start_threepeat > start_repeat_limit):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(route_repeat_loc) == 3 and (route_repeat_loc[1] - route_repeat_loc[0] < 16) or
                        (len(route_repeat_loc) == 2 and route_repeat_loc[1] - route_repeat_loc[0] < 16)):
                    sg_pairs = []
                    for _ in range(list_size):
                        random.shuffle(sg_pairs_list)
                        sg_pairs += sg_pairs_list.copy()
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(route_repeat_loc) == 3 and (route_repeat_loc[2] - route_repeat_loc[1] < 16):
                    sg_pairs = []
                    for _ in range(list_size):
                        random.shuffle(sg_pairs_list)
                        sg_pairs += sg_pairs_list.copy()
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(goal_repeat_loc) == 3 and (goal_repeat_loc[1] - goal_repeat_loc[0] < 16) or
                        (len(goal_repeat_loc) == 2 and goal_repeat_loc[1] - goal_repeat_loc[0] < 16)):
                    sg_pairs = []
                    for _ in range(list_size):
                        random.shuffle(sg_pairs_list)
                        sg_pairs += sg_pairs_list.copy()
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(goal_repeat_loc) == 3 and (goal_repeat_loc[2] - goal_repeat_loc[1] < 16):
                    sg_pairs = []
                    for _ in range(list_size):
                        random.shuffle(sg_pairs_list)
                        sg_pairs += sg_pairs_list.copy()
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(start_repeat_loc) == 3 and (start_repeat_loc[1] - start_repeat_loc[0] < 16) or
                        (len(start_repeat_loc) == 2 and start_repeat_loc[1] - start_repeat_loc[0] < 16)):
                    sg_pairs = []
                    for _ in range(list_size):
                        random.shuffle(sg_pairs_list)
                        sg_pairs += sg_pairs_list.copy()
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(start_repeat_loc) == 3 and (start_repeat_loc[2] - start_repeat_loc[1] < 16):
                    sg_pairs = []
                    for _ in range(list_size):
                        random.shuffle(sg_pairs_list)
                        sg_pairs += sg_pairs_list.copy()
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
            # return sg_pairs, fails, [(start_threepeat, start_repeat_loc), (goal_threepeat, goal_repeat_loc),
            #                          (route_threepeat, route_repeat_loc)]
            return sg_pairs

        def generate_sg_discrimination_3a(list_size, ort):
            sg_pairs_list_trained = []
            sg_pairs_list_test = []

            if ort == 'N/NW':
                # Third index: LL = 0, LR = 1, RL =2
                sg_pairs_list_trained = [(i, (j + i) % 4, j) for i in range(4) for j in range(3)]
            elif ort == 'N/NE':
                # Third index:  LR= 0, RL = 1, RR =2
                sg_pairs_list_trained = [(i, (j + i + 1) % 4, j) for i in range(4) for j in range(3)]
            elif ort == 'N/SE':
                # Third index:  RL= 0, RR = 1, LL =2
                sg_pairs_list_trained = [(i, (j + i + 1) % 4, j) for i in range(4) for j in range(3)]
            elif ort == 'N/SW':
                # Third index:  RR= 0, LL = 1, LR =2
                sg_pairs_list_trained = [(i, (j + i + 3) % 4, j) for i in range(4) for j in range(3)]


            if ort == 'N/NW':
                # Third index: 0 = RL, 1 = LL, 2 = LR, 3 = RR
                sg_pairs_list_0 = [(i, (i + 2) % 4, 0) for i in range(4)]
                sg_pairs_list_1 = [(i, i, 1) for i in range(4)]
                sg_pairs_list_2 = [(i % 4, (i + 1) % 4, 2) for i in range(8)]
                sg_pairs_list_3 = [(i % 4, (i + 3) % 4, 3) for i in range(8)]
                sg_pairs_list_test += sg_pairs_list_0 + sg_pairs_list_1 + sg_pairs_list_2 + sg_pairs_list_3
            elif ort == 'N/NE':
                # Third index: 0 = LR, 1 = RR, 2 = RL, 3 = LL
                sg_pairs_list_0 = [(i, (i + 1) % 4, 0) for i in range(4)]
                sg_pairs_list_1 = [(i, (i + 3) % 4, 1) for i in range(4)]
                sg_pairs_list_2 = [(i % 4, (i + 2) % 4, 2) for i in range(8)]
                sg_pairs_list_3 = [(i % 4, i % 4, 3) for i in range(8)]
                sg_pairs_list_test += sg_pairs_list_0 + sg_pairs_list_1 + sg_pairs_list_2 + sg_pairs_list_3
            elif ort == 'N/SE':
                # Third index: 0 = RL, 1 = LL, 2 = RR, 3 = LR
                sg_pairs_list_0 = [(i, (i + 2) % 4, 0) for i in range(4)]
                sg_pairs_list_1 = [(i, i, 1) for i in range(4)]
                sg_pairs_list_2 = [(i % 4, (i + 3) % 4, 2) for i in range(8)]
                sg_pairs_list_3 = [(i % 4, (i + 1) % 4, 3) for i in range(8)]
                sg_pairs_list_test += sg_pairs_list_0 + sg_pairs_list_1 + sg_pairs_list_2 + sg_pairs_list_3
            elif ort == 'N/SW':
                # Third index: 0 = RR, 1 = LR, 2 = LL, 3 = RL
                sg_pairs_list_0 = [(i, (i + 3) % 4, 0) for i in range(4)]
                sg_pairs_list_1 = [(i, (i + 1) % 4, 1) for i in range(4)]
                sg_pairs_list_2 = [(i % 4, i % 4, 2) for i in range(8)]
                sg_pairs_list_3 = [(i % 4, (i + 2) % 4, 3) for i in range(8)]
                sg_pairs_list_test += sg_pairs_list_0 + sg_pairs_list_1 + sg_pairs_list_2 + sg_pairs_list_3

            start_repeat_limit = 3
            goal_repeat_limit = 3
            route_repeat_limit = 3
            start_threepeat = 0
            goal_threepeat = 0
            route_threepeat = 0
            start_fourpeat = 0
            goal_fourpeat = 0
            route_fourpeat = 0
            route_repeat_loc = []
            goal_repeat_loc = []
            start_repeat_loc = []
            sg_pairs = []
            passed = False
            fails = 0

            while not passed:
                passed = True
                sg_pairs.clear()
                for i in range(list_size):
                    if i > 0:
                        random.shuffle(sg_pairs_list_trained)
                        sg_pairs += sg_pairs_list_trained.copy()
                    else:
                        random.shuffle(sg_pairs_list_test)
                        sg_pairs += sg_pairs_list_test.copy()

                for i, sgp in enumerate(sg_pairs[0:-3]):
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2] and sgp[2] == sg_pairs[i + 3][2]:
                        route_fourpeat += 1
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1] and sgp[1] == sg_pairs[i + 3][1]:
                        goal_fourpeat += 1
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0] and sgp[0] == sg_pairs[i + 3][0]:
                        start_fourpeat += 1
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2]:
                        route_threepeat += 1
                        route_repeat_loc.append(i)
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1]:
                        goal_threepeat += 1
                        goal_repeat_loc.append(i)
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0]:
                        start_threepeat += 1
                        start_repeat_loc.append(i)
                # Catch four repeats or over threepeat limit
                if (route_fourpeat > 0 or goal_fourpeat > 0 or start_fourpeat > 0 or
                        route_threepeat > route_repeat_limit or
                        goal_threepeat > goal_repeat_limit or
                        start_threepeat > start_repeat_limit):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(route_repeat_loc) == 3 and (route_repeat_loc[1] - route_repeat_loc[0] < 24) or
                        (len(route_repeat_loc) == 2 and route_repeat_loc[1] - route_repeat_loc[0] < 24)):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(route_repeat_loc) == 3 and (route_repeat_loc[2] - route_repeat_loc[1] < 24):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(goal_repeat_loc) == 3 and (goal_repeat_loc[1] - goal_repeat_loc[0] < 24) or
                        (len(goal_repeat_loc) == 2 and goal_repeat_loc[1] - goal_repeat_loc[0] < 24)):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(goal_repeat_loc) == 3 and (goal_repeat_loc[2] - goal_repeat_loc[1] < 24):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(start_repeat_loc) == 3 and (start_repeat_loc[1] - start_repeat_loc[0] < 24) or
                        (len(start_repeat_loc) == 2 and start_repeat_loc[1] - start_repeat_loc[0] < 24)):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(start_repeat_loc) == 3 and (start_repeat_loc[2] - start_repeat_loc[1] < 24):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
            return sg_pairs

        def generate_sg_discrimination_3b(list_size, ort):
            sg_pairs_list = []
            if ort == 'N/NW':
                # Third index: 0 = RL, 1 = LL, 2 = LR, 3 = RR
                sg_pairs_list_0 = [(i, (i + 2) % 4, 0) for i in range(4)]
                sg_pairs_list_1 = [(i, i, 1) for i in range(4)]
                sg_pairs_list_2 = [(i % 4, (i + 1) % 4, 2) for i in range(8)]
                sg_pairs_list_3 = [(i % 4, (i + 3) % 4, 3) for i in range(8)]
                sg_pairs_list += sg_pairs_list_0 + sg_pairs_list_1 + sg_pairs_list_2 + sg_pairs_list_3
            elif ort == 'N/NE':
                # Third index: 0 = LR, 1 = RR, 2 = RL, 3 = LL
                sg_pairs_list_0 = [(i, (i + 1) % 4, 0) for i in range(4)]
                sg_pairs_list_1 = [(i, (i + 3) % 4, 1) for i in range(4)]
                sg_pairs_list_2 = [(i % 4, (i + 2) % 4, 2) for i in range(8)]
                sg_pairs_list_3 = [(i % 4, i % 4, 3) for i in range(8)]
                sg_pairs_list += sg_pairs_list_0 + sg_pairs_list_1 + sg_pairs_list_2 + sg_pairs_list_3
            elif ort == 'N/SE':
                # Third index: 0 = RL, 1 = LL, 2 = RR, 3 = LR
                sg_pairs_list_0 = [(i, (i + 2) % 4, 0) for i in range(4)]
                sg_pairs_list_1 = [(i, i, 1) for i in range(4)]
                sg_pairs_list_2 = [(i % 4, (i + 3) % 4, 2) for i in range(8)]
                sg_pairs_list_3 = [(i % 4, (i + 1) % 4, 3) for i in range(8)]
                sg_pairs_list += sg_pairs_list_0 + sg_pairs_list_1 + sg_pairs_list_2 + sg_pairs_list_3
            elif ort == 'N/SW':
                # Third index: 0 = RR, 1 = LR, 2 = LL, 3 = RL
                sg_pairs_list_0 = [(i, (i + 3) % 4, 0) for i in range(4)]
                sg_pairs_list_1 = [(i, (i + 1) % 4, 1) for i in range(4)]
                sg_pairs_list_2 = [(i % 4, i % 4, 2) for i in range(8)]
                sg_pairs_list_3 = [(i % 4, (i + 2) % 4, 3) for i in range(8)]
                sg_pairs_list += sg_pairs_list_0 + sg_pairs_list_1 + sg_pairs_list_2 + sg_pairs_list_3

            start_repeat_limit = 3
            goal_repeat_limit = 3
            route_repeat_limit = 3
            start_threepeat = 0
            goal_threepeat = 0
            route_threepeat = 0
            start_fourpeat = 0
            goal_fourpeat = 0
            route_fourpeat = 0
            route_repeat_loc = []
            goal_repeat_loc = []
            start_repeat_loc = []
            sg_pairs = []
            passed = False
            fails = 0

            while not passed:
                passed = True
                sg_pairs.clear()
                for _ in range(list_size):
                    random.shuffle(sg_pairs_list)
                    sg_pairs += sg_pairs_list.copy()
                for i, sgp in enumerate(sg_pairs[0:-3]):
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2] and sgp[2] == sg_pairs[i + 3][2]:
                        route_fourpeat += 1
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1] and sgp[1] == sg_pairs[i + 3][1]:
                        goal_fourpeat += 1
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0] and sgp[0] == sg_pairs[i + 3][0]:
                        start_fourpeat += 1
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2]:
                        route_threepeat += 1
                        route_repeat_loc.append(i)
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1]:
                        goal_threepeat += 1
                        goal_repeat_loc.append(i)
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0]:
                        start_threepeat += 1
                        start_repeat_loc.append(i)
                # Catch four repeats or over threepeat limit
                if (route_fourpeat > 0 or goal_fourpeat > 0 or start_fourpeat > 0 or
                        route_threepeat > route_repeat_limit or
                        goal_threepeat > goal_repeat_limit or
                        start_threepeat > start_repeat_limit):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(route_repeat_loc) == 3 and (route_repeat_loc[1] - route_repeat_loc[0] < 24) or
                        (len(route_repeat_loc) == 2 and route_repeat_loc[1] - route_repeat_loc[0] < 24)):
                    sg_pairs = []
                    for _ in range(list_size):
                        random.shuffle(sg_pairs_list)
                        sg_pairs += sg_pairs_list.copy()
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(route_repeat_loc) == 3 and (route_repeat_loc[2] - route_repeat_loc[1] < 24):
                    sg_pairs = []
                    for _ in range(list_size):
                        random.shuffle(sg_pairs_list)
                        sg_pairs += sg_pairs_list.copy()
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(goal_repeat_loc) == 3 and (goal_repeat_loc[1] - goal_repeat_loc[0] < 24) or
                        (len(goal_repeat_loc) == 2 and goal_repeat_loc[1] - goal_repeat_loc[0] < 24)):
                    sg_pairs = []
                    for _ in range(list_size):
                        random.shuffle(sg_pairs_list)
                        sg_pairs += sg_pairs_list.copy()
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(goal_repeat_loc) == 3 and (goal_repeat_loc[2] - goal_repeat_loc[1] < 24):
                    sg_pairs = []
                    for _ in range(list_size):
                        random.shuffle(sg_pairs_list)
                        sg_pairs += sg_pairs_list.copy()
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(start_repeat_loc) == 3 and (start_repeat_loc[1] - start_repeat_loc[0] < 24) or
                        (len(start_repeat_loc) == 2 and start_repeat_loc[1] - start_repeat_loc[0] < 24)):
                    sg_pairs = []
                    for _ in range(list_size):
                        random.shuffle(sg_pairs_list)
                        sg_pairs += sg_pairs_list.copy()
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(start_repeat_loc) == 3 and (start_repeat_loc[2] - start_repeat_loc[1] < 24):
                    sg_pairs = []
                    for _ in range(list_size):
                        random.shuffle(sg_pairs_list)
                        sg_pairs += sg_pairs_list.copy()
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
            return sg_pairs

        def generate_sg_discrimination_4(list_size):
            sg_pairs_list = [(i, (j + i) % 4, j) for i in range(4) for j in range(4)]
            start_repeat_limit = 3
            goal_repeat_limit = 3
            route_repeat_limit = 3
            start_threepeat = 0
            goal_threepeat = 0
            route_threepeat = 0
            start_fourpeat = 0
            goal_fourpeat = 0
            route_fourpeat = 0
            route_repeat_loc = []
            goal_repeat_loc = []
            start_repeat_loc = []
            sg_pairs = []
            passed = False
            fails = 0

            while not passed:
                passed = True
                sg_pairs.clear()
                for _ in range(list_size):
                    random.shuffle(sg_pairs_list)
                    sg_pairs += sg_pairs_list.copy()
                for i, sgp in enumerate(sg_pairs[0:-3]):
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2] and sgp[2] == sg_pairs[i + 3][2]:
                        route_fourpeat += 1
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1] and sgp[1] == sg_pairs[i + 3][1]:
                        goal_fourpeat += 1
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0] and sgp[0] == sg_pairs[i + 3][0]:
                        start_fourpeat += 1
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2]:
                        route_threepeat += 1
                        route_repeat_loc.append(i)
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1]:
                        goal_threepeat += 1
                        goal_repeat_loc.append(i)
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0]:
                        start_threepeat += 1
                        start_repeat_loc.append(i)
                # Catch four repeats or over threepeat limit
                if (route_fourpeat > 0 or goal_fourpeat > 0 or start_fourpeat > 0 or
                        route_threepeat > route_repeat_limit or
                        goal_threepeat > goal_repeat_limit or
                        start_threepeat > start_repeat_limit):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(route_repeat_loc) == 3 and (route_repeat_loc[1] - route_repeat_loc[0] < 16) or
                        (len(route_repeat_loc) == 2 and route_repeat_loc[1] - route_repeat_loc[0] < 16)):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(route_repeat_loc) == 3 and (route_repeat_loc[2] - route_repeat_loc[1] < 16):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(goal_repeat_loc) == 3 and (goal_repeat_loc[1] - goal_repeat_loc[0] < 16) or
                        (len(goal_repeat_loc) == 2 and goal_repeat_loc[1] - goal_repeat_loc[0] < 16)):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(goal_repeat_loc) == 3 and (goal_repeat_loc[2] - goal_repeat_loc[1] < 16):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(start_repeat_loc) == 3 and (start_repeat_loc[1] - start_repeat_loc[0] < 16) or
                        (len(start_repeat_loc) == 2 and start_repeat_loc[1] - start_repeat_loc[0] < 16)):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(start_repeat_loc) == 3 and (start_repeat_loc[2] - start_repeat_loc[1] < 16):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
            return sg_pairs

        def generate_sg_discrimination_cue_delay(list_size):
            sg_pairs_list_on = [(i, (j + i) % 4, j, 1) for i in range(4) for j in range(4)]
            sg_pairs_list_off = [(i, (j + i) % 4, j, 0) for i in range(4) for j in range(4)]
            sg_pairs_list = sg_pairs_list_on + sg_pairs_list_off
            start_repeat_limit = 4
            goal_repeat_limit = 4
            route_repeat_limit = 4
            cue_on_repeat_limit = 4
            cue_off_repeat_limit = 4
            start_threepeat = 0
            goal_threepeat = 0
            route_threepeat = 0
            cue_on_threepeat = 0
            cue_off_threepeat = 0
            start_fourpeat = 0
            goal_fourpeat = 0
            route_fourpeat = 0
            cue_on_fourpeat = 0
            cue_off_fourpeat = 0
            route_repeat_loc = []
            goal_repeat_loc = []
            start_repeat_loc = []
            cue_on_repeat_loc = []
            cue_off_repeat_loc = []
            sg_pairs = []
            passed = False
            fails = 0

            while not passed:
                passed = True
                sg_pairs.clear()
                for _ in range(list_size):
                    random.shuffle(sg_pairs_list)
                    sg_pairs += sg_pairs_list
                for i, sgp in enumerate(sg_pairs[0:-3]):
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2] and sgp[2] == sg_pairs[i + 3][2]:
                        route_fourpeat += 1
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1] and sgp[1] == sg_pairs[i + 3][1]:
                        goal_fourpeat += 1
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0] and sgp[0] == sg_pairs[i + 3][0]:
                        start_fourpeat += 1
                    if sgp[3] == 1 and sg_pairs[i + 1][3] == 1 and sg_pairs[i + 2][3] == 1 and sg_pairs[i + 3][3] == 1:
                        cue_on_fourpeat += 1
                    if sgp[3] == 0 and sg_pairs[i + 1][3] == 0 and sg_pairs[i + 2][3] == 0 and sg_pairs[i + 3][3] == 0:
                        cue_off_fourpeat += 1
                    if sgp[3] == 1 and sg_pairs[i + 1][3] == 1 and sg_pairs[i + 2][3] == 1:
                        cue_on_threepeat += 1
                        cue_on_repeat_loc.append(i)
                    if sgp[3] == 0 and sg_pairs[i + 1][3] == 0 and sg_pairs[i + 2][3] == 0:
                        cue_off_threepeat += 1
                        cue_off_repeat_loc.append(i)
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2]:
                        route_threepeat += 1
                        route_repeat_loc.append(i)
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1]:
                        goal_threepeat += 1
                        goal_repeat_loc.append(i)
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0]:
                        start_threepeat += 1
                        start_repeat_loc.append(i)
                # Catch four repeats or over threepeat limit

                if (route_fourpeat > 0 or goal_fourpeat > 0 or start_fourpeat > 0 or
                        cue_on_fourpeat > 0 or cue_off_fourpeat > 0 or
                        route_threepeat > route_repeat_limit or
                        goal_threepeat > goal_repeat_limit or
                        start_threepeat > start_repeat_limit or
                        cue_on_threepeat > cue_on_repeat_limit or
                        cue_off_threepeat > cue_off_repeat_limit):
                    cue_on_threepeat = 0
                    cue_off_threepeat = 0
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    cue_on_fourpeat = 0
                    cue_off_fourpeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    cue_on_repeat_loc = []
                    cue_off_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if len(route_repeat_loc) == 3 and (route_repeat_loc[1] - route_repeat_loc[0] < 32):
                    cue_on_threepeat = 0
                    cue_off_threepeat = 0
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    cue_on_fourpeat = 0
                    cue_off_fourpeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    cue_on_repeat_loc = []
                    cue_off_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(route_repeat_loc) == 3 and (route_repeat_loc[2] - route_repeat_loc[1] < 32):
                    cue_on_threepeat = 0
                    cue_off_threepeat = 0
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    cue_on_fourpeat = 0
                    cue_off_fourpeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    cue_on_repeat_loc = []
                    cue_off_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch goal threepeats that are too close together for first occurance
                if len(goal_repeat_loc) == 3 and (goal_repeat_loc[1] - goal_repeat_loc[0] < 32):
                    cue_on_threepeat = 0
                    cue_off_threepeat = 0
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    cue_on_fourpeat = 0
                    cue_off_fourpeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    cue_on_repeat_loc = []
                    cue_off_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(goal_repeat_loc) == 3 and (goal_repeat_loc[2] - goal_repeat_loc[1] < 32):
                    cue_on_threepeat = 0
                    cue_off_threepeat = 0
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    cue_on_fourpeat = 0
                    cue_off_fourpeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    cue_on_repeat_loc = []
                    cue_off_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch start threepeats that are too close together for first occurance
                if len(start_repeat_loc) == 3 and (start_repeat_loc[1] - start_repeat_loc[0] < 32):
                    cue_on_threepeat = 0
                    cue_off_threepeat = 0
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    cue_on_fourpeat = 0
                    cue_off_fourpeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    cue_on_repeat_loc = []
                    cue_off_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(start_repeat_loc) == 3 and (start_repeat_loc[2] - start_repeat_loc[1] < 32):
                    cue_on_threepeat = 0
                    cue_off_threepeat = 0
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    cue_on_fourpeat = 0
                    cue_off_fourpeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    cue_on_repeat_loc = []
                    cue_off_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                # Catch cue threepeats that are too close together for first occurance
                if len(cue_on_repeat_loc) == 3 and (cue_on_repeat_loc[1] - cue_on_repeat_loc[0] < 32):
                    cue_on_threepeat = 0
                    cue_off_threepeat = 0
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    cue_on_fourpeat = 0
                    cue_off_fourpeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    cue_on_repeat_loc = []
                    cue_off_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(cue_on_repeat_loc) == 3 and (cue_on_repeat_loc[2] - cue_on_repeat_loc[1] < 32):
                    cue_on_threepeat = 0
                    cue_off_threepeat = 0
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    cue_on_fourpeat = 0
                    cue_off_fourpeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    cue_on_repeat_loc = []
                    cue_off_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(cue_off_repeat_loc) == 3 and (cue_off_repeat_loc[1] - cue_off_repeat_loc[0] < 32):
                    cue_on_threepeat = 0
                    cue_off_threepeat = 0
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    cue_on_fourpeat = 0
                    cue_off_fourpeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    cue_on_repeat_loc = []
                    cue_off_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(cue_off_repeat_loc) == 3 and (cue_off_repeat_loc[2] - cue_off_repeat_loc[1] < 32):
                    cue_on_threepeat = 0
                    cue_off_threepeat = 0
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    cue_on_fourpeat = 0
                    cue_off_fourpeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    cue_on_repeat_loc = []
                    cue_off_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
            return sg_pairs

        def generate_sg_discrimination_all_cue_delay(list_size):
            sg_pairs_list_off = [(i, (j + i) % 4, j, 0) for i in range(4) for j in range(4)]
            sg_pairs_list = sg_pairs_list_off
            start_repeat_limit = 3
            goal_repeat_limit = 3
            route_repeat_limit = 3
            start_threepeat = 0
            goal_threepeat = 0
            route_threepeat = 0
            start_fourpeat = 0
            goal_fourpeat = 0
            route_fourpeat = 0
            route_repeat_loc = []
            goal_repeat_loc = []
            start_repeat_loc = []
            sg_pairs = []
            passed = False
            fails = 0

            while not passed:
                passed = True
                sg_pairs.clear()
                for _ in range(list_size):
                    random.shuffle(sg_pairs_list)
                    sg_pairs += sg_pairs_list
                for i, sgp in enumerate(sg_pairs[0:-3]):
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2] and sgp[2] == sg_pairs[i + 3][2]:
                        route_fourpeat += 1
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1] and sgp[1] == sg_pairs[i + 3][1]:
                        goal_fourpeat += 1
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0] and sgp[0] == sg_pairs[i + 3][0]:
                        start_fourpeat += 1
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2]:
                        route_threepeat += 1
                        route_repeat_loc.append(i)
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1]:
                        goal_threepeat += 1
                        goal_repeat_loc.append(i)
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0]:
                        start_threepeat += 1
                        start_repeat_loc.append(i)
                # Catch four repeats or over threepeat limit

                if (route_fourpeat > 0 or goal_fourpeat > 0 or start_fourpeat > 0 or
                        route_threepeat > route_repeat_limit or
                        goal_threepeat > goal_repeat_limit or
                        start_threepeat > start_repeat_limit):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if len(route_repeat_loc) == 2 and (route_repeat_loc[1] - route_repeat_loc[0] < 24):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(route_repeat_loc) == 3 and (route_repeat_loc[2] - route_repeat_loc[1] < 24):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch goal threepeats that are too close together for first occurance
                if len(goal_repeat_loc) == 2 and (goal_repeat_loc[1] - goal_repeat_loc[0] < 24):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(goal_repeat_loc) == 3 and (goal_repeat_loc[2] - goal_repeat_loc[1] < 24):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch start threepeats that are too close together for first occurance
                if len(start_repeat_loc) == 2 and (start_repeat_loc[1] - start_repeat_loc[0] < 24):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(start_repeat_loc) == 3 and (start_repeat_loc[2] - start_repeat_loc[1] < 24):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

            return sg_pairs

        def generate_sg_discrimination_split_cue_delay(list_size):
            sg_pairs_list_on = [(i, (j + i) % 4, j, 1) for i in range(4) for j in range(4)]
            sg_pairs_list_off = [(i, (j + i) % 4, j, 0) for i in range(4) for j in range(4)]
            start_repeat_limit = 4
            goal_repeat_limit = 4
            route_repeat_limit = 4
            start_threepeat = 0
            goal_threepeat = 0
            route_threepeat = 0
            start_fourpeat = 0
            goal_fourpeat = 0
            route_fourpeat = 0
            route_repeat_loc = []
            goal_repeat_loc = []
            start_repeat_loc = []
            sg_pairs = []
            passed = False
            fails = 0

            while not passed:
                passed = True
                sg_pairs.clear()
                for i in range(list_size):
                    if i < 2:
                        sg_pairs_temp = sg_pairs_list_on.copy()
                        random.shuffle(sg_pairs_temp)
                    else:
                        sg_pairs_temp = sg_pairs_list_off.copy()
                        random.shuffle(sg_pairs_temp)
                    sg_pairs += sg_pairs_temp
                for i, sgp in enumerate(sg_pairs[0:-3]):
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2] and sgp[2] == sg_pairs[i + 3][2]:
                        route_fourpeat += 1
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1] and sgp[1] == sg_pairs[i + 3][1]:
                        goal_fourpeat += 1
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0] and sgp[0] == sg_pairs[i + 3][0]:
                        start_fourpeat += 1
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2]:
                        route_threepeat += 1
                        route_repeat_loc.append(i)
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1]:
                        goal_threepeat += 1
                        goal_repeat_loc.append(i)
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0]:
                        start_threepeat += 1
                        start_repeat_loc.append(i)
                # Catch four repeats or over threepeat limit

                if (route_fourpeat > 0 or goal_fourpeat > 0 or start_fourpeat > 0 or
                        route_threepeat > route_repeat_limit or
                        goal_threepeat > goal_repeat_limit or
                        start_threepeat > start_repeat_limit):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if len(route_repeat_loc) == 2 and (route_repeat_loc[1] - route_repeat_loc[0] < 24):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(route_repeat_loc) == 3 and (route_repeat_loc[2] - route_repeat_loc[1] < 24):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch goal threepeats that are too close together for first occurance
                if len(goal_repeat_loc) == 2 and (goal_repeat_loc[1] - goal_repeat_loc[0] < 24):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(goal_repeat_loc) == 3 and (goal_repeat_loc[2] - goal_repeat_loc[1] < 24):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch start threepeats that are too close together for first occurance
                if len(start_repeat_loc) == 2 and (start_repeat_loc[1] - start_repeat_loc[0] < 24):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(start_repeat_loc) == 3 and (start_repeat_loc[2] - start_repeat_loc[1] < 24):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

            return sg_pairs

        def generate_sg_differentiate_cue_delay_1a(list_size, ort):
            # Third index is tell if reward is to the right or to the left.
            print(ort)
            if ort == 'N/NE' or ort == 'N/SW':
                print('NE or SW')
                sg_pairs_list_on = [(i, (i + 1) % 4, 0, 1) for i in range(4)] + [(i, (i - 1) % 4, 1, 1) for i in
                                                                                 range(4)]
                sg_pairs_list_off = [(i, (i + 1) % 4, 0, 0) for i in range(4)] + [(i, (i - 1) % 4, 1, 0) for i in
                                                                                  range(4)]
            else:
                print('SE or NW')
                sg_pairs_list_on = [(i, i, 0, 1) for i in range(4)] + [(i, (i + 2) % 4, 1, 1) for i in range(4)]
                sg_pairs_list_off = [(i, i, 0, 0) for i in range(4)] + [(i, (i + 2) % 4, 1, 0) for i in range(4)]

            start_repeat_limit = 3
            goal_repeat_limit = 3
            route_repeat_limit = 3
            start_threepeat = 0
            goal_threepeat = 0
            route_threepeat = 0
            start_fourpeat = 0
            goal_fourpeat = 0
            route_fourpeat = 0
            route_repeat_loc = []
            goal_repeat_loc = []
            start_repeat_loc = []
            sg_pairs = []
            passed = False
            fails = 0

            while not passed:
                passed = True
                sg_pairs.clear()
                for i in range(list_size):
                    if i < 1:
                        random.shuffle(sg_pairs_list_on)
                        sg_pairs += sg_pairs_list_on.copy()
                    else:
                        random.shuffle(sg_pairs_list_off)
                        sg_pairs += sg_pairs_list_off.copy()

                for i, sgp in enumerate(sg_pairs[0:-3]):
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2] and sgp[2] == sg_pairs[i + 3][2]:
                        route_fourpeat += 1
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1] and sgp[1] == sg_pairs[i + 3][1]:
                        goal_fourpeat += 1
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0] and sgp[0] == sg_pairs[i + 3][0]:
                        start_fourpeat += 1
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2]:
                        route_threepeat += 1
                        route_repeat_loc.append(i)
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1]:
                        goal_threepeat += 1
                        goal_repeat_loc.append(i)
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0]:
                        start_threepeat += 1
                        start_repeat_loc.append(i)
                # Catch four repeats or over threepeat limit
                if (route_fourpeat > 0 or goal_fourpeat > 0 or start_fourpeat > 0 or
                        route_threepeat > route_repeat_limit or
                        goal_threepeat > goal_repeat_limit or
                        start_threepeat > start_repeat_limit):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(route_repeat_loc) == 3 and (route_repeat_loc[1] - route_repeat_loc[0] < 16) or
                        (len(route_repeat_loc) == 2 and route_repeat_loc[1] - route_repeat_loc[0] < 16)):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(route_repeat_loc) == 3 and (route_repeat_loc[2] - route_repeat_loc[1] < 16):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(goal_repeat_loc) == 3 and (goal_repeat_loc[1] - goal_repeat_loc[0] < 16) or
                        (len(goal_repeat_loc) == 2 and goal_repeat_loc[1] - goal_repeat_loc[0] < 16)):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(goal_repeat_loc) == 3 and (goal_repeat_loc[2] - goal_repeat_loc[1] < 16):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(start_repeat_loc) == 3 and (start_repeat_loc[1] - start_repeat_loc[0] < 16) or
                        (len(start_repeat_loc) == 2 and start_repeat_loc[1] - start_repeat_loc[0] < 16)):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(start_repeat_loc) == 3 and (start_repeat_loc[2] - start_repeat_loc[1] < 16):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
            return sg_pairs

        def generate_sg_differentiate_cue_delay_1b(list_size, ort):
            # Third index is tell if reward is to the right or to the left.
            print(ort)
            if ort == 'N/NE' or ort == 'N/SW':
                print('NE or SW')
                sg_pairs_list_on = [(i, (i + 1) % 4, 0, 1) for i in range(4)] + [(i, (i - 1) % 4, 1, 1) for i in
                                                                                 range(4)]
                sg_pairs_list_off = [(i, (i + 1) % 4, 0, 0) for i in range(4)] + [(i, (i - 1) % 4, 1, 0) for i in
                                                                                  range(4)]
                sg_pairs_list = sg_pairs_list_on + sg_pairs_list_off
            else:
                print('SE or NW')
                sg_pairs_list_on = [(i, i, 0, 1) for i in range(4)] + [(i, (i + 2) % 4, 1, 1) for i in range(4)]
                sg_pairs_list_off = [(i, i, 0, 0) for i in range(4)] + [(i, (i + 2) % 4, 1, 0) for i in range(4)]
                sg_pairs_list = sg_pairs_list_on + sg_pairs_list_off

            start_repeat_limit = 4
            goal_repeat_limit = 4
            route_repeat_limit = 4
            cue_on_repeat_limit = 4
            cue_off_repeat_limit = 4
            start_threepeat = 0
            goal_threepeat = 0
            route_threepeat = 0
            cue_on_threepeat = 0
            cue_off_threepeat = 0
            start_fourpeat = 0
            goal_fourpeat = 0
            route_fourpeat = 0
            cue_on_fourpeat = 0
            cue_off_fourpeat = 0
            route_repeat_loc = []
            goal_repeat_loc = []
            start_repeat_loc = []
            cue_on_repeat_loc = []
            cue_off_repeat_loc = []
            sg_pairs = []
            passed = False
            fails = 0
            while not passed:
                passed = True
                sg_pairs.clear()
                for _ in range(list_size):
                    random.shuffle(sg_pairs_list)
                    sg_pairs += sg_pairs_list
                for i, sgp in enumerate(sg_pairs[0:-3]):
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2] and sgp[2] == sg_pairs[i + 3][2]:
                        route_fourpeat += 1
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1] and sgp[1] == sg_pairs[i + 3][1]:
                        goal_fourpeat += 1
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0] and sgp[0] == sg_pairs[i + 3][0]:
                        start_fourpeat += 1
                    if sgp[3] == 1 and sg_pairs[i + 1][3] == 1 and sg_pairs[i + 2][3] == 1 and sg_pairs[i + 3][3] == 1:
                        cue_on_fourpeat += 1
                    if sgp[3] == 0 and sg_pairs[i + 1][3] == 0 and sg_pairs[i + 2][3] == 0 and sg_pairs[i + 3][3] == 0:
                        cue_off_fourpeat += 1
                    if sgp[3] == 1 and sg_pairs[i + 1][3] == 1 and sg_pairs[i + 2][3] == 1:
                        cue_on_threepeat += 1
                        cue_on_repeat_loc.append(i)
                    if sgp[3] == 0 and sg_pairs[i + 1][3] == 0 and sg_pairs[i + 2][3] == 0:
                        cue_off_threepeat += 1
                        cue_off_repeat_loc.append(i)
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2]:
                        route_threepeat += 1
                        route_repeat_loc.append(i)
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1]:
                        goal_threepeat += 1
                        goal_repeat_loc.append(i)
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0]:
                        start_threepeat += 1
                        start_repeat_loc.append(i)
                # Catch four repeats or over threepeat limit

                if (route_fourpeat > 0 or goal_fourpeat > 0 or start_fourpeat > 0 or
                        cue_on_fourpeat > 0 or cue_off_fourpeat > 0 or
                        route_threepeat > route_repeat_limit or
                        goal_threepeat > goal_repeat_limit or
                        start_threepeat > start_repeat_limit or
                        cue_on_threepeat > cue_on_repeat_limit or
                        cue_off_threepeat > cue_off_repeat_limit):
                    cue_on_threepeat = 0
                    cue_off_threepeat = 0
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    cue_on_fourpeat = 0
                    cue_off_fourpeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    cue_on_repeat_loc = []
                    cue_off_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if len(route_repeat_loc) == 3 and (route_repeat_loc[1] - route_repeat_loc[0] < 32):
                    cue_on_threepeat = 0
                    cue_off_threepeat = 0
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    cue_on_fourpeat = 0
                    cue_off_fourpeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    cue_on_repeat_loc = []
                    cue_off_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(route_repeat_loc) == 3 and (route_repeat_loc[2] - route_repeat_loc[1] < 32):
                    cue_on_threepeat = 0
                    cue_off_threepeat = 0
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    cue_on_fourpeat = 0
                    cue_off_fourpeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    cue_on_repeat_loc = []
                    cue_off_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch goal threepeats that are too close together for first occurance
                if len(goal_repeat_loc) == 3 and (goal_repeat_loc[1] - goal_repeat_loc[0] < 32):
                    cue_on_threepeat = 0
                    cue_off_threepeat = 0
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    cue_on_fourpeat = 0
                    cue_off_fourpeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    cue_on_repeat_loc = []
                    cue_off_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(goal_repeat_loc) == 3 and (goal_repeat_loc[2] - goal_repeat_loc[1] < 32):
                    cue_on_threepeat = 0
                    cue_off_threepeat = 0
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    cue_on_fourpeat = 0
                    cue_off_fourpeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    cue_on_repeat_loc = []
                    cue_off_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch start threepeats that are too close together for first occurance
                if len(start_repeat_loc) == 3 and (start_repeat_loc[1] - start_repeat_loc[0] < 32):
                    cue_on_threepeat = 0
                    cue_off_threepeat = 0
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    cue_on_fourpeat = 0
                    cue_off_fourpeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    cue_on_repeat_loc = []
                    cue_off_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(start_repeat_loc) == 3 and (start_repeat_loc[2] - start_repeat_loc[1] < 32):
                    cue_on_threepeat = 0
                    cue_off_threepeat = 0
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    cue_on_fourpeat = 0
                    cue_off_fourpeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    cue_on_repeat_loc = []
                    cue_off_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                # Catch cue threepeats that are too close together for first occurance
                if len(cue_on_repeat_loc) == 3 and (cue_on_repeat_loc[1] - cue_on_repeat_loc[0] < 32):
                    cue_on_threepeat = 0
                    cue_off_threepeat = 0
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    cue_on_fourpeat = 0
                    cue_off_fourpeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    cue_on_repeat_loc = []
                    cue_off_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(cue_on_repeat_loc) == 3 and (cue_on_repeat_loc[2] - cue_on_repeat_loc[1] < 32):
                    cue_on_threepeat = 0
                    cue_off_threepeat = 0
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    cue_on_fourpeat = 0
                    cue_off_fourpeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    cue_on_repeat_loc = []
                    cue_off_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(cue_off_repeat_loc) == 3 and (cue_off_repeat_loc[1] - cue_off_repeat_loc[0] < 32):
                    cue_on_threepeat = 0
                    cue_off_threepeat = 0
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    cue_on_fourpeat = 0
                    cue_off_fourpeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    cue_on_repeat_loc = []
                    cue_off_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(cue_off_repeat_loc) == 3 and (cue_off_repeat_loc[2] - cue_off_repeat_loc[1] < 32):
                    cue_on_threepeat = 0
                    cue_off_threepeat = 0
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    cue_on_fourpeat = 0
                    cue_off_fourpeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    cue_on_repeat_loc = []
                    cue_off_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
            #
            # while not passed:
            #     passed = True
            #     sg_pairs.clear()
            #     for i in range(list_size):
            #         random.shuffle(sg_pairs_list)
            #         sg_pairs += sg_pairs_list_off.copy()
            #
            #     for i, sgp in enumerate(sg_pairs[0:-3]):
            #         if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2] and sgp[2] == sg_pairs[i + 3][2]:
            #             route_fourpeat += 1
            #         if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1] and sgp[1] == sg_pairs[i + 3][1]:
            #             goal_fourpeat += 1
            #         if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0] and sgp[0] == sg_pairs[i + 3][0]:
            #             start_fourpeat += 1
            #         if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2]:
            #             route_threepeat += 1
            #             route_repeat_loc.append(i)
            #         if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1]:
            #             goal_threepeat += 1
            #             goal_repeat_loc.append(i)
            #         if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0]:
            #             start_threepeat += 1
            #             start_repeat_loc.append(i)
            #     # Catch four repeats or over threepeat limit
            #     if (route_fourpeat > 0 or goal_fourpeat > 0 or start_fourpeat > 0 or
            #             route_threepeat > route_repeat_limit or
            #             goal_threepeat > goal_repeat_limit or
            #             start_threepeat > start_repeat_limit):
            #         start_threepeat = 0
            #         goal_threepeat = 0
            #         route_threepeat = 0
            #         cue_on_threepeat = 0
            #         cue_off_threepeat = 0
            #         start_fourpeat = 0
            #         goal_fourpeat = 0
            #         route_fourpeat = 0
            #         cue_on_fourpeat = 0
            #         cue_off_fourpeat = 0
            #         route_repeat_loc = []
            #         goal_repeat_loc = []
            #         start_repeat_loc = []
            #         cue_on_repeat_loc = []
            #         cue_off_repeat_loc = []
            #         sg_pairs = []
            #         fails += 1
            #         passed = False
            #         continue
            #
            #     # Catch route threepeats that are too close together for first occurance
            #     if (len(route_repeat_loc) == 3 and (route_repeat_loc[1] - route_repeat_loc[0] < 32) or
            #             (len(route_repeat_loc) == 2 and route_repeat_loc[1] - route_repeat_loc[0] < 32)):
            #         start_threepeat = 0
            #         goal_threepeat = 0
            #         route_threepeat = 0
            #         cue_on_threepeat = 0
            #         cue_off_threepeat = 0
            #         start_fourpeat = 0
            #         goal_fourpeat = 0
            #         route_fourpeat = 0
            #         cue_on_fourpeat = 0
            #         cue_off_fourpeat = 0
            #         route_repeat_loc = []
            #         goal_repeat_loc = []
            #         start_repeat_loc = []
            #         cue_on_repeat_loc = []
            #         cue_off_repeat_loc = []
            #         sg_pairs = []
            #         fails += 1
            #         passed = False
            #         continue
            #     if len(route_repeat_loc) == 3 and (route_repeat_loc[2] - route_repeat_loc[1] < 32):
            #         start_threepeat = 0
            #         goal_threepeat = 0
            #         route_threepeat = 0
            #         cue_on_threepeat = 0
            #         cue_off_threepeat = 0
            #         start_fourpeat = 0
            #         goal_fourpeat = 0
            #         route_fourpeat = 0
            #         cue_on_fourpeat = 0
            #         cue_off_fourpeat = 0
            #         route_repeat_loc = []
            #         goal_repeat_loc = []
            #         start_repeat_loc = []
            #         cue_on_repeat_loc = []
            #         cue_off_repeat_loc = []
            #         sg_pairs = []
            #         fails += 1
            #         passed = False
            #         continue
            #
            #     # Catch route threepeats that are too close together for first occurance
            #     if (len(goal_repeat_loc) == 3 and (goal_repeat_loc[1] - goal_repeat_loc[0] < 32) or
            #             (len(goal_repeat_loc) == 2 and goal_repeat_loc[1] - goal_repeat_loc[0] < 32)):
            #         start_threepeat = 0
            #         goal_threepeat = 0
            #         route_threepeat = 0
            #         cue_on_threepeat = 0
            #         cue_off_threepeat = 0
            #         start_fourpeat = 0
            #         goal_fourpeat = 0
            #         route_fourpeat = 0
            #         cue_on_fourpeat = 0
            #         cue_off_fourpeat = 0
            #         route_repeat_loc = []
            #         goal_repeat_loc = []
            #         start_repeat_loc = []
            #         cue_on_repeat_loc = []
            #         cue_off_repeat_loc = []
            #         sg_pairs = []
            #         fails += 1
            #         passed = False
            #         continue
            #     if len(goal_repeat_loc) == 3 and (goal_repeat_loc[2] - goal_repeat_loc[1] < 32):
            #         start_threepeat = 0
            #         goal_threepeat = 0
            #         route_threepeat = 0
            #         cue_on_threepeat = 0
            #         cue_off_threepeat = 0
            #         start_fourpeat = 0
            #         goal_fourpeat = 0
            #         route_fourpeat = 0
            #         cue_on_fourpeat = 0
            #         cue_off_fourpeat = 0
            #         route_repeat_loc = []
            #         goal_repeat_loc = []
            #         start_repeat_loc = []
            #         cue_on_repeat_loc = []
            #         cue_off_repeat_loc = []
            #         sg_pairs = []
            #         fails += 1
            #         passed = False
            #         continue
            #
            #     # Catch route threepeats that are too close together for first occurance
            #     if (len(start_repeat_loc) == 3 and (start_repeat_loc[1] - start_repeat_loc[0] < 32) or
            #             (len(start_repeat_loc) == 2 and start_repeat_loc[1] - start_repeat_loc[0] < 32)):
            #         start_threepeat = 0
            #         goal_threepeat = 0
            #         route_threepeat = 0
            #         cue_on_threepeat = 0
            #         cue_off_threepeat = 0
            #         start_fourpeat = 0
            #         goal_fourpeat = 0
            #         route_fourpeat = 0
            #         cue_on_fourpeat = 0
            #         cue_off_fourpeat = 0
            #         route_repeat_loc = []
            #         goal_repeat_loc = []
            #         start_repeat_loc = []
            #         cue_on_repeat_loc = []
            #         cue_off_repeat_loc = []
            #         sg_pairs = []
            #         fails += 1
            #         passed = False
            #         continue
            #     if len(start_repeat_loc) == 3 and (start_repeat_loc[2] - start_repeat_loc[1] < 32):
            #         start_threepeat = 0
            #         goal_threepeat = 0
            #         route_threepeat = 0
            #         cue_on_threepeat = 0
            #         cue_off_threepeat = 0
            #         start_fourpeat = 0
            #         goal_fourpeat = 0
            #         route_fourpeat = 0
            #         cue_on_fourpeat = 0
            #         cue_off_fourpeat = 0
            #         route_repeat_loc = []
            #         goal_repeat_loc = []
            #         start_repeat_loc = []
            #         cue_on_repeat_loc = []
            #         cue_off_repeat_loc = []
            #         sg_pairs = []
            #         fails += 1
            #         passed = False
            #         continue
            #
            #     # Catch cue threepeats that are too close together for first occurance
            #     if len(cue_on_repeat_loc) == 3 and (cue_on_repeat_loc[1] - cue_on_repeat_loc[0] < 32):
            #         start_threepeat = 0
            #         goal_threepeat = 0
            #         route_threepeat = 0
            #         cue_on_threepeat = 0
            #         cue_off_threepeat = 0
            #         start_fourpeat = 0
            #         goal_fourpeat = 0
            #         route_fourpeat = 0
            #         cue_on_fourpeat = 0
            #         cue_off_fourpeat = 0
            #         route_repeat_loc = []
            #         goal_repeat_loc = []
            #         start_repeat_loc = []
            #         cue_on_repeat_loc = []
            #         cue_off_repeat_loc = []
            #         sg_pairs = []
            #         fails += 1
            #         passed = False
            #         continue
            #     if len(cue_on_repeat_loc) == 3 and (cue_on_repeat_loc[2] - cue_on_repeat_loc[1] < 32):
            #         start_threepeat = 0
            #         goal_threepeat = 0
            #         route_threepeat = 0
            #         cue_on_threepeat = 0
            #         cue_off_threepeat = 0
            #         start_fourpeat = 0
            #         goal_fourpeat = 0
            #         route_fourpeat = 0
            #         cue_on_fourpeat = 0
            #         cue_off_fourpeat = 0
            #         route_repeat_loc = []
            #         goal_repeat_loc = []
            #         start_repeat_loc = []
            #         cue_on_repeat_loc = []
            #         cue_off_repeat_loc = []
            #         sg_pairs = []
            #         fails += 1
            #         passed = False
            #         continue
            #     if len(cue_off_repeat_loc) == 3 and (cue_off_repeat_loc[1] - cue_off_repeat_loc[0] < 32):
            #         start_threepeat = 0
            #         goal_threepeat = 0
            #         route_threepeat = 0
            #         cue_on_threepeat = 0
            #         cue_off_threepeat = 0
            #         start_fourpeat = 0
            #         goal_fourpeat = 0
            #         route_fourpeat = 0
            #         cue_on_fourpeat = 0
            #         cue_off_fourpeat = 0
            #         route_repeat_loc = []
            #         goal_repeat_loc = []
            #         start_repeat_loc = []
            #         cue_on_repeat_loc = []
            #         cue_off_repeat_loc = []
            #         sg_pairs = []
            #         fails += 1
            #         passed = False
            #         continue
            #     if len(cue_off_repeat_loc) == 3 and (cue_off_repeat_loc[2] - cue_off_repeat_loc[1] < 32):
            #         start_threepeat = 0
            #         goal_threepeat = 0
            #         route_threepeat = 0
            #         cue_on_threepeat = 0
            #         cue_off_threepeat = 0
            #         start_fourpeat = 0
            #         goal_fourpeat = 0
            #         route_fourpeat = 0
            #         cue_on_fourpeat = 0
            #         cue_off_fourpeat = 0
            #         route_repeat_loc = []
            #         goal_repeat_loc = []
            #         start_repeat_loc = []
            #         cue_on_repeat_loc = []
            #         cue_off_repeat_loc = []
            #         sg_pairs = []
            #         fails += 1
            #         passed = False
            #         continue
            return sg_pairs

        def generate_sg_predetour(ort, goal):
            if goal == 'Northeast':
                goal_loc = 0
            elif goal == 'Southeast':
                goal_loc = 1
            elif goal == 'Southwest':
                goal_loc = 2
            elif goal == 'Northwest':
                goal_loc = 3

            if ort == 'N/NE':
                sg_pairs_list = [((goal_loc + 1) % 4, goal_loc, 1), ((goal_loc - 1) % 4, goal_loc, 3)]
            elif ort == 'N/SE':
                sg_pairs_list = [(goal_loc, goal_loc, 0), ((goal_loc + 2) % 4, goal_loc, 2)]
            elif ort == 'N/SW':
                sg_pairs_list = [((goal_loc - 1) % 4, goal_loc, 3), ((goal_loc + 1) % 4, goal_loc, 1)]
            elif ort == 'N/NW':
                sg_pairs_list = [((goal_loc + 2) % 4, goal_loc, 2), (goal_loc, goal_loc, 0)]

            random.shuffle(sg_pairs_list)

            return sg_pairs_list

        def generate_sg_fixed_cue_1(list_size, ort):
            index_size = list_size*8
            print(index_size)
            # NE:0, SE:1, SW:2, NW:3
            goal_loc = random.randint(0, 3)
            # LL:0, RR:1, RL:2, LR:3
            if ort == 'N/NE':
                sg_pairs_list = [((goal_loc + 1) % 4, goal_loc, 1), ((goal_loc - 1) % 4, goal_loc, 3)]
            elif ort == 'N/SE':
                sg_pairs_list = [(goal_loc, goal_loc, 0), ((goal_loc + 2) % 4, goal_loc, 2)]
            elif ort == 'N/SW':
                sg_pairs_list = [((goal_loc - 1) % 4, goal_loc, 3), ((goal_loc + 1) % 4, goal_loc, 1)]
            elif ort == 'N/NW':
                sg_pairs_list = [((goal_loc + 2) % 4, goal_loc, 2), (goal_loc, goal_loc, 0)]
            sg_pairs_temp = sg_pairs_list * 4

            start_repeat_limit = 2
            start_threepeat = 0
            start_fourpeat = 0
            start_repeat_loc = []
            sg_pairs = []
            passed = False
            fails = 0
            while not passed:
                passed = True
                sg_pairs.clear()
                for _ in range(list_size):
                    random.shuffle(sg_pairs_temp)
                    sg_pairs += sg_pairs_temp.copy()
                for i, sgp in enumerate(sg_pairs[0:-3]):
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0] and sgp[0] == sg_pairs[i + 3][0]:
                        start_fourpeat += 1
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0]:
                        start_threepeat += 1
                        start_repeat_loc.append(i)
                    if i == index_size - 4 and sg_pairs[i + 1][0] == sg_pairs[i + 2][0] and sg_pairs[i + 1][0] == \
                            sg_pairs[i + 3][0]:
                        start_threepeat += 1
                        start_repeat_loc.append(i)
                # Catch four repeats or over threepeat limit
                if (start_fourpeat > 0 or start_threepeat > start_repeat_limit):
                    start_threepeat = 0
                    start_fourpeat = 0
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(start_repeat_loc) == 3 and ((start_repeat_loc[1] - start_repeat_loc[0]) < 16) or
                        (len(start_repeat_loc) == 2 and ((start_repeat_loc[1] - start_repeat_loc[0]) < 16))):
                    start_threepeat = 0
                    start_fourpeat = 0
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(start_repeat_loc) == 3 and (start_repeat_loc[2] - start_repeat_loc[1] < 16):
                    start_threepeat = 0
                    start_fourpeat = 0
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
            print('fails: ', fails)
            print('Repeat loc: ', start_repeat_loc)
            return sg_pairs

        def generate_sg_fixed_cue_2a(list_size, ort):
            index_size = 16 + (list_size - 1) * 6
            # print(index_size)
            # NE:0, SE:1, SW:2, NW:3
            goal_loc = random.randint(0, 3)

            # LL:0, RR:1, RL:2, LR:3
            if ort == 'N/NE':
                sg_pairs_list = [((goal_loc + 1) % 4, goal_loc, 1), ((goal_loc - 1) % 4, goal_loc, 3)]
            elif ort == 'N/SE':
                sg_pairs_list = [(goal_loc, goal_loc, 0), ((goal_loc + 2) % 4, goal_loc, 2)]
            elif ort == 'N/SW':
                sg_pairs_list = [((goal_loc - 1) % 4, goal_loc, 3), ((goal_loc + 1) % 4, goal_loc, 1)]
            elif ort == 'N/NW':
                sg_pairs_list = [((goal_loc + 2) % 4, goal_loc, 2), (goal_loc, goal_loc, 0)]
            sg_pairs_trained = sg_pairs_list * 8 # 16 trained trials to start
            sg_pairs_list = []

            # LL:0, RR:1, RL:2, LR:3
            if ort == 'N/NE':
                sg_pairs_list = [((goal_loc + 1) % 4, goal_loc, 1), ((goal_loc - 1) % 4, goal_loc, 3),
                                 ((goal_loc - 2) % 4, goal_loc, 2), ((goal_loc - 2) % 4, goal_loc, 2),
                                 ((goal_loc - 2) % 4, goal_loc, 2), ((goal_loc - 2) % 4, goal_loc, 2)]
            elif ort == 'N/SE':
                sg_pairs_list = [(goal_loc, goal_loc, 0), ((goal_loc + 2) % 4, goal_loc, 2),
                                 ((goal_loc + 1) % 4, goal_loc, 1), ((goal_loc + 1) % 4, goal_loc, 1),
                                 ((goal_loc + 1) % 4, goal_loc, 1), ((goal_loc + 1) % 4, goal_loc, 1)]
            elif ort == 'N/SW':
                sg_pairs_list = [((goal_loc - 1) % 4, goal_loc, 3), ((goal_loc + 1) % 4, goal_loc, 1),
                                 (goal_loc, goal_loc, 0), (goal_loc, goal_loc, 0),
                                 (goal_loc, goal_loc, 0), (goal_loc, goal_loc, 0)]
            elif ort == 'N/NW':
                sg_pairs_list = [((goal_loc + 2) % 4, goal_loc, 2), (goal_loc, goal_loc, 0),
                                 ((goal_loc - 1) % 4, goal_loc, 3), ((goal_loc - 1) % 4, goal_loc, 3),
                                 ((goal_loc - 1) % 4, goal_loc, 3), ((goal_loc - 1) % 4, goal_loc, 3)]
            sg_pairs_test = sg_pairs_list

            start_threepeat_limit = 0
            start_threepeat = 0
            start_fourpeat = 0
            start_repeat_loc = []
            sg_pairs = []
            temp_item = sg_pairs_test[-1]
            passed = False
            fails = 0
            while not passed:
                passed = True
                sg_pairs.clear()
                for i in range(list_size):
                    if i < 1:
                        random.shuffle(sg_pairs_trained)
                        sg_pairs += sg_pairs_trained.copy()
                    elif i == 1:
                        sg_pairs_test.remove(temp_item)
                        random.shuffle(sg_pairs_test)
                        sg_pairs += [temp_item] + sg_pairs_test.copy()
                        sg_pairs_test.append(temp_item)
                    else:
                        random.shuffle(sg_pairs_test)
                        if sg_pairs[-6:] == sg_pairs_test:
                            passed = False
                            continue
                        else:
                            sg_pairs += sg_pairs_test.copy()

                for i, sgp in enumerate(sg_pairs[0:-3]):
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0] and sgp[0] == sg_pairs[i + 3][0]:
                        start_fourpeat += 1
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0]:
                        start_threepeat += 1
                        start_repeat_loc.append(i)
                    if i == index_size - 4 and sg_pairs[i + 1][0] == sg_pairs[i + 2][0] and sg_pairs[i + 1][0] == sg_pairs[i + 3][0]:
                        start_threepeat += 1
                        start_repeat_loc.append(i)
                # Catch four repeats or over threepeat limit
                if (start_fourpeat > 0 or start_threepeat > start_threepeat_limit):
                    start_threepeat = 0
                    start_fourpeat = 0
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue


            print('fails: ', fails)
            print('threepeat: ', start_threepeat)
            print('threepeat loc: ', start_repeat_loc)
            return sg_pairs

        def generate_sg_fixed_cue_2b(list_size, ort):
            # NE:0, SE:1, SW:2, NW:3
            goal_loc = random.randint(0, 3)
            # LL:0, RR:1, RL:2, LR:3
            if ort == 'N/NE':
                sg_pairs_list = [((goal_loc + 1) % 4, goal_loc, 1), ((goal_loc - 1) % 4, goal_loc, 3),
                                 ((goal_loc - 2) % 4, goal_loc, 2)]
            elif ort == 'N/SE':
                sg_pairs_list = [(goal_loc, goal_loc, 0), ((goal_loc + 2) % 4, goal_loc, 2),
                                 ((goal_loc + 1) % 4, goal_loc, 1)]
            elif ort == 'N/SW':
                sg_pairs_list = [((goal_loc - 1) % 4, goal_loc, 3), ((goal_loc + 1) % 4, goal_loc, 1),
                                 (goal_loc, goal_loc, 0)]
            elif ort == 'N/NW':
                sg_pairs_list = [((goal_loc + 2) % 4, goal_loc, 2), (goal_loc, goal_loc, 0),
                                 ((goal_loc - 1) % 4, goal_loc, 3)]
            sg_pairs_temp = sg_pairs_list * 4

            start_repeat_limit = 3
            start_threepeat = 0
            start_fourpeat = 0
            start_repeat_loc = []
            sg_pairs = []
            passed = False
            fails = 0
            while not passed:
                passed = True
                sg_pairs.clear()
                for _ in range(list_size):
                    random.shuffle(sg_pairs_temp)
                    sg_pairs += sg_pairs_temp.copy()
                for i, sgp in enumerate(sg_pairs[0:-3]):
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0] and sgp[0] == sg_pairs[i + 3][0]:
                        start_fourpeat += 1
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0]:
                        start_threepeat += 1
                        start_repeat_loc.append(i)
                # Catch four repeats or over threepeat limit
                if (start_fourpeat > 0 or start_threepeat > start_repeat_limit):
                    start_threepeat = 0
                    start_fourpeat = 0
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(start_repeat_loc) == 3 and (start_repeat_loc[1] - start_repeat_loc[0] < 16) or
                        (len(start_repeat_loc) == 2 and start_repeat_loc[1] - start_repeat_loc[0] < 16)):
                    start_threepeat = 0
                    start_fourpeat = 0
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(start_repeat_loc) == 3 and (start_repeat_loc[2] - start_repeat_loc[1] < 16):
                    start_threepeat = 0
                    start_fourpeat = 0
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
            return sg_pairs

        def generate_sg_fixed_cue_3(list_size, ort):
            # NE:0, SE:1, SW:2, NW:3
            goal_loc = random.randint(0, 3)
            # LL:0, RR:1, RL:2, LR:3
            if goal_loc == 0:
                sg_pairs_list = [(0, goal_loc, 0), (1, goal_loc, 1), (2, goal_loc, 2), (3, goal_loc, 3)]
            elif goal_loc == 1:
                sg_pairs_list = [(0, goal_loc, 3), (1, goal_loc, 0), (2, goal_loc, 1), (3, goal_loc, 2)]
            elif goal_loc == 2:
                sg_pairs_list = [(0, goal_loc, 2), (1, goal_loc, 3), (2, goal_loc, 0), (3, goal_loc, 1)]
            elif goal_loc == 3:
                sg_pairs_list = [(0, goal_loc, 1), (1, goal_loc, 2), (2, goal_loc, 3), (3, goal_loc, 0)]

            sg_pairs_temp = sg_pairs_list * 4

            start_repeat_limit = 3
            start_threepeat = 0
            start_fourpeat = 0
            start_repeat_loc = []
            sg_pairs = []
            passed = False
            fails = 0
            while not passed:
                passed = True
                sg_pairs.clear()
                for _ in range(list_size):
                    random.shuffle(sg_pairs_temp)
                    sg_pairs += sg_pairs_temp.copy()
                for i, sgp in enumerate(sg_pairs[0:-3]):
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0] and sgp[0] == sg_pairs[i + 3][0]:
                        start_fourpeat += 1
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0]:
                        start_threepeat += 1
                        start_repeat_loc.append(i)
                # Catch four repeats or over threepeat limit
                if (start_fourpeat > 0 or start_threepeat > start_repeat_limit):
                    start_threepeat = 0
                    start_fourpeat = 0
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(start_repeat_loc) == 3 and (start_repeat_loc[1] - start_repeat_loc[0] < 16) or
                        (len(start_repeat_loc) == 2 and start_repeat_loc[1] - start_repeat_loc[0] < 16)):
                    start_threepeat = 0
                    start_fourpeat = 0
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(start_repeat_loc) == 3 and (start_repeat_loc[2] - start_repeat_loc[1] < 16):
                    start_threepeat = 0
                    start_fourpeat = 0
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
            return sg_pairs

        # This function just use the training from the first two routes and the a detour with the cue above the startarm
        def generate_sg_fixed_cue_3a(list_size, ort):
            # NE:0, SE:1, SW:2, NW:3
            goal_loc = random.randint(0, 3)
            # LL:0, RR:1, RL:2, LR:3
            if ort == 'N/NE':
                sg_pairs_temp = [((goal_loc + 1) % 4, goal_loc, 1), ((goal_loc - 1) % 4, goal_loc, 3)]
            elif ort == 'N/SE':
                sg_pairs_temp = [(goal_loc, goal_loc, 0), ((goal_loc + 2) % 4, goal_loc, 2)]
            elif ort == 'N/SW':
                sg_pairs_temp = [((goal_loc - 1) % 4, goal_loc, 3), ((goal_loc + 1) % 4, goal_loc, 1)]
            elif ort == 'N/NW':
                sg_pairs_temp = [((goal_loc + 2) % 4, goal_loc, 2), (goal_loc, goal_loc, 0)]
            sg_pairs_warmup = sg_pairs_temp*4
            if ort == 'N/NE':
                sg_pairs_detour = [((goal_loc + 1) % 4, goal_loc, 1), ((goal_loc - 1) % 4, goal_loc, 3),
                                   (goal_loc, goal_loc, 0), (goal_loc, goal_loc, 0),
                                   (goal_loc, goal_loc, 0), (goal_loc, goal_loc, 0)]
            elif ort == 'N/SE':
                sg_pairs_detour = [(goal_loc, goal_loc, 0), ((goal_loc + 2) % 4, goal_loc, 2),
                                   ((goal_loc - 1) % 4, goal_loc, 3), ((goal_loc - 1) % 4, goal_loc, 3),
                                   ((goal_loc - 1) % 4, goal_loc, 3), ((goal_loc - 1) % 4, goal_loc, 3)]
            elif ort == 'N/SW':
                sg_pairs_detour = [((goal_loc - 1) % 4, goal_loc, 3), ((goal_loc + 1) % 4, goal_loc, 1),
                                   ((goal_loc + 2) % 4, goal_loc, 2), ((goal_loc + 2) % 4, goal_loc, 2),
                                   ((goal_loc + 2) % 4, goal_loc, 2), ((goal_loc + 2) % 4, goal_loc, 2)]
            elif ort == 'N/NW':
                sg_pairs_detour = [((goal_loc + 2) % 4, goal_loc, 2), (goal_loc, goal_loc, 0),
                                   ((goal_loc + 1) % 4, goal_loc, 1), ((goal_loc + 1) % 4, goal_loc, 1),
                                   ((goal_loc + 1) % 4, goal_loc, 1), ((goal_loc + 1) % 4, goal_loc, 1)]

            start_repeat_limit = 3
            start_threepeat = 0
            start_fourpeat = 0
            start_repeat_loc = []
            sg_pairs = []
            passed = False
            fails = 0
            while not passed:
                passed = True
                sg_pairs.clear()
                # Create Full List
                for i in range(list_size):
                    if i < 2:
                        random.shuffle(sg_pairs_warmup)
                        sg_pairs += sg_pairs_warmup.copy()
                    elif i >= 2:
                        random.shuffle(sg_pairs_detour)
                        sg_pairs += sg_pairs_detour.copy()

                # Check list for unwanted repeats
                for i, sgp in enumerate(sg_pairs[0:-3]):
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0] and sgp[0] == sg_pairs[i + 3][0]:
                        start_fourpeat += 1
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0]:
                        start_threepeat += 1
                        start_repeat_loc.append(i)
                # Catch four repeats or over threepeat limit
                if (start_fourpeat > 0 or start_threepeat > start_repeat_limit):
                    start_threepeat = 0
                    start_fourpeat = 0
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(start_repeat_loc) == 3 and (start_repeat_loc[1] - start_repeat_loc[0] < 16) or
                        (len(start_repeat_loc) == 2 and start_repeat_loc[1] - start_repeat_loc[0] < 16)):
                    start_threepeat = 0
                    start_fourpeat = 0
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(start_repeat_loc) == 3 and (start_repeat_loc[2] - start_repeat_loc[1] < 16):
                    start_threepeat = 0
                    start_fourpeat = 0
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

            return sg_pairs

        def generate_sg_rotate_detour_1a(list_size, ort):
            if ort == 'N/NE' or ort == 'N/SW':
                #print('N/NE')
                sg_pairs_list_warmup = [(i, (i + 1) % 4, 0) for i in range(4)] + [(i, (i - 1) % 4, 2) for i in range(4)]
            else:
                #print('SE or NW')
                sg_pairs_list_warmup = [(i, i, 0) for i in range(4)] + [(i, (i + 2) % 4, 2) for i in range(4)]

            if ort == 'N/NW':
                # Third index: LL = 0, LR = 1, RL =2
                sg_pairs_list_test_detour = [(i, (j + i) % 4, j) for i in range(4) for j in [1]]
                sg_pairs_list_test_train = [(i, (j + i) % 4, j) for i in range(4) for j in [0,2]]
                random.shuffle(sg_pairs_list_test_train)
            elif ort == 'N/NE':
                # Third index:  LR= 0, RL = 1, RR =2
                sg_pairs_list_test_detour = [(i, (j + i + 1) % 4, j) for i in range(4) for j in [1]]
                sg_pairs_list_test_train = [(i, (j + i + 1) % 4, j) for i in range(4) for j in [0,2]]
                random.shuffle(sg_pairs_list_test_train)
            elif ort == 'N/SE':
                # Third index:  RL= 0, RR = 1, LL =2
                sg_pairs_list_test_detour = [(i, (j + i + 2) % 4, j) for i in range(4) for j in [1]]
                sg_pairs_list_test_train = [(i, (j + i + 2) % 4, j) for i in range(4) for j in [0,2]]
                random.shuffle(sg_pairs_list_test_train)
            elif ort == 'N/SW':
                # Third index:  RR= 0, LL = 1, LR =2
                sg_pairs_list_test_detour = [(i, (j + i + 3) % 4, j) for i in range(4) for j in [1]]
                sg_pairs_list_test_train = [(i, (j + i + 3) % 4, j) for i in range(4) for j in [0,2]]
                random.shuffle(sg_pairs_list_test_train)

            start_repeat_limit = 3
            goal_repeat_limit = 3
            route_repeat_limit = 3
            start_threepeat = 0
            goal_threepeat = 0
            route_threepeat = 0
            start_fourpeat = 0
            goal_fourpeat = 0
            route_fourpeat = 0
            route_repeat_loc = []
            goal_repeat_loc = []
            start_repeat_loc = []
            sg_pairs = []
            passed = False
            fails = 0
            while not passed:
                passed = True
                sg_pairs.clear()
                sg_pairs_list_test_train_cp = sg_pairs_list_test_train.copy()
                for i in range(list_size):
                    if i < 2:
                        random.shuffle(sg_pairs_list_warmup)
                        sg_pairs += sg_pairs_list_warmup.copy()
                    else:
                        sg_pairs_list_test = sg_pairs_list_test_detour + [sg_pairs_list_test_train_cp.pop(),
                                                                          sg_pairs_list_test_train_cp.pop()]
                        random.shuffle(sg_pairs_list_test)
                        sg_pairs += sg_pairs_list_test.copy()

                for i, sgp in enumerate(sg_pairs[0:-3]):
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2] and sgp[2] == sg_pairs[i + 3][2]:
                        route_fourpeat += 1
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1] and sgp[1] == sg_pairs[i + 3][1]:
                        goal_fourpeat += 1
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0] and sgp[0] == sg_pairs[i + 3][0]:
                        start_fourpeat += 1
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2]:
                        route_threepeat += 1
                        route_repeat_loc.append(i)
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1]:
                        goal_threepeat += 1
                        goal_repeat_loc.append(i)
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0]:
                        start_threepeat += 1
                        start_repeat_loc.append(i)
                # Catch four repeats or over threepeat limit
                if (route_fourpeat > 0 or goal_fourpeat > 0 or start_fourpeat > 0 or
                        route_threepeat > route_repeat_limit or
                        goal_threepeat > goal_repeat_limit or
                        start_threepeat > start_repeat_limit):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(route_repeat_loc) == 3 and (route_repeat_loc[1] - route_repeat_loc[0] < 16) or
                        (len(route_repeat_loc) == 2 and route_repeat_loc[1] - route_repeat_loc[0] < 16)):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(route_repeat_loc) == 3 and (route_repeat_loc[2] - route_repeat_loc[1] < 16):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(goal_repeat_loc) == 3 and (goal_repeat_loc[1] - goal_repeat_loc[0] < 16) or
                        (len(goal_repeat_loc) == 2 and goal_repeat_loc[1] - goal_repeat_loc[0] < 16)):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(goal_repeat_loc) == 3 and (goal_repeat_loc[2] - goal_repeat_loc[1] < 16):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(start_repeat_loc) == 3 and (start_repeat_loc[1] - start_repeat_loc[0] < 16) or
                        (len(start_repeat_loc) == 2 and start_repeat_loc[1] - start_repeat_loc[0] < 16)):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(start_repeat_loc) == 3 and (start_repeat_loc[2] - start_repeat_loc[1] < 16):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
            # return sg_pairs, fails, [(start_threepeat, start_repeat_loc), (goal_threepeat, goal_repeat_loc),
            #                          (route_threepeat, route_repeat_loc)]
            return sg_pairs

        def generate_sg_rotate_detour_1b(list_size, ort):
            if ort == 'N/NE' or ort == 'N/SW':
                #print('N/NE')
                sg_pairs_list_warmup = [(i, (i + 1) % 4, 0) for i in range(4)] + [(i, (i - 1) % 4, 2) for i in range(4)]
            else:
                #print('SE or NW')
                sg_pairs_list_warmup = [(i, i, 0) for i in range(4)] + [(i, (i + 2) % 4, 2) for i in range(4)]

            if ort == 'N/NW':
                # Third index: LL = 0, LR = 1, RL =2
                sg_pairs_list_test_detour = [(i, (j + i) % 4, j) for i in range(4) for j in [1]]
                sg_pairs_list_test_train_a = [(i, (j + i) % 4, j) for i in range(4) for j in [0,2]]
                sg_pairs_list_test_train_b = [(i, (j + i) % 4, j) for i in range(4) for j in [0, 2]]
                random.shuffle(sg_pairs_list_test_train_a)
                random.shuffle(sg_pairs_list_test_train_b)
            elif ort == 'N/NE':
                # Third index:  LR= 0, RL = 1, RR =2
                sg_pairs_list_test_detour = [(i, (j + i + 1) % 4, j) for i in range(4) for j in [1]]
                sg_pairs_list_test_train_a = [(i%4, (j + i + 1) % 4, j%4) for i in range(8) for j in [2]]
                sg_pairs_list_test_train_b = [(i%4, (j + i + 1) % 4, j%4) for i in range(8) for j in [2]]
                random.shuffle(sg_pairs_list_test_train_a)
                random.shuffle(sg_pairs_list_test_train_b)
            elif ort == 'N/SE':
                # Third index:  RL= 0, RR = 1, LL =2
                sg_pairs_list_test_detour = [(i, (j + i + 2) % 4, j) for i in range(4) for j in [1]]
                sg_pairs_list_test_train_a = [(i, (j + i + 2) % 4, j) for i in range(4) for j in [0,2]]
                sg_pairs_list_test_train_b = [(i, (j + i + 2) % 4, j) for i in range(4) for j in [0, 2]]
                random.shuffle(sg_pairs_list_test_train_a)
                random.shuffle(sg_pairs_list_test_train_b)
            elif ort == 'N/SW':
                # Third index:  RR= 0, LL = 1, LR =2
                sg_pairs_list_test_detour = [(i, (j + i + 3) % 4, j) for i in range(4) for j in [1]]
                sg_pairs_list_test_train_a = [(i, (j + i + 3) % 4, j) for i in range(4) for j in [0,2]]
                sg_pairs_list_test_train_b = [(i, (j + i + 3) % 4, j) for i in range(4) for j in [0, 2]]
                random.shuffle(sg_pairs_list_test_train_a)
                random.shuffle(sg_pairs_list_test_train_b)

            start_repeat_limit = 3
            goal_repeat_limit = 3
            route_repeat_limit = 3
            start_threepeat = 0
            goal_threepeat = 0
            route_threepeat = 0
            start_fourpeat = 0
            goal_fourpeat = 0
            route_fourpeat = 0
            route_repeat_loc = []
            goal_repeat_loc = []
            start_repeat_loc = []
            sg_pairs = []
            passed = False
            fails = 0
            while not passed:
                passed = True
                sg_pairs.clear()
                sg_pairs_list_test_train_a_cp = sg_pairs_list_test_train_a.copy()
                sg_pairs_list_test_train_b_cp = sg_pairs_list_test_train_b.copy()
                random.shuffle(sg_pairs_list_test_train_a_cp)
                random.shuffle(sg_pairs_list_test_train_b_cp)
                for i in range(list_size):
                    sg_pairs_list_test = sg_pairs_list_test_detour + [sg_pairs_list_test_train_a_cp.pop(),
                                                                      sg_pairs_list_test_train_b_cp.pop(),
                                                                      sg_pairs_list_test_train_a_cp.pop(),
                                                                      sg_pairs_list_test_train_b_cp.pop()
                                                                      ]

                    random.shuffle(sg_pairs_list_test)
                    sg_pairs += sg_pairs_list_test.copy()

                for i, sgp in enumerate(sg_pairs[0:-3]):
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2] and sgp[2] == sg_pairs[i + 3][2]:
                        route_fourpeat += 1
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1] and sgp[1] == sg_pairs[i + 3][1]:
                        goal_fourpeat += 1
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0] and sgp[0] == sg_pairs[i + 3][0]:
                        start_fourpeat += 1
                    if sgp[2] == sg_pairs[i + 1][2] and sgp[2] == sg_pairs[i + 2][2]:
                        route_threepeat += 1
                        route_repeat_loc.append(i)
                    if sgp[1] == sg_pairs[i + 1][1] and sgp[1] == sg_pairs[i + 2][1]:
                        goal_threepeat += 1
                        goal_repeat_loc.append(i)
                    if sgp[0] == sg_pairs[i + 1][0] and sgp[0] == sg_pairs[i + 2][0]:
                        start_threepeat += 1
                        start_repeat_loc.append(i)
                # Catch four repeats or over threepeat limit
                if (route_fourpeat > 0 or goal_fourpeat > 0 or start_fourpeat > 0 or
                        route_threepeat > route_repeat_limit or
                        goal_threepeat > goal_repeat_limit or
                        start_threepeat > start_repeat_limit):
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(route_repeat_loc) == 3 and (route_repeat_loc[1] - route_repeat_loc[0] < 16) or
                        (len(route_repeat_loc) == 2 and route_repeat_loc[1] - route_repeat_loc[0] < 16)):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(route_repeat_loc) == 3 and (route_repeat_loc[2] - route_repeat_loc[1] < 16):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(goal_repeat_loc) == 3 and (goal_repeat_loc[1] - goal_repeat_loc[0] < 16) or
                        (len(goal_repeat_loc) == 2 and goal_repeat_loc[1] - goal_repeat_loc[0] < 16)):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(goal_repeat_loc) == 3 and (goal_repeat_loc[2] - goal_repeat_loc[1] < 16):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue

                # Catch route threepeats that are too close together for first occurance
                if (len(start_repeat_loc) == 3 and (start_repeat_loc[1] - start_repeat_loc[0] < 16) or
                        (len(start_repeat_loc) == 2 and start_repeat_loc[1] - start_repeat_loc[0] < 16)):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
                if len(start_repeat_loc) == 3 and (start_repeat_loc[2] - start_repeat_loc[1] < 16):
                    sg_pairs = []
                    route_threepeat = 0
                    goal_threepeat = 0
                    start_threepeat = 0
                    start_fourpeat = 0
                    goal_fourpeat = 0
                    route_fourpeat = 0
                    route_repeat_loc = []
                    goal_repeat_loc = []
                    start_repeat_loc = []
                    fails += 1
                    passed = False
                    continue
            # return sg_pairs, fails, [(start_threepeat, start_repeat_loc), (goal_threepeat, goal_repeat_loc),
            #                          (route_threepeat, route_repeat_loc)]
            return sg_pairs

        random.seed(_seed)
        if pair_type == 'x Fixed LGT' or pair_type == 'x Fixed' or pair_type == 'x Fixed Switch 1' or pair_type == 'x Fixed Switch N':
            sg_pairs = generate_sg_training(12)
        elif pair_type == 'Rotating LGT 2':
            sg_pairs = generate_sg_rotating_2(6)
        elif pair_type == 'Rotating LGT 4A':
            sg_pairs = generate_sg_rotating_4A(3)
        elif pair_type == 'Rotating LGT 4B' or pair_type == 'LGTOM':
            sg_idx = [0, 1, 2, 3]
            sg_pairs_1 = generate_sg_pairs_3(sg_idx)
            sg_pairs_2 = generate_sg_pairs_3(sg_idx)
            sg_pairs_3 = generate_sg_pairs_3(sg_idx)
            sg_pairs = sg_pairs_1 + sg_pairs_2 + sg_pairs_3
        elif pair_type == 'Diff LGT 1' or pair_type == 'Diff LGT Cue ITI 1':
            sg_pairs = generate_sg_differentiate_1(4, cue_goal_index)
        elif pair_type == 'Diff LGT 2a':
            sg_pairs = generate_sg_differentiate_2a(6, cue_goal_index)
        elif pair_type == 'Diff LGT 2b':
            sg_pairs = generate_sg_differentiate_2b(4, cue_goal_index)
        elif pair_type == 'Diff LGT 3a':
            sg_pairs = generate_sg_discrimination_3a(3, cue_goal_index)
        elif pair_type == 'Diff LGT 3b':
            sg_pairs = generate_sg_discrimination_3b(2, cue_goal_index)
        elif pair_type == 'Diff LGT 4':
            sg_pairs = generate_sg_discrimination_4(3)
        elif pair_type == 'Diff LGT Switch':
            sg_pairs = generate_sg_discrimination_4(4)
        elif pair_type == 'Diff LGT Cue Delay':
            sg_pairs = generate_sg_discrimination_cue_delay(2)
        elif pair_type == 'Diff LGT All Cue Delay':
            sg_pairs = generate_sg_discrimination_all_cue_delay(3)
        elif pair_type == 'Diff LGT Split Cue Delay':
            sg_pairs = generate_sg_discrimination_split_cue_delay(4)
        elif pair_type == 'Diff LGT Cue Delay 1a':
            sg_pairs = generate_sg_differentiate_cue_delay_1a(6, cue_goal_index)
        elif pair_type == 'Diff LGT Cue Delay 1b':
            sg_pairs = generate_sg_differentiate_cue_delay_1b(4, cue_goal_index)
        elif pair_type in ['Fixed Cue 1', 'Fixed Cue 1 Imaging']:
            sg_pairs = generate_sg_fixed_cue_1(4, cue_goal_index)
        elif pair_type == 'Fixed Cue 2b':
            sg_pairs = generate_sg_fixed_cue_2b(4, cue_goal_index)
        elif pair_type == 'Fixed Cue 3':
            sg_pairs = generate_sg_fixed_cue_3(3, cue_goal_index)
        elif pair_type in ['Fixed Cue 3a', 'Fixed Cue 3a Imaging']:
            sg_pairs = generate_sg_fixed_cue_3a(6, cue_goal_index)
        elif pair_type in ['Fixed Cue Switch', 'Fixed Cue Switch Imaging']:
            sg_pairs = generate_sg_fixed_cue_1(10, cue_goal_index)
        elif pair_type in ['Fixed No Cue', 'Fixed No Cue Imaging']:
            sg_pairs = generate_sg_fixed_cue_1(4, cue_goal_index)
        elif pair_type in ['Fixed Cue Rotate', 'Fixed Cue Rotate Imaging']:
            sg_pairs = generate_sg_differentiate_1(2, cue_goal_index)
        elif pair_type == 'Dark Train':
            sg_pairs = generate_sg_fixed_cue_1(4, cue_goal_index)
        elif pair_type in ['Dark Detour', 'Dark Detour No Cue']:
            sg_pairs = generate_sg_fixed_cue_2a(5, cue_goal_index)
        elif pair_type == 'Dark Reverse':
            sg_pairs = generate_sg_fixed_cue_1(10, cue_goal_index)
        elif pair_type in ['Rotate Train', 'Rotate Train Imaging']:
            sg_pairs = generate_sg_differentiate_1(4, cue_goal_index)
        elif pair_type in ['Rotate Detour', 'Rotate Detour Imaging']:
            sg_pairs = generate_sg_fixed_cue_2a(5, cue_goal_index)
        elif pair_type in ['Rotate Detour Moving', 'Rotate Detour Moving Imaging']:
            sg_pairs = generate_sg_rotate_detour_1a(6, cue_goal_index)
        elif pair_type in ['Rotate Detour 1b Moving', 'Rotate Detour 1b Moving Imaging']:
            sg_pairs = generate_sg_rotate_detour_1b(4, cue_goal_index)
        elif pair_type in ['Rotate Reverse', 'Rotate Reverse Imaging']:
            sg_pairs = generate_sg_differentiate_1(10, cue_goal_index)
        elif pair_type == 'predetour':
            sg_pairs = generate_sg_predetour(cue_goal_index, goal_location=goal_location)
        elif pair_type == 'None':
            sg_pairs = None
        else:
            pass

        return sg_pairs

    def set_cue_goal_index(self, cue_goal):
        if cue_goal == 'N/NE':
            return 0
        elif cue_goal == 'N/SE':
            return 1
        elif cue_goal == 'N/SW':
            return 2
        elif cue_goal == 'N/NW':
            return 3

    # returns the cue orientation based on the animals assigned cue goal association
    # and the current reward position for the trial. Results how cue should be
    # orriented to goal. Index corresponds to [0:N, 1:E, 2:S, 3:W].
    def cue_trial_index(self, cue_goal_index, trial_goal):
        if cue_goal_index == 0:  # N/NE association
            return trial_goal
        elif cue_goal_index == 3:  # N/SE association
            return (trial_goal + 1) % 4
        elif cue_goal_index == 2:
            return (trial_goal + 2) % 4 # N/SW association
        elif cue_goal_index == 1:
            return (trial_goal + 3) % 4 # N/NW association

    def action_vector_list_to_readable(self, action_vector_list, start_goal_pair):
        # avlr: action vector list readable
        avlr = []
        # 0: append index
        avlr.append(action_vector_list[31])
        # 1: append type
        if action_vector_list[0] == 0:
            avlr.append('Presession')
        elif action_vector_list[0] == 1:
            avlr.append('ITI')
        elif action_vector_list[0] == 2:
            avlr.append('Pretrial')
        elif action_vector_list[0] == 3:
            avlr.append('Trial Start')
        elif action_vector_list[0] == 4:
            avlr.append('Trial End')
        elif action_vector_list[0] == 5:
            avlr.append('Exp Trial')
        elif action_vector_list[0] == 6:
            avlr.append('Exp Barrier')
        # 2: append trigger zone
        avlr.append(action_vector_list[1])
        # 3: append delay time
        avlr.append(action_vector_list[2])
        # 4: append start arm
        if start_goal_pair[0] == 0:
            avlr.append('North')
        elif start_goal_pair[0] == 1:
            avlr.append('East')
        elif start_goal_pair[0] == 2:
            avlr.append('South')
        elif start_goal_pair[0] == 3:
            avlr.append('West')
        elif start_goal_pair[0] == 4:
            avlr.append('None')
        # 5: append goal
        if start_goal_pair[1] == 0:
            avlr.append('Northeast')
        elif start_goal_pair[1] == 1:
            avlr.append('Southeast')
        elif start_goal_pair[1] == 2:
            avlr.append('Southwest')
        elif start_goal_pair[1] == 3:
            avlr.append('Northwest')
        elif start_goal_pair[1] == 4:
            avlr.append('Any')
        # 6: append cue orientation
        if action_vector_list[19] == 1:
            avlr.append('North')
        elif action_vector_list[20] == 1:
            avlr.append('East')
        elif action_vector_list[21] == 1:
            avlr.append('South')
        elif action_vector_list[22] == 1:
            avlr.append('West')
        else:
            avlr.append('OFF')
        # 7: append reward
        if (action_vector_list[23] == 1 or
                action_vector_list[24] == 1 or
                action_vector_list[25] == 1 or
                action_vector_list[26] == 1):
            avlr.append('Given')
        elif self.label_session_type_data.text() == 'Exposure' and action_vector_list[0] == 5:
            avlr.append('Given')
        else:
            avlr.append('Held')
        # 8: append UV Light
        if (action_vector_list[27] == 1 or
                action_vector_list[28] == 1 or
                action_vector_list[29] == 1 or
                action_vector_list[30] == 1):
            avlr.append('ON')
        else:
            avlr.append('OFF')

        # 9: Append session type
        avlr.append(self.label_session_type.text())

        return avlr

    def warning_dialog(self, warning_message):
        dlg = QMessageBox(self)
        dlg.setWindowTitle(warning_message[0])
        message = str()
        for wm in warning_message[1:]:
            message += wm + '\n'
        dlg.setText(message)
        dlg.setStandardButtons(QMessageBox.Ok | QMessageBox.Ignore)
        dlg.setIcon(QMessageBox.Warning)
        button = dlg.exec()

        if button == QMessageBox.Ok:
            return False
        elif button == QMessageBox.Ignore:
            return True
        else:
            return False

    def pause_session_dialog(self):
        self.worker_trsc.pause_session = True
        dlg = QMessageBox(self)
        dlg.setWindowTitle('Session Paused')
        dlg.setText('Session paused\nselect Ok to\ncontinue.')
        dlg.setStandardButtons(QMessageBox.Ok)
        dlg.setIcon(QMessageBox.Warning)
        #advance_vector = dlg.addButton('Adv Vect', QMessageBox.YesRole)
        dlg.setModal(False)
        dlg.show()
        button = dlg.exec()

        if button == QMessageBox.Ok:
            self.worker_trsc.pause_session = False
        else:
            self.worker_trsc.pause_session = False

    def run_session_dialog(self, message):
        dlg = QMessageBox(self)
        dlg.setWindowTitle(message[0])
        dlg.setText(message[1])
        dlg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        button = dlg.exec()
        if button == QMessageBox.Ok:
            return True
        elif button == QMessageBox.Cancel:
            return False
        else:
            return False

    def insert_predetour_session_data(self, goal_location):
        session_seed = int(self.label_session_seed_data.text())
        session_type = self.label_session_type.text()
        self.start_goal_pairs = self.generate_start_goal_pairs(session_seed, session_type,
                                                               self.label_session_cue_conf_data.text(),
                                                               goal_location)
        pass


    def init_session_data(self):
        # Check that all information is entered before initializing session data
        warning_raise = False
        warning_message = []
        warning_message.append('Session Init Warning')
        if self.label_subject_name_data.text() == '':
            warning_message.append('Enter subject name')
            warning_raise = True
        if self.label_sex_data.text() == '':
            warning_message.append('Enter rat sex')
            warning_raise = True
        if self.label_last_session_data.text() == '':
            warning_message.append('Enter last session number')
            warning_raise = True
        if self.label_behavior_data.text() == '':
            warning_message.append('Enter behavior')
            warning_raise = True
        if self.label_cue_conf_data.text() == '':
            warning_message.append('Enter cue configuration')
            warning_raise = True
        if self.label_session_type_data.text() == '':
            warning_message.append('Enter cue retained')
            warning_raise = True

        if warning_raise == True:
            warning_state = self.warning_dialog(warning_message)
            if warning_state == False:
                return

        # Check what kind of session it is to properly update the session number
        if self.label_session_type_data.text() == 'Exposure':
            if self.label_last_session_data.text() == 'None':
                session_number = '1e'
            elif self.label_last_session_data.text() == '1e':
                session_number = '2e'
            else:
                session_number = 'None'
        elif self.label_session_type_data.text() != 'Exposure':
            if self.label_last_session_data.text() == '2e':
                session_number = 1
            elif self.label_last_session_data.text() == 'None':
                session_number = 1
            else:
                session_number = int(self.label_last_session_data.text()) + 1

        self.label_session_number_data.setText(str(session_number))

        # Set date and time
        dt_date = datetime.datetime.today()
        current_date = str(dt_date.month) + '/' + str(dt_date.day) + '/' + str(dt_date.year)
        self.label_session_date_data.setText(current_date)
        current_time = str(dt_date.hour).zfill(2) + ':' + str(dt_date.minute).zfill(2) + ':' + str(
            dt_date.second).zfill(2)
        self.label_session_time_data.setText(current_time)
        # Store the seed used for the random numbers
        # The ord gets rid of string values in the seed
        if session_number == '1e':
            self.label_session_seed_data.setText(self.add_seed(ord('a'), current_date))
        elif session_number == '2e':
            self.label_session_seed_data.setText(self.add_seed(ord('b'), current_date))
        elif session_number == 'None':
            self.label_session_seed_data.setText(self.add_seed(ord('n'), current_date))
        else:
            self.label_session_seed_data.setText(self.add_seed(session_number, current_date))

        self.label_session_behavior_data.setText(self.label_behavior_data.text())
        self.label_session_cue_conf_data.setText(self.label_cue_conf_data.text())
        self.label_session_type.setText(self.label_session_type_data.text())
        # clear general info
        self.session_general_info.clear()
        # initialize session_file_header
        self.session_general_info['subject_name'] = self.label_subject_name_data.text()
        self.session_general_info['subject_id'] = self.label_subject_id_data.text()
        self.session_general_info['session_number'] = self.label_session_number_data.text()
        self.session_general_info['date'] = self.label_session_date_data.text()
        self.session_general_info['time'] = self.label_session_time_data.text()
        self.session_general_info['behavior'] = self.label_behavior_data.text()
        self.session_general_info['cue_conf'] = self.label_cue_conf_data.text()
        self.session_general_info['session_type'] = self.label_session_type.text()
        self.session_general_info['delay'] = self.label_delay_data.text()
        self.session_general_info['reward_volume'] = self.line_edit_reward_volume.text()

        # going to use this seed variable to shuffle start arm and reward
        session_seed = int(self.label_session_seed_data.text())
        self.session_general_info['seed'] = session_seed

        # Generate list of start arm and goal locations to be used
        # for each trial
        session_type = self.label_session_type.text()
        if self.label_behavior_data.text() == 'Landmark Guided Task':
            # Set varThreshold for motion tracking given that particular lighting of the landmark guided task
            self.line_edit_varThreshold.setText('200')
            self.line_edit_IR_lights.setText('255')
            if session_type in ['Fixed LGT', 'Rotating LGT 2', 'Rotating LGT 4A', 'Rotating LGT 4B', 'Fixed Cue 1',
                                'Fixed Cue 2a', 'Fixed Cue 2b', 'Fixed Cue 3', 'Fixed Cue Switch', 'Fixed No Cue',
                                'Fixed Cue Rotate', 'Diff LGT 1', 'Diff LGT 2a', 'Diff LGT 2b', 'Diff LGT 3a',
                                'Diff LGT 3b', 'Diff LGT 4', 'Diff LGT Cue Delay', 'Diff LGT Cue Delay 1a',
                                'Diff LGT Cue Delay 1b', 'Diff LGT All Cue Delay', 'Diff LGT Split Cue Delay',
                                'Diff LGT Switch', 'Diff LGT Cue ITI 1', 'Dark Train', 'Dark Detour',
                                'Dark Detour No Cue', 'Dark Reverse', 'Rotate Train', 'Rotate Detour', 'Rotate Reverse',
                                'Rotate Detour Moving', 'Fixed Cue 1 Imaging', 'Fixed Cue 2a Imaging',
                                'Fixed No Cue Imaging', 'Fixed Cue Rotate Imaging', 'Fixed Cue Switch Imaging',
                                'Rotate Train Imaging', 'Rotate Detour Imaging', 'Rotate Detour Moving Imaging',
                                'Rotate Reverse Imaging', 'Rotate Detour 1b Moving', 'Rotate Detour 1b Moving Imaging',
                                'Fixed Cue 3a', 'Fixed Cue 3a Imaging']:


                self.start_goal_pairs = self.generate_start_goal_pairs(session_seed, session_type,
                                                                       self.label_session_cue_conf_data.text())
                self.session_general_info['start_goal_pairs'] = self.start_goal_pairs

                # cue_goal_index coresponds to [N/NE:0, N/SE:1, N/SW:2, N/NW:3] where
                # the above key is cue/reward associations if cue was set to north.
                cue_goal_index = self.set_cue_goal_index(self.label_cue_conf_data.text())
                self.session_general_info['cue_goal_index'] = cue_goal_index

                # cue_index gives the cue location given the reward location based
                # on the animals cue_goal_orientation
                cue_index = self.cue_trial_index(cue_goal_index, self.start_goal_pairs[0][1])
                self.session_general_info['cue_index'] = cue_index

                # clear action vector list
                self.action_vector_list.clear()

                # print('goal: ', start_goal_pairs[0][1], 'cgi: ', cue_goal_index, 'ci: ', cue_index)
                # START ADDING ACTION VECTORS TO ACTION VECTOR LIST:
                # Presession and first trial
                # First trial starts with presession rather than ITI
                # append presession state to action vector list
                self.action_vector_list.append(self.action_states_matrix_LMGT[0][self.start_goal_pairs[0][0]].copy())
                # append pretrial state to action vector list
                self.action_vector_list.append(self.action_states_matrix_LMGT[2][self.start_goal_pairs[0][0]][cue_index].copy())
                # append trial start state to action vector list
                self.action_vector_list.append(self.action_states_matrix_LMGT[3][self.start_goal_pairs[0][0]][cue_index].copy())
                # append trial end state to action vector list
                self.action_vector_list.append(self.action_states_matrix_LMGT[4][self.start_goal_pairs[0][1]][cue_index].copy())

                # factory add the remainder of action vectors to action vector matrix
                # sgp: start goal pairs
                for i, sgp in enumerate(self.start_goal_pairs[1:]):
                    cue_index = self.cue_trial_index(cue_goal_index, sgp[1])
                    self.action_vector_list.append(self.action_states_matrix_LMGT[1][sgp[0]].copy())
                    self.action_vector_list.append(self.action_states_matrix_LMGT[2][sgp[0]][cue_index].copy())
                    self.action_vector_list.append(self.action_states_matrix_LMGT[3][sgp[0]][cue_index].copy())
                    self.action_vector_list.append(self.action_states_matrix_LMGT[4][sgp[1]][cue_index].copy())
                # Assign appropriate index values to each list
                for i, avl in enumerate(self.action_vector_list):
                    avl[31] = i

                self.session_general_info['action_vector_list'] = self.action_vector_list

                # create readable action value list
                self.action_vector_list_readable.clear()
                sgp_index = -1
                for i, avl in enumerate(self.action_vector_list):
                    if i % 4 == 0:
                        sgp_index += 1
                    self.action_vector_list_readable.append(
                        self.action_vector_list_to_readable(avl, self.start_goal_pairs[sgp_index]))

                self.session_general_info['readable_action_vector_list'] = self.action_vector_list_readable

                # Display Action Vector in GUI
                del self.action_vec_table_model
                self.action_vec_table_model = TableStaticModel(
                    self.action_vector_list_readable_header,
                    self.action_vector_list_readable)
                self.action_vec_table.setModel(self.action_vec_table_model)
                self.action_vec_table.selectionModel().selectionChanged.connect(self.get_action_vector_idx)
                self.action_vec_table.resizeRowsToContents()
                self.action_vec_table.setColumnHidden(9, True)

            elif session_type == 'LGTOM':
                self.start_goal_pairs = self.generate_start_goal_pairs(session_seed, session_type)
                self.session_general_info['start_goal_pairs'] = self.start_goal_pairs
                cue_goal_index = self.set_cue_goal_index(self.label_cue_conf_data.text())
                self.session_general_info['cue_goal_index'] = cue_goal_index
                cue_index = self.cue_trial_index(cue_goal_index, self.start_goal_pairs[0][1])
                self.session_general_info['cue_index'] = cue_index

                self.action_vector_list.clear()
                print(self.action_states_matrix_LMGTOM[0])
                self.action_vector_list.append(self.action_states_matrix_LMGTOM[0][self.start_goal_pairs[0][0]].copy())
                self.action_vector_list.append(self.action_states_matrix_LMGTOM[2][self.start_goal_pairs[0][0]][cue_index].copy())
                self.action_vector_list.append(self.action_states_matrix_LMGTOM[3][self.start_goal_pairs[0][0]][cue_index].copy())
                self.action_vector_list.append(self.action_states_matrix_LMGTOM[4][self.start_goal_pairs[0][1]][cue_index].copy())

                # factory add the remainder of action vectors to action vector matrix
                # sgp: start goal pairs
                for sgp in self.start_goal_pairs[1:]:
                    cue_index = self.cue_trial_index(cue_goal_index, sgp[1])
                    self.action_vector_list.append(self.action_states_matrix_LMGTOM[1][sgp[0]].copy())
                    self.action_vector_list.append(self.action_states_matrix_LMGTOM[2][sgp[0]][cue_index].copy())
                    self.action_vector_list.append(self.action_states_matrix_LMGTOM[3][sgp[0]][cue_index].copy())
                    self.action_vector_list.append(self.action_states_matrix_LMGTOM[4][sgp[1]][cue_index].copy())

                # Assign appropriate index values to each list
                for i, avl in enumerate(self.action_vector_list):
                    avl[31] = i

                self.session_general_info['action_vector_list'] = self.action_vector_list

                self.action_vector_list_readable.clear()
                # create readable action value list
                sgp_index = -1
                for i, avl in enumerate(self.action_vector_list):
                    if i % 4 == 0:
                        sgp_index += 1
                    self.action_vector_list_readable.append(
                        self.action_vector_list_to_readable(avl, self.start_goal_pairs[sgp_index]))

                self.session_general_info['readable_action_vector_list'] = self.action_vector_list_readable
                del self.action_vec_table_model
                self.action_vec_table_model = TableStaticModel(
                    self.action_vector_list_readable_header,
                    self.action_vector_list_readable)
                self.action_vec_table.setModel(self.action_vec_table_model)
                self.action_vec_table.selectionModel().selectionChanged.connect(self.get_action_vector_idx)
                self.action_vec_table.resizeRowsToContents()
                self.action_vec_table.setColumnHidden(9, True)

            elif session_type == 'Exposure' or session_type == 'None':
                if session_number == 'None' or session_number == '1e':
                    self.start_goal_pairs = []
                    for _ in range(33):
                        self.start_goal_pairs.append((4, 4))
                    self.session_general_info['start_goal_pairs'] = self.start_goal_pairs
                elif session_number == '2e':
                    self.start_goal_pairs = []
                    for _ in range(41):
                        self.start_goal_pairs.append((4, 4))
                    self.session_general_info['start_goal_pairs'] = self.start_goal_pairs
                # cue_goal_index coresponds to [N/NE:0, N/SE:1, N/SW:2, N/NW:3] where
                # the above key is cue/reward associations if cue was set to north.
                cue_goal_index = self.set_cue_goal_index(self.label_cue_conf_data.text())
                self.session_general_info['cue_goal_index'] = cue_goal_index
                # cue_index gives the cue location given the reward location based
                # on the animals cue_goal_orientation
                cue_index = self.cue_trial_index(cue_goal_index, self.start_goal_pairs[0][1])
                self.session_general_info['cue_index'] = cue_index
                # clear action vector list
                self.action_vector_list.clear()

                # START ADDING ACTION VECTORS TO ACTION VECTOR LIST:
                # Presession and first trial
                # First trial starts with presession rather than ITI
                # append presession state to action vector list
                # Make a shuffle vector to randomly pick where cue displays
                if session_number == '1e' or session_number == 'None':
                    self.action_vector_list = [
                        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ]
                    for i in range(1, 33):
                        delay_interval = int(random.gauss(45,10))
                        action_vector = [5, 0, delay_interval, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, i]
                        self.action_vector_list.append(action_vector)

                elif session_number == '2e':
                    self.action_vector_list = [
                        [0,  0,  0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                        [6,  0, 60, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                        [6,  0, 30, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2],
                        [6, 15, 30, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3],
                        [6, 12, 30, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4],
                        [6,  7, 30, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 5],
                        [6, 10,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 6],
                    ]
                    for i in range(7, 40):
                        delay_interval = int(random.gauss(45,10))
                        action_vector = [5, 0, delay_interval, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, i]
                        self.action_vector_list.append(action_vector)


                # append pretrial state to action vector list

                self.session_general_info['action_vector_list'] = self.action_vector_list

                self.action_vector_list_readable.clear()
                # create readable action value list
                sgp_index = -1
                for i, avl in enumerate(self.action_vector_list):
                    if i % 4 == 0:
                        sgp_index += 1
                    self.action_vector_list_readable.append(
                        self.action_vector_list_to_readable(avl, self.start_goal_pairs[sgp_index]))

                self.session_general_info['readable_action_vector_list'] = self.action_vector_list_readable
                del self.action_vec_table_model
                self.action_vec_table_model = TableStaticModel(
                    self.action_vector_list_readable_header,
                    self.action_vector_list_readable)
                self.action_vec_table.setModel(self.action_vec_table_model)
                self.action_vec_table.selectionModel().selectionChanged.connect(self.get_action_vector_idx)
                self.action_vec_table.resizeRowsToContents()
                self.action_vec_table.setColumnHidden(9, True)
            else:
                pass

        elif self.label_behavior_data.text() == 'Path Integration Guided Task':
            self.line_edit_varThreshold.setText('200')
            self.line_edit_IR_lights.setText('20')
            if session_type == 'Fixed' or session_type == 'Fixed Switch 1' or session_type == 'Fixed Switch N':
                self.start_goal_pairs = self.generate_start_goal_pairs(session_seed, session_type)
                # Save list to general info
                self.session_general_info['start_goal_pairs'] = self.start_goal_pairs
                # cue_goal_index coresponds to [N/NE:0, N/SE:1, N/SW:2, N/NW:3] where
                # the above key is cue/reward associations if cue was set to north.
                cue_goal_index = self.set_cue_goal_index(self.label_cue_conf_data.text())
                self.session_general_info['cue_goal_index'] = cue_goal_index
                # cue_index gives the cue location given the reward location based
                # on the animals cue_goal_orientation
                cue_index = self.cue_trial_index(cue_goal_index, self.start_goal_pairs[0][1])
                self.session_general_info['cue_index'] = cue_index
                # clear action vector list
                self.action_vector_list.clear()
                # print('goal: ', start_goal_pairs[0][1], 'cgi: ', cue_goal_index, 'ci: ', cue_index)
                # START ADDING ACTION VECTORS TO ACTION VECTOR LIST:
                # Presession and first trial
                # First trial starts with presession rather than ITI
                # append presession state to action vector list
                self.action_vector_list.append(self.action_states_matrix_PIGT[0][self.start_goal_pairs[0][0]].copy())
                # append pretrial state to action vector list
                self.action_vector_list.append(
                    self.action_states_matrix_PIGT[2][self.start_goal_pairs[0][0]][cue_index].copy())
                # append trial start state to action vector list
                self.action_vector_list.append(
                    self.action_states_matrix_PIGT[3][self.start_goal_pairs[0][0]][cue_index].copy())
                # append trial end state to action vector list
                self.action_vector_list.append(
                    self.action_states_matrix_PIGT[4][self.start_goal_pairs[0][1]][cue_index].copy())

                # factory add the remainder of action vectors to action vector matrix
                # sgp: start goal pairs
                for sgp in self.start_goal_pairs[1:]:
                    cue_index = self.cue_trial_index(cue_goal_index, sgp[1])
                    self.action_vector_list.append(self.action_states_matrix_PIGT[1][sgp[0]].copy())
                    self.action_vector_list.append(self.action_states_matrix_PIGT[2][sgp[0]][cue_index].copy())
                    self.action_vector_list.append(self.action_states_matrix_PIGT[3][sgp[0]][cue_index].copy())
                    self.action_vector_list.append(self.action_states_matrix_PIGT[4][sgp[1]][cue_index].copy())

                # Assign appropriate index values to each list
                for i, avl in enumerate(self.action_vector_list):
                    avl[31] = i

                self.session_general_info['action_vector_list'] = self.action_vector_list

                self.action_vector_list_readable.clear()
                # create readable action value list
                sgp_index = -1
                for i, avl in enumerate(self.action_vector_list):
                    if i % 4 == 0:
                        sgp_index += 1
                    self.action_vector_list_readable.append(
                        self.action_vector_list_to_readable(avl, self.start_goal_pairs[sgp_index]))

                self.session_general_info['readable_action_vector_list'] = self.action_vector_list_readable
                del self.action_vec_table_model
                self.action_vec_table_model = TableStaticModel(
                    self.action_vector_list_readable_header,
                    self.action_vector_list_readable)
                self.action_vec_table.setModel(self.action_vec_table_model)
                self.action_vec_table.selectionModel().selectionChanged.connect(self.get_action_vector_idx)
                self.action_vec_table.resizeRowsToContents()
                self.action_vec_table.setColumnHidden(9, True)

            elif session_type == 'Exposure' or session_type == 'None':
                self.start_goal_pairs = [(0, 0)]
                self.session_general_info['start_goal_pairs'] = self.start_goal_pairs

                # cue_goal_index coresponds to [N/NE:0, N/SE:1, N/SW:2, N/NW:3] where
                # the above key is cue/reward associations if cue was set to north.
                cue_goal_index = self.set_cue_goal_index(self.label_cue_conf_data.text())
                self.session_general_info['cue_goal_index'] = cue_goal_index
                # cue_index gives the cue location given the reward location based
                # on the animals cue_goal_orientation
                cue_index = self.cue_trial_index(cue_goal_index, self.start_goal_pairs[0][1])
                self.session_general_info['cue_index'] = cue_index
                # clear action vector list
                self.action_vector_list.clear()

                # START ADDING ACTION VECTORS TO ACTION VECTOR LIST:
                # Presession and first trial
                # First trial starts with presession rather than ITI
                # append presession state to action vector list
                if session_number == '1e' or session_number == 'None':
                    self.action_vector_list = [
                        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                        [0, 0, 900, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]
                    ]
                elif session_number == '2e':
                    self.action_vector_list = [
                        [0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                        [0, 0, 900, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]
                    ]
                # append pretrial state to action vector list

                self.session_general_info['action_vector_list'] = self.action_vector_list

                self.action_vector_list_readable.clear()
                # create readable action value list
                sgp_index = -1
                for i, avl in enumerate(self.action_vector_list):
                    if i % 4 == 0:
                        sgp_index += 1
                    self.action_vector_list_readable.append(
                        self.action_vector_list_to_readable(avl, self.start_goal_pairs[sgp_index]))

                self.session_general_info['readable_action_vector_list'] = self.action_vector_list_readable
                del self.action_vec_table_model
                self.action_vec_table_model = TableStaticModel(
                    self.action_vector_list_readable_header,
                    self.action_vector_list_readable)
                self.action_vec_table.setModel(self.action_vec_table_model)
                self.action_vec_table.selectionModel().selectionChanged.connect(self.get_action_vector_idx)
                self.action_vec_table.resizeRowsToContents()
                self.action_vec_table.setColumnHidden(9, True)

            else:
                pass

        self.button_test_action_vector.setEnabled(True)
        self.button_open_stream_session.setEnabled(True)

    # Converts zone to rectangle coordinates for opencv
    def zone_cordinates(self, zone):
        if zone == 1:
            return [0, 0], [47, 0], [0, 47]
        elif zone == 2:
            return [43, 0], [97, 35]
        elif zone == 3:
            return [98, 0], [138, 35]
        elif zone == 4:
            return [139, 0], [194, 35]
        elif zone == 5:
            return [193,0], [239, 0], [239,46]
        elif zone == 6:
            return [0, 45], [34, 100]
        elif zone == 7:
            return [96, 36], [138, 96]
        elif zone == 8:
            return [205, 41], [239, 97]
        elif zone == 9:
            return [0, 101], [34, 139]
        elif zone == 10:
            return [35, 103], [95, 137]
        elif zone == 11:
            return [96, 97], [143, 142]
        elif zone == 12:
            return [144, 98], [204, 139]
        elif zone == 13:
            return [205, 98], [239, 139]
        elif zone == 14:
            return [0, 140], [34, 196]
        elif zone == 15:
            return [102, 143], [137, 204]
        elif zone == 16:
            return [205, 140], [239, 195]
        elif zone == 17:
            return [0, 193], [46, 239], [0, 239]
        elif zone == 18:
            return [43, 205], [97, 239]
        elif zone == 19:
            return [98, 205], [139, 239]
        elif zone == 20:
            return [140, 205], [195, 239]
        elif zone == 21:
            return [239, 192], [239, 239], [192, 239]
        else:
            return [-1, -2], [-1, -2]

    def display_video(self, frame, x, y, zone):
        scale = 2 # 1 is scale on 240 x 240
        self.video_coordinate_stream = [zone, x, y]
        # USE MotionTrack_SocketStream_CameraAllign.py on rasp to allign camera
        magnitude = 2
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if zone == 1 or zone == 5 or zone == 17 or zone == 21:
            c1, c2, c3 = self.zone_cordinates(zone)
            c1 = [scale*c for c in c1]
            c2 = [scale*c for c in c2]
            c3 = [scale*c for c in c3]
            poly_coordinates = np.array([[c1,c2,c3]],np.int32)
            poly_coordinates = poly_coordinates.reshape((-1,1,2))
            cv2.polylines(frame, [poly_coordinates], True, (255,255,0),scale)
        else:
            x_rect_rat_cordinates, y_rect_rat_cordinates = self.zone_cordinates(zone)
            x_rect_rat_cordinates = [scale*x for x in x_rect_rat_cordinates]
            y_rect_rat_cordinates = [scale*y for y in y_rect_rat_cordinates]
            cv2.rectangle(frame, x_rect_rat_cordinates, y_rect_rat_cordinates, (0, 0, 255), scale)

        #Allignment lines
        # cv2.rectangle(frame, (28, 28), (236, 236), (0, 0, 255), 2)
        # cv2.rectangle(frame, (238, 238), (448, 448), (0, 0, 255), 2)
        # cv2.rectangle(frame, (238, 28), (448, 236), (0, 0, 255), 2)
        # cv2.rectangle(frame, (28, 238), (236, 448), (0, 0, 255), 2)
        # cv2.rectangle(frame, (26, 32), (32, 38), (0, 255, 0), -1)
        # cv2.rectangle(frame, (442, 22), (442, 28), (0, 255, 0), -1)
        # cv2.rectangle(frame, (446, 446), (452, 452), (0, 255, 0), -1)
        # cv2.rectangle(frame, (26, 446), (32, 452), (0, 255, 0), -1)

        cv2.circle(frame, (scale*x, scale*y), scale*2, (0, 255, 0), -1)
        frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        height, width, channels = frame.shape
        bytes_per_line = width * channels
        converted_Qt_image = QImage(frame, width, height, bytes_per_line, QImage.Format_RGB888)
        self.label_video_display.setPixmap(QPixmap.fromImage(converted_Qt_image).scaled(
            self.label_video_display.width(), self.label_video_display.height(), Qt.KeepAspectRatioByExpanding))

    def test_action_vector(self):
        action_vector = self.action_vector_list[self.action_vector_idx[0]]
        # print('2: test actuators')
        # Check barrier states and emit signal
        for i, av in enumerate(action_vector[3:19]):
            if av != self.state_barrier_list[i]:
                self.control_actuator(i)
                time.sleep(0.5)

        # print('3: test cues')
        # Check which cue if any should be displayed
        for i, av in enumerate(action_vector[19:23]):
            if i == 0 and av == 1:
                cue_index = 0
                break
            elif i == 1 and av == 1:
                cue_index = 1
                break
            elif i == 2 and av == 1:
                cue_index = 2
                break
            elif i == 3 and av == 1:
                cue_index = 3
                break
            else:
                cue_index = 4
        print(cue_index)
        # make sure display is in state that needs to actually be changed
        if self.state_cue_list[cue_index] == 0:
            self.control_cue(cue_index)

        # print('4: test reward')
        # Check reward condition and if it needs to be emited
        for i, av in enumerate(action_vector[23:27]):
            if av == 1:
                self.control_syringe_pump(i)
                break

        # Check which light if any should be used
        for i, av in enumerate(action_vector[27:31]):
            if av != self.state_cue_light_list[i]:
                self.control_cue_light(i)
                break

    def test_action_vector_thd(self):
        if self.action_vector_idx[0] != '':
            action_vector = self.action_vector_list[self.action_vector_idx[0]]
            print(self.action_vector_list[self.action_vector_idx[0]])
            self.thread_tav = QThread(parent=self)
            self.worker_tav = WorkerDeviceControlThread(action_vector,
                                                        self.state_barrier_list, self.state_cue_list,
                                                        self.state_cue_light_list)
            self.worker_tav.moveToThread(self.thread_tav)

            self.thread_tav.started.connect(self.worker_tav.run)

            self.worker_tav.finished.connect(self.thread_tav.quit)
            self.worker_tav.finished.connect(self.worker_tav.deleteLater)
            self.thread_tav.finished.connect(self.thread_tav.deleteLater)

            self.worker_tav.barrier_index.connect(self.control_actuator)
            self.worker_tav.cue_index.connect(self.control_cue)
            self.worker_tav.reward_index.connect(self.control_syringe_pump)
            self.worker_tav.cue_light_index.connect(self.control_cue_light)

            self.thread_tav.start()
        else:
            print('ERROR: action_vector_list not initialized!')

    def mp_start_sound_process(self):
        self.sound_control.start_player()

    def mp_stop_sound_process(self):
        self.sound_control.stop_player()

    def mp_play_sound(self, sound_type):
        self.sound_control.play_sound(sound_type)

    def button_mp_play_sound(self):
        self.mp_start_sound_process()
        pass_sound_type = int(self.line_edit_sound.text())
        if pass_sound_type == 1:
            print('setting sound to noise')
            self.mp_play_sound(pass_sound_type)
            time.sleep(10)
        else:
            print('setting sound to quite')
            self.mp_play_sound(pass_sound_type)
        self.mp_stop_sound_process()

    def thread_run_video(self):
        # let main_window know video is running
        self.state_video[0] = 1

        self.button_open_video.setEnabled(False)

        # trv: thread_run_video
        self.thread_trv = QThread()
        self.worker_trv = WorkerVideoThread(int(self.line_edit_fps.text()),
                                            int(self.line_edit_shutter_speed.text()),
                                            int(self.line_edit_iso.text()),
                                            int(self.line_edit_varThreshold.text()))
        self.worker_trv.moveToThread(self.thread_trv)

        self.thread_trv.started.connect(self.worker_trv.run)
        self.worker_trv.finished.connect(self.thread_trv.quit)
        self.worker_trv.finished.connect(self.worker_trv.deleteLater)
        self.thread_trv.finished.connect(self.thread_trv.deleteLater)
        self.worker_trv.updated_image.connect(self.display_video)
        self.worker_trv.update_button.connect(self.update_state_close_video_button)

        self.thread_trv.start()

        self.label_state_video.setText('Running')

        self.button_close_video.setEnabled(True)
        self.thread_trv.finished.connect(
            lambda: self.button_open_video.setEnabled(True)
        )
        self.thread_trv.finished.connect(
            lambda: self.button_close_video.setEnabled(False)
        )
        self.thread_trv.finished.connect(
            lambda: self.label_state_video.setText('Idle')
        )

    def thread_close_video(self):
        self.state_video[0] = 0
        self.worker_trv.thread_open_video = False
        # del self.worker_trv

    def update_state_close_video_button(self):
        self.state_video[0] = 0
        self.button_close_video.setEnabled(False)
        self.button_open_video.setEnabled(True)

    def update_label_session(self, state, step, time_stamp, pixel_coordinate_x,
                             pixel_coordinate_y, zone):
        time_stamp_offset = time_stamp - self.session_start_time_offset
        self.label_stream_session.setText(
            f'Session: {state} | Step: {step} | Time: {int(time_stamp_offset / 3600000) % 12}:{int(time_stamp_offset / 60000) % 60:02}:{int(time_stamp_offset / 1000) % 60:02}:{int((time_stamp_offset % 1000) / 10):02} | Pixel Coordinates: ({pixel_coordinate_x}, {pixel_coordinate_y}) | Zone: {zone}')
        self.session_event_stream_LGT[0] = step
        self.session_event_stream_LGT[1] = time_stamp
        self.session_event_stream_LGT[2] = pixel_coordinate_x
        self.session_event_stream_LGT[3] = pixel_coordinate_y
        self.session_event_stream_LGT[4] = zone
        # print(self.session_event_stream_LGT)

    def update_session_event_table_control_thd(self, event_list):
        self.db_cursor.execute(
            f'''
                INSERT INTO session_event (action_vector_idx, action_vector_type, frame, time_stamp, zone,
                                           x_coordinate, y_coordinate, time_duration, start_arm, goal_location,
                                           cue_orientation, session_id)
                VALUES({event_list[0]},
                       '{event_list[1]}',
                       {event_list[2]},
                       {event_list[3]},
                       {event_list[4]},
                       {event_list[5]},
                       {event_list[6]},
                       {event_list[7]},
                       '{event_list[8]}',
                       '{event_list[9]}',
                       '{event_list[10]}',
                       {event_list[11]});
            ''')
        self.db_conn_dir.commit()

    def update_trial_table_control_thd(self, trial_list):
        self.db_cursor.execute(
            f'''
                        INSERT INTO trial (trial_number, start_arm, goal_location, cue_orientation, time_duration,
                                           errors, session_type, session_id, turn_1, turn_2, goal_zones_visited, cue_on)
                        VALUES({trial_list[0]},
                               '{trial_list[1]}',
                               '{trial_list[2]}',
                               '{trial_list[3]}',
                               {trial_list[4]},
                               {trial_list[5]},
                               '{trial_list[6]}',
                               {trial_list[7]},
                               '{trial_list[9][0]}',
                               '{trial_list[9][1]}',
                               '{str(trial_list[10])}',
                               '{trial_list[11]}'
                               );
                    ''')
        self.db_conn_dir.commit()
        self.label_trial_info.setText(
            f'Session Info\nTotal Trials: {trial_list[0]} | Correct Trials: {trial_list[8]} | Score: {trial_list[8] / trial_list[0]}\nTrial Info\ntrial num: {trial_list[0]} | time: {trial_list[4]:.3f} | errors: {trial_list[5]}')

    def update_session_table_video_thd(self, session_var_list):
        self.db_cursor.execute(f'''
            UPDATE session
            SET coordinate_history_file = '{session_var_list[0]}',
                video_file = '{session_var_list[1]}'
            WHERE
                session_id = {session_var_list[2]};
        ''')
        self.db_conn_dir.commit()

    def update_session_table_control_thd(self, session_var_list):
        self.db_cursor.execute(
            f'''
                UPDATE session
                SET session_event_history_file = '{session_var_list[0]}',
                    total_trials = '{session_var_list[1]}',
                    total_perfect = '{session_var_list[2]}',
                    score = '{session_var_list[3]}',
                    total_errors = '{session_var_list[4]}',
                    total_switches = '{session_var_list[5]}',
                    average_errors = '{session_var_list[6]}',
                    session_duration = '{session_var_list[7]}'
                WHERE session_id = {session_var_list[8]};
            ''')
        self.db_conn_dir.commit()

    def update_subject_table_control_thd(self, session_var_list):
        self.db_cursor.execute(
            f'''
                UPDATE subjects
                SET last_session = '{session_var_list[0]}'
                WHERE subject_id = {int(session_var_list[1])};
            ''')
        self.db_conn_dir.commit()
        del self.subjects_model
        self.subjects_model = SubjectsModel()
        self.subjects_table.setModel(self.subjects_model.model)
        self.subjects_table.selectionModel().selectionChanged.connect(self.get_subject_idx)
        self.subjects_table.resizeColumnsToContents()
        self.subjects_table.resizeRowsToContents()
        self.subjects_table.horizontalHeader().setStretchLastSection(True)
        self.subjects_table.horizontalHeader().setFont(QFont('Ariel', 10))
        self.subjects_table.verticalHeader().setVisible(False)
        delegate_align_center = AlignCenterDelegate(self.subjects_table)
        for i in range(7):
            self.subjects_table.setItemDelegateForColumn(i, delegate_align_center)
        column_widths = (30, 60, 40, 230, 70, 50, 50)
        for idx, column_widths in enumerate(column_widths[:7]):
            self.subjects_table.setColumnWidth(idx, column_widths)

    def update_label_current_action(self, action_vector):
        self.label_current_action.setText(
            f'Curr Act: {action_vector}'
        )

    def thread_run_session(self, testing=False):
        self.button_open_stream_session.setEnabled(False)
        self.button_close_stream_session.setEnabled(True)
        self.button_open_video.setEnabled(False)
        self.button_close_video.setEnabled(False)

        self.button_all_barriers_up.setEnabled(False)
        self.button_all_barriers_down.setEnabled(False)
        self.button_pause_session.setEnabled(True)

        self.state_session[0] = 1
        self.update_label_current_action(self.action_vector_list[0])

        self.label_trial_info.setText('Session Info\n\nTrial Info')

        self.sound_control.start_player()
        self.sound_control.play_sound(1)

        # Check if room lights are on and turn on IR lights
        if self.state_room_lights[0] == 0:
            self.control_IR_lights_on()
        elif self.state_room_lights[0] == 1:
            self.control_room_lights_bright_off()
            self.control_IR_lights_on()
        elif self.state_room_lights[0] == 2:
            self.control_room_lights_dim_off()
            self.control_IR_lights_on()

        # If running imaging without IR lights
        sess_type = self.session_general_info['readable_action_vector_list'][0][9]
        run_dark = False

        if run_dark:
            if 'Imaging' in sess_type:
                self.control_IR_lights_off()


        # Check if cue displays are running
        if self.state_cue_display[0] == 0:
            self.control_connect_display()
            time.sleep(1)

        # Check if basic video is running if so quit it and start recording
        if self.state_video[0] == 1:
            self.thread_close_video()
            time.sleep(1)

        # Cut power to monitors so rats are put in complete darkness
        #self.control_display_power_off()

        # if no testing add session to database
        if not testing:
            # Get directory values for session files
            name = self.session_general_info['subject_name']
            session_num = self.session_general_info['session_number']
            sess_date = self.session_general_info['date'].replace('/', '')
            behavior = self.session_general_info['behavior']
            sess_type = self.session_general_info['readable_action_vector_list'][0][9]
            dt_date = datetime.datetime.today()
            sess_time = str(dt_date.hour).zfill(2) + str(dt_date.minute).zfill(2) + str(dt_date.second).zfill(2)
            if behavior == 'Landmark Guided Task':
                dir_name = (name + '_' + sess_type + '_' + session_num +
                            '_' + sess_date + '_' + sess_time)
                dir_parent = '/media/blairlab/WD_BLACK/Maze Control Data/Session Data/LGT Data'
                path_to_dir = os.path.join(dir_parent, dir_name)
            elif behavior == 'Path Integration Guided Task':
                dir_name = (name + '_' + sess_type + '_' + session_num +
                            '_' + sess_date + '_' + sess_time)
                dir_parent = '/media/blairlab/WD_BLACK/Maze Control Data/Session Data/PGT Data'
                path_to_dir = os.path.join(dir_parent, dir_name)
            else:
                dir_name = (name + '_' + 'Test' + '_' + session_num +
                            '_' + sess_date + '_' + sess_time)
                dir_parent = '/media/blairlab/WD_BLACK/Maze Control Data/Session Data/TestFolder'
                path_to_dir = os.path.join(dir_parent, dir_name)

            os.makedirs(path_to_dir)
            # Add session instance to database
            self.session_general_info['session_id'] = self.db_cursor.execute(
                f'''
                    INSERT INTO session (session_number, date, time, behavior, cue_conf, session_type, seed, subject_id)
                    VALUES('{self.label_session_number_data.text()}',
                           '{self.label_session_date_data.text()}',
                           '{self.label_session_time_data.text()}',
                           '{self.label_behavior_data.text()}',
                           '{self.label_cue_conf_data.text()}',
                           '{self.label_session_type.text()}',
                           {int(self.label_session_seed_data.text())},
                           '{self.label_subject_id_data.text()}');
                ''').lastrowid
            self.db_conn_dir.commit()

            self.thread_run_session_video(path_to_dir, testing)
            time.sleep(4)

            presession_start = time.time()
            self.db_cursor.execute(
                f'''
                    INSERT INTO session_event (action_vector_idx, action_vector_type, frame, time_stamp, zone,
                                   x_coordinate, y_coordinate, time_duration, start_arm, goal_location,
                                   cue_orientation, session_id)
                    VALUES(0,
                           'Presession',
                           0,
                           0,
                           {self.video_coordinate_stream[0]},
                           {self.video_coordinate_stream[1]},
                           {self.video_coordinate_stream[2]},
                           {time.time() - presession_start},
                           '{self.session_general_info['readable_action_vector_list'][0][4]}',
                           '{self.session_general_info['readable_action_vector_list'][0][5]}',
                           '{self.session_general_info['readable_action_vector_list'][0][6]}',
                           {self.session_general_info['session_id']});
                ''')
            self.db_conn_dir.commit()
        else:
            path_to_dir = None

        # if testing make sure to start session video that otherwise was started in the not testing condition
        if testing == True:
            self.thread_run_session_video(path_to_dir, testing)
            time.sleep(4)

        # Raise barriers to around starting location session
        intermodbus_sleep_time = 0.050
        # for i in range(16):
        #     if self.action_vector_list[0][i + 3] != self.state_barrier_list[i]:
        #         self.control_actuator(i)
        #         time.sleep(intermodbus_sleep_time)
        self.connect_run_action_vector(self.action_vector_list[0])

        # Raise dialog to put rat on maze and press ok when ready to start the session
        msg = ['Session Start Hold', 'Place rat in starting arm.\nOk to start\nCancel to quit']
        session_running = self.run_session_dialog(msg)
        if not session_running:
            self.worker_trsv.thread_running = False
            self.state_session[0] = 0
            self.state_session_video[0] = 0
            self.mp_stop_sound_process()
            self.button_open_video.setEnabled(True)
            self.button_close_video.setEnabled(False)
            self.button_close_stream_session.setEnabled(False)
            self.button_open_stream_session.setEnabled(True)
            self.button_all_barriers_up.setEnabled(True)
            self.button_all_barriers_down.setEnabled(True)
            self.button_pause_session.setEnabled(False)
            return
        #self.control_display_power_on()
        self.session_start_time_offset = self.worker_trsv.session_video_offset_time
        self.thread_run_session_control(path_to_dir, testing)

    def thread_run_session_video(self, path_to_dir, testing):
        # let main_window know video is running
        self.state_session_video[0] = 1

        self.button_open_video.setEnabled(False)
        self.button_close_video.setEnabled(False)
        self.button_close_stream_session.setEnabled(True)

        # trv: thread_run_video
        self.thread_trsv = QThread()
        self.worker_trsv = WorkerSessionVideoThread(self.session_general_info,
                                                    int(self.line_edit_fps.text()),
                                                    int(self.line_edit_shutter_speed.text()),
                                                    int(self.line_edit_iso.text()),
                                                    int(self.line_edit_varThreshold.text()),
                                                    path_to_dir, testing)
        self.worker_trsv.moveToThread(self.thread_trsv)

        self.worker_trsv.update_image.connect(self.display_video)
        self.worker_trsv.update_coordinates.connect(self.update_label_session)
        self.worker_trsv.db_session_video.connect(self.update_session_table_video_thd)
        self.thread_trsv.started.connect(self.worker_trsv.run)
        self.worker_trsv.finished.connect(self.thread_trsv.quit)
        self.worker_trsv.finished.connect(self.worker_trsv.deleteLater)
        self.thread_trsv.finished.connect(self.thread_trsv.deleteLater)

        self.thread_trsv.start()

        self.label_state_video.setText('Video: Running')

        self.thread_trsv.finished.connect(
            lambda: self.button_open_video.setEnabled(True)
        )
        self.thread_trsv.finished.connect(
            lambda: self.button_close_video.setEnabled(False)
        )
        self.thread_trsv.finished.connect(
            lambda: self.label_state_video.setText('Video: Idle')
        )

    def thread_run_session_control(self, path_to_dir, testing):
        self.thread_trsc = QThread()
        self.worker_trsc = WorkerSessionControlThread(self.session_general_info, self.state_list,
                                                      self.session_event_stream_LGT,
                                                      path_to_dir, testing)
        self.worker_trsc.moveToThread(self.thread_trsc)

        self.thread_trsc.started.connect(self.worker_trsc.run)
        self.worker_trsc.finished.connect(self.thread_trsc.quit)
        self.worker_trsc.finished.connect(self.worker_trsc.deleteLater)
        self.thread_trsc.finished.connect(self.thread_trsc.deleteLater)

        self.worker_trsc.update_vector_lists.connect(self.connect_update_action_vectors)
        self.worker_trsc.db_session_event.connect(self.update_session_event_table_control_thd)
        self.worker_trsc.db_session.connect(self.update_session_table_control_thd)
        self.worker_trsc.db_subject_update.connect(self.update_subject_table_control_thd)
        self.worker_trsc.barrier_index.connect(self.control_actuator)
        self.worker_trsc.cue_index.connect(self.control_cue)
        self.worker_trsc.reward_index.connect(self.control_syringe_pump)
        self.worker_trsc.cue_light_index.connect(self.control_cue_light)
        self.worker_trsc.update_label_action.connect(self.update_label_current_action)
        self.worker_trsc.trigger_action_vector.connect(self.connect_run_action_vector)
        self.worker_trsc.trigger_actuators.connect(self.connect_control_actuators)
        self.worker_trsc.db_trial_update.connect(self.update_trial_table_control_thd)
        self.worker_trsc.trigger_cue.connect(self.connect_run_cue)
        self.worker_trsc.trigger_pause.connect(self.pause_session_dialog)

        self.thread_trsc.start()
        self.label_state_video.setText('Video: Running')
        # self.thread_trsc.finished.connect(
        #     lambda: self.control_cue(4))
        self.thread_trsc.finished.connect(self.thread_close_session)
        self.thread_trsc.finished.connect(
            lambda: self.label_state_video.setText('Video: Idle')
        )

    def connect_update_action_vectors(self, vector_list, vector_read):
        self.action_vector_list = vector_list
        self.action_vector_list_readable = vector_read
        self.session_general_info['readable_action_vector_list'] = self.action_vector_list_readable
        self.session_general_info['action_vector_list'] = self.action_vector_list
        del self.action_vec_table_model
        self.action_vec_table_model = TableStaticModel(
            self.action_vector_list_readable_header,
            self.action_vector_list_readable)
        self.action_vec_table.setModel(self.action_vec_table_model)
        self.action_vec_table.selectionModel().selectionChanged.connect(self.get_action_vector_idx)
        self.action_vec_table.resizeRowsToContents()
        self.action_vec_table.setColumnHidden(9, True)

    def connect_run_cue(self, action_vector):
        for i, av in enumerate(action_vector[19:23]):
            if i == 0 and av == 1:
                cue_index = 0
                break
            elif i == 1 and av == 1:
                cue_index = 1
                break
            elif i == 2 and av == 1:
                cue_index = 2
                break
            elif i == 3 and av == 1:
                cue_index = 3
                break
            else:
                cue_index = 4
        if self.state_cue_list[cue_index] == 0:
            time.sleep(0.250)
            self.control_cue(cue_index)

    # Added change here to account for cue on during ITI and off during pretrial
    def connect_run_action_vector(self, action_vector):
        # 1) Check if reward needs to be delivered if so give it first!
        if action_vector[0] in [4, 5]:
            for i, av in enumerate(action_vector[23:27]):
                if av == 1:
                    self.control_syringe_pump(i)
                    break

        # 2) Change barrier configurations
        # Check barrier states and emit signal to actuator control
        # Shift indexes such that barriers close right behind animal
        # when pretrial configuration (2) action happens.
        # Check if pretrial in east start arm (also this condition is ok
        # for changing barriers at any other condition, except reward
        # when barrier configuration is ignored).
        if (action_vector[0] == 2 and action_vector[1] == 15 or
            action_vector[0] == 2 and action_vector[1] == 11 or
                action_vector[0] in [0,1,3,6]):
            for i in range(16):
                if action_vector[i + 3] != self.state_barrier_list[i]:
                    self.control_actuator(i)
        # Check if pretrial in north start arm
        elif action_vector[0] == 2 and action_vector[1] == 12:
            indexes = [(i + 3) % 16 for i in range(16)]
            for i in indexes:
                if action_vector[i + 3] != self.state_barrier_list[i]:
                    self.control_actuator(i)
        # Check if pretrial in east start arm
        elif action_vector[0] == 2 and action_vector[1] == 7:
            indexes = [(i + 6) % 16 for i in range(16)]
            for i in indexes:
                if action_vector[i + 3] != self.state_barrier_list[i]:
                    self.control_actuator(i)
        # Check if pretrial in south start arm
        elif action_vector[0] == 2 and action_vector[1] == 10:
            indexes = [(i + 9) % 16 for i in range(16)]
            for i in indexes:
                if action_vector[i + 3] != self.state_barrier_list[i]:
                    self.control_actuator(i)
        else:
            # passing on pretrial conditions
            pass

        # 3) Change cue configuration (Don't do anychange ITI action_vector[0] == 1
        # Case 1: Fist get the cue config action vector 2 to display cue when maze starts
        # up and rat is put in environment.
        if (action_vector[0] == 0 or action_vector[0] == 1) and \
                self.session_general_info['session_type'] == 'Diff LGT Cue ITI 1':
            first_cue_config = self.action_vector_list[1][19:23]
            for i, av in enumerate(first_cue_config):
                if i == 0 and av == 1:
                    cue_index = 0
                    break
                elif i == 1 and av == 1:
                    cue_index = 1
                    break
                elif i == 2 and av == 1:
                    cue_index = 2
                    break
                elif i == 3 and av == 1:
                    cue_index = 3
                    break
                else:
                    cue_index = 4
            if self.state_cue_list[cue_index] == 0:
                time.sleep(0.250)
                self.control_cue(cue_index)
        # Case 2: Turn cue off for pretrial
        elif action_vector[0] == 2 and self.session_general_info['session_type'] == 'Diff LGT Cue ITI 1':
            for i, av in enumerate([0, 0, 0, 0]):
                if i == 0 and av == 1:
                    cue_index = 0
                    break
                elif i == 1 and av == 1:
                    cue_index = 1
                    break
                elif i == 2 and av == 1:
                    cue_index = 2
                    break
                elif i == 3 and av == 1:
                    cue_index = 3
                    break
                else:
                    cue_index = 4
            if self.state_cue_list[cue_index] == 0:
                time.sleep(0.250)
                self.control_cue(cue_index)
        elif action_vector[0] == 0 or action_vector[0] == 1 or action_vector[0] == 2:
            for i, av in enumerate(action_vector[19:23]):
                if i == 0 and av == 1:
                    cue_index = 0
                    break
                elif i == 1 and av == 1:
                    cue_index = 1
                    break
                elif i == 2 and av == 1:
                    cue_index = 2
                    break
                elif i == 3 and av == 1:
                    cue_index = 3
                    break
                else:
                    cue_index = 4
            if self.state_cue_list[cue_index] == 0:
                time.sleep(0.250)
                self.control_cue(cue_index)

    def connect_control_actuators(self, actuator_list):
        for i in actuator_list:
            self.control_actuator(i)

    def thread_close_session(self):
        self.sound_control.stop_player()
        time.sleep(1)
        self.worker_trsc.thread_open_session = False
        self.worker_trsv.thread_running = False
        self.state_session[0] = 0
        self.state_session_video[0] = 0
        self.state_session_control[0] = 0
        self.session_start_time_offset = 0
        self.control_IR_lights_off()
        self.control_room_lights_dim_on()
        self.button_open_video.setEnabled(True)
        self.button_close_video.setEnabled(False)
        self.button_close_stream_session.setEnabled(False)
        self.button_open_stream_session.setEnabled(True)
        self.button_all_barriers_up.setEnabled(True)
        self.button_all_barriers_down.setEnabled(True)
        self.button_pause_session.setEnabled(False)

    def control_actuator(self, list_index):
        i = list_index
        if self.state_barrier_list[i] == 0:
            self.button_barrier_list[i].setStyleSheet("background-color : Peru")
            self.button_barrier_list[i].setText(f'{self.actuator_parameters[i][0]}\nUP')
            self.state_barrier_list[i] = 1
            self.modbus_actuator_list[i].move_up(255, self.actuator_parameters[i][1], 1, 300)
        elif self.state_barrier_list[i] == 1:
            self.button_barrier_list[i].setStyleSheet("background-color : Khaki")
            self.button_barrier_list[i].setText(f'{self.actuator_parameters[i][0]}\nDWN')
            self.state_barrier_list[i] = 0
            self.modbus_actuator_list[i].move_down(255, self.actuator_parameters[i][2], 1, 300)

    def update_actuator_parameters(self, list_index):
        self.modbus_actuator_list[list_index].update_parameters(255, self.actuator_parameters[i][1],
                                                                self.actuator_parameters[i][2], 1, 250)

    def control_syringe_pump(self, index):
        self.modbus_syringe_pump_list[index].deliver_reward(self.syringe_pump_parameters[index][1],
                                                            self.syringe_pump_parameters[index][2],
                                                            self.syringe_pump_parameters[index][3],
                                                            self.syringe_pump_parameters[index][4])

    def control_cue_light_pulse(self, index):
        if self.state_cue_light_list[index] == 0:
            self.modbus_cue_light_list[index].turn_on_pulse()
            self.button_cue_light_list[index].setStyleSheet('background-color: Violet')
            self.button_cue_light_list[index].setText(f'UV{index + 1}\nON')
            self.state_cue_light_list[index] = 1
        elif self.state_cue_light_list[index] == 1:
            self.modbus_cue_light_list[index].turn_off()
            self.button_cue_light_list[index].setStyleSheet('background-color: Thistle')
            self.button_cue_light_list[index].setText(f'UV{index + 1}\nOFF')
            self.state_cue_light_list[index] = 0

    def control_cue_light(self, index):
        if self.state_cue_light_list[index] == 0:
            self.modbus_cue_light_list[index].turn_on()
            self.button_cue_light_list[index].setStyleSheet('background-color: Violet')
            self.button_cue_light_list[index].setText(f'UV{index + 1}\nON')
            self.state_cue_light_list[index] = 1
        elif self.state_cue_light_list[index] == 1:
            self.modbus_cue_light_list[index].turn_off()
            self.button_cue_light_list[index].setStyleSheet('background-color: Thistle')
            self.button_cue_light_list[index].setText(f'UV{index + 1}\nOFF')
            self.state_cue_light_list[index] = 0

    def control_cue(self, index):
        # print(index, ' ', self.state_cue_list[index])
        if index == 0 and self.state_cue_list[index] == 0:
            self.monitor_cue.virtualNorthAtTrueNorth()
            self.button_cue_list[0].setText('N CUE\nON')
            self.button_cue_list[0].setStyleSheet('background-color: Lightskyblue')
            self.button_cue_list[1].setText('E CUE\nOFF')
            self.button_cue_list[1].setStyleSheet('background-color: Azure')
            self.button_cue_list[2].setText('S CUE\nOFF')
            self.button_cue_list[2].setStyleSheet('background-color: Azure')
            self.button_cue_list[3].setText('W CUE\nOFF')
            self.button_cue_list[3].setStyleSheet('background-color: Azure')
            self.state_cue_list[0] = 1
            self.state_cue_list[1] = 0
            self.state_cue_list[2] = 0
            self.state_cue_list[3] = 0
            self.state_cue_list[4] = 0
        elif index == 0 and self.state_cue_list[index] == 1:
            self.monitor_cue.blankDisplays()
            self.button_cue_list[index].setText('N CUE\nOFF')
            self.button_cue_list[index].setStyleSheet('background-color: Azure')
            self.state_cue_list[index] = 0
            self.state_cue_list[4] = 1
        elif index == 1 and self.state_cue_list[index] == 0:
            self.monitor_cue.virtualNorthAtTrueEast()
            self.button_cue_list[0].setText('N CUE\nOFF')
            self.button_cue_list[0].setStyleSheet('background-color: Azure')
            self.button_cue_list[1].setText('E CUE\nON')
            self.button_cue_list[1].setStyleSheet('background-color: Lightskyblue')
            self.button_cue_list[2].setText('S CUE\nOFF')
            self.button_cue_list[2].setStyleSheet('background-color: Azure')
            self.button_cue_list[3].setText('W CUE\nOFF')
            self.button_cue_list[3].setStyleSheet('background-color: Azure')
            self.state_cue_list[0] = 0
            self.state_cue_list[1] = 1
            self.state_cue_list[2] = 0
            self.state_cue_list[3] = 0
            self.state_cue_list[4] = 0
        elif index == 1 and self.state_cue_list[index] == 1:
            self.button_cue_list[index].setText('S CUE\nOFF')
            self.button_cue_list[index].setStyleSheet('background-color: Azure')
            self.state_cue_list[index] = 0
            self.state_cue_list[4] = 1
            self.monitor_cue.blankDisplays()
        elif index == 2 and self.state_cue_list[index] == 0:
            self.monitor_cue.virtualNorthAtTrueSouth()
            self.button_cue_list[0].setText('N CUE\nOFF')
            self.button_cue_list[0].setStyleSheet('background-color: Azure')
            self.button_cue_list[1].setText('E CUE\nOFF')
            self.button_cue_list[1].setStyleSheet('background-color: Azure')
            self.button_cue_list[2].setText('S CUE\nON')
            self.button_cue_list[2].setStyleSheet('background-color: Lightskyblue')
            self.button_cue_list[3].setText('W CUE\nOFF')
            self.button_cue_list[3].setStyleSheet('background-color: Azure')
            self.state_cue_list[0] = 0
            self.state_cue_list[1] = 0
            self.state_cue_list[2] = 1
            self.state_cue_list[3] = 0
            self.state_cue_list[4] = 0
        elif index == 2 and self.state_cue_list[index] == 1:
            self.monitor_cue.blankDisplays()
            self.button_cue_list[index].setText('S CUE\nOFF')
            self.button_cue_list[index].setStyleSheet('background-color: Azure')
            self.state_cue_list[index] = 0
            self.state_cue_list[4] = 1
        elif index == 3 and self.state_cue_list[index] == 0:
            self.monitor_cue.virtualNorthAtTrueWest()
            self.button_cue_list[0].setText('N CUE\nOFF')
            self.button_cue_list[0].setStyleSheet('background-color: Azure')
            self.button_cue_list[1].setText('E CUE\nOFF')
            self.button_cue_list[1].setStyleSheet('background-color: Azure')
            self.button_cue_list[2].setText('S CUE\nOFF')
            self.button_cue_list[2].setStyleSheet('background-color: Azure')
            self.button_cue_list[3].setText('W CUE\nON')
            self.button_cue_list[3].setStyleSheet('background-color: Lightskyblue')
            self.state_cue_list[0] = 0
            self.state_cue_list[1] = 0
            self.state_cue_list[2] = 0
            self.state_cue_list[3] = 1
            self.state_cue_list[4] = 0
        elif index == 3 and self.state_cue_list[index] == 1:
            self.monitor_cue.blankDisplays()
            self.button_cue_list[index].setText('S CUE\nOFF')
            self.button_cue_list[index].setStyleSheet('background-color: Azure')
            self.state_cue_list[index] = 0
            self.state_cue_list[4] = 1
        elif index == 4 and self.state_cue_list[index] in [0, 2]:
            self.monitor_cue.blankDisplays()
            self.button_cue_list[0].setText('N CUE\nOFF')
            self.button_cue_list[0].setStyleSheet('background-color: Azure')
            self.button_cue_list[1].setText('E CUE\nOFF')
            self.button_cue_list[1].setStyleSheet('background-color: Azure')
            self.button_cue_list[2].setText('S CUE\nOFF')
            self.button_cue_list[2].setStyleSheet('background-color: Azure')
            self.button_cue_list[3].setText('W CUE\nOFF')
            self.button_cue_list[3].setStyleSheet('background-color: Azure')
            self.state_cue_list[0] = 0
            self.state_cue_list[1] = 0
            self.state_cue_list[2] = 0
            self.state_cue_list[3] = 0
            self.state_cue_list[4] = 1
        elif index == 5 and self.state_cue_list[index] in [0, 1]:
            self.monitor_cue.blankDisplays()
            self.button_cue_list[0].setText('N CUE\nOFF')
            self.button_cue_list[0].setStyleSheet('background-color: Azure')
            self.button_cue_list[1].setText('E CUE\nOFF')
            self.button_cue_list[1].setStyleSheet('background-color: Azure')
            self.button_cue_list[2].setText('S CUE\nOFF')
            self.button_cue_list[2].setStyleSheet('background-color: Azure')
            self.button_cue_list[3].setText('W CUE\nOFF')
            self.button_cue_list[3].setStyleSheet('background-color: Azure')
            self.state_cue_list[0] = 0
            self.state_cue_list[1] = 0
            self.state_cue_list[2] = 0
            self.state_cue_list[3] = 0
            self.state_cue_list[4] = 2

    def control_connect_display(self):
        self.monitor_cue.launchStimulusDisplay()
        self.button_connect_display.setEnabled(False)
        self.button_disconnect_display.setEnabled(True)
        self.state_cue_display[0] = 1
        self.state_cue_list[4] = 0

    def control_disconnect_display(self):
        self.monitor_cue.exitScript()
        self.button_disconnect_display.setEnabled(False)
        self.button_connect_display.setEnabled(True)
        self.state_cue_display[0] = 0
        self.state_cue_list[:5] = [0, 0, 0, 0, 0]
        self.button_cue_list[0].setText('N CUE\nOFF')
        self.button_cue_list[0].setStyleSheet('background-color: Azure')
        self.button_cue_list[1].setText('E CUE\nOFF')
        self.button_cue_list[1].setStyleSheet('background-color: Azure')
        self.button_cue_list[2].setText('S CUE\nOFF')
        self.button_cue_list[2].setStyleSheet('background-color: Azure')
        self.button_cue_list[3].setText('W CUE\nOFF')
        self.button_cue_list[3].setStyleSheet('background-color: Azure')

    def control_display_power_on(self):
        self.monitor_cue.turn_on_signal_power()

    def control_display_power_off(self):
        self.monitor_cue.turn_off_signal_power()

    def control_room_lights_bright_on(self):

        self.modbus_room_lights.turn_on(int(self.line_edit_lights.text()))
        time.sleep(0.25)
        self.monitor_cue.whiteDisplays()
        self.button_room_lights_ON.setEnabled(False)
        self.button_dim_lights_ON.setEnabled(False)
        self.button_room_lights_OFF.setEnabled(True)
        self.state_cue_list[:5] = [0, 0, 0, 0, 1]
        self.button_cue_list[0].setText('N CUE\nOFF')
        self.button_cue_list[0].setStyleSheet('background-color: Azure')
        self.button_cue_list[1].setText('E CUE\nOFF')
        self.button_cue_list[1].setStyleSheet('background-color: Azure')
        self.button_cue_list[2].setText('S CUE\nOFF')
        self.button_cue_list[2].setStyleSheet('background-color: Azure')
        self.button_cue_list[3].setText('W CUE\nOFF')
        self.button_cue_list[3].setStyleSheet('background-color: Azure')

        self.state_room_lights[0] = 1

    def control_room_lights_bright_off(self):
        self.modbus_room_lights.turn_off()
        time.sleep(0.25)
        self.monitor_cue.blankDisplays()
        self.button_room_lights_OFF.setEnabled(False)
        self.button_room_lights_ON.setEnabled(True)
        self.button_dim_lights_ON.setEnabled(True)
        self.state_cue_list[:5] = [0, 0, 0, 0, 0]
        self.button_cue_list[0].setText('N CUE\nOFF')
        self.button_cue_list[0].setStyleSheet('background-color: Azure')
        self.button_cue_list[1].setText('E CUE\nOFF')
        self.button_cue_list[1].setStyleSheet('background-color: Azure')
        self.button_cue_list[2].setText('S CUE\nOFF')
        self.button_cue_list[2].setStyleSheet('background-color: Azure')
        self.button_cue_list[3].setText('W CUE\nOFF')
        self.button_cue_list[3].setStyleSheet('background-color: Azure')

        self.state_room_lights[0] = 0

    def control_room_lights_dim_on(self):
        self.modbus_room_lights.turn_off()
        time.sleep(0.25)
        self.monitor_cue.grey_displays()
        self.button_dim_lights_ON.setEnabled(False)
        self.button_room_lights_ON.setEnabled(False)
        self.button_dim_lights_OFF.setEnabled(True)
        self.state_cue_list[:5] = [0, 0, 0, 0, 2]
        self.button_cue_list[0].setText('N CUE\nOFF')
        self.button_cue_list[0].setStyleSheet('background-color: Azure')
        self.button_cue_list[1].setText('E CUE\nOFF')
        self.button_cue_list[1].setStyleSheet('background-color: Azure')
        self.button_cue_list[2].setText('S CUE\nOFF')
        self.button_cue_list[2].setStyleSheet('background-color: Azure')
        self.button_cue_list[3].setText('W CUE\nOFF')
        self.button_cue_list[3].setStyleSheet('background-color: Azure')

        self.state_room_lights[0] = 2

    def control_room_lights_dim_off(self):
        self.modbus_room_lights.turn_off()
        time.sleep(0.25)
        self.monitor_cue.blankDisplays()
        self.button_dim_lights_OFF.setEnabled(False)
        self.button_room_lights_ON.setEnabled(True)
        self.button_dim_lights_ON.setEnabled(True)
        self.state_cue_list[:5] = [0, 0, 0, 0, 0]
        self.button_cue_list[0].setText('N CUE\nOFF')
        self.button_cue_list[0].setStyleSheet('background-color: Azure')
        self.button_cue_list[1].setText('E CUE\nOFF')
        self.button_cue_list[1].setStyleSheet('background-color: Azure')
        self.button_cue_list[2].setText('S CUE\nOFF')
        self.button_cue_list[2].setStyleSheet('background-color: Azure')
        self.button_cue_list[3].setText('W CUE\nOFF')
        self.button_cue_list[3].setStyleSheet('background-color: Azure')

        self.state_room_lights[0] = 0

    def control_IR_lights_on(self):
        self.modbus_room_lights.turn_on_IR(int(self.line_edit_IR_lights.text()))
        self.button_IR_lights_ON.setEnabled(False)
        self.button_IR_lights_OFF.setEnabled(True)
        self.state_IR_lights[0] = 1

    def control_IR_lights_off(self):
        self.modbus_room_lights.turn_off_IR()
        self.button_IR_lights_ON.setEnabled(True)
        self.button_IR_lights_OFF.setEnabled(False)
        self.state_IR_lights[0] = 0

    def closeEvent(self, event):
        self.db_connection.close()
        if self.state_session[0] == 1:
            self.thread_close_session()
        if self.state_video[0] == 1:
            self.thread_close_video()
        if self.state_cue_display[0] == 1:
            self.control_disconnect_display()
            time.sleep(0.250)
        if self.state_IR_lights[0] == 1:
            self.control_IR_lights_off()

        with open('actuator_parameters.json', 'w', encoding='utf-8') as f:
            json.dump(self.actuator_parameters, f, ensure_ascii=False, indent=4)
        with open('syringe_pump_parameters_list_30ml.json', 'w', encoding='utf-8') as f:
            json.dump(self.syringe_pump_parameters_list, f, ensure_ascii=False, indent=4)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec_())
