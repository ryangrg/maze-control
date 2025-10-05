#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue May 18 14:07:15 2021

@author: ryangrgurich
"""
import random
import glob
import time
import pygame
import zmq
import os
import subprocess

testing = False

# Get PID
PID = os.getpid()
print('PID: ', PID)

# Setup zmq context
context = zmq.Context()

# Setup zmq server
server = context.socket(zmq.REP)
server.bind('tcp://*:5001') 

request = server.recv_string()
print(request)
if request == 'Start':
    server.send_string(str(PID))

# Import pygame.locals for easier access to key coordinates
# Updated to conform to flake8 and black standards
from pygame.locals import (
    K_0, K_1, K_2, K_3, K_4,
    K_ESCAPE,
    KEYDOWN,
    RLEACCEL,
    QUIT,
)

#Color constants
GREY_VAL = 113
GREY = [GREY_VAL, GREY_VAL, GREY_VAL]
WHITE = [255, 255, 255]
B_val = 0
BLACK = [B_val,B_val,B_val]

#classes for pygame      
class Stimuli(pygame.sprite.Sprite):
    def __init__(self, *args):
        super(Stimuli, self).__init__()
        if(len(args) == 5):
            #self.surf = pygame.image.load(args[0]).convert_alpha()
            self.processType = args[0]
            self.surf = args[1]
            self.frame_count = 0
            self.frame_index = list(range(len(self.surf)))
            random.shuffle(self.frame_index)
            self.image = self.surf[0]
            self.image.set_colorkey((255, 255, 255), RLEACCEL)
            self.rect = self.image.get_rect(topleft=args[2])
            self.clock1 = 0
            self.ms = args[3]
            self.step = args[4]
        elif(len(args) == 3):
            self.processType = args[3]
            self.surf = pygame.Surface(args[0])
            self.surf.fill(args[1])   
            self.rect = self.surf.get_rect(topleft=[0,0])

    def update(self):
        if self.processType == 1:
            if (pygame.time.get_ticks() - self.clock1)>self.ms:
                if self.frame_count > len(self.surf)-self.step:
                    self.frame_count = 0
                    random.shuffle(self.frame_index)
                self.image = self.surf[self.frame_index[self.frame_count]]
                self.clock1 = pygame.time.get_ticks()
                self.frame_count += self.step
        elif self.processType == 2:
            if(pygame.time.get_ticks()-self.clock1)>self.ms:
                if self.frame_count > len(self.surf)-self.step:
                    self.frame_count = 0
                self.image = self.surf[self.frame_count]
                self.clock1 = pygame.time.get_ticks()
                self.frame_count += self.step
                
# def drawScreen(size):
#     pygame.display.update(size)



#t1 =time.time()
# Initialize pygame
pygame.init()

#hide mouse
pygame.mouse.set_visible(0)

# Define constants for the screen width and height
# Define constants for the screen width and height
SCREEN_WIDTH = pygame.display.Info().current_w
SCREEN_HEIGHT = pygame.display.Info().current_h
#SCREEN_WIDTH = 2560
#SCREEN_HEIGHT = 720

STIM_WIDTH = int(SCREEN_WIDTH/2)
STIM_HEIGHT = SCREEN_HEIGHT

STIM_POS_X = 0
STIM_POS_Y = 0

LeftScreen = True


# Create the screen object
# The size is determined by the constant SCREEN_WIDTH and SCREEN_HEIGHT
if testing == True:
    screen = pygame.display.set_mode((int(SCREEN_WIDTH), SCREEN_HEIGHT))
else:
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT),pygame.FULLSCREEN | pygame.DOUBLEBUF)
    
Path_1 = 'StaticStim/'
Path_2 = 'BallBounce/'

# Files_1 = sorted(glob.glob(Path_1 + 'CircleEdge_L.png'))
# Files_2 = sorted(glob.glob(Path_1 + '*.png'))
Files_2 = sorted(glob.glob(Path_1 + 'EyeI.png'))
Files_1 = sorted(glob.glob(Path_1 + 'TriangleStim.png'))
Files_3 = sorted(glob.glob(Path_1 + 'Bars.png'))

pygameIMGS_1 = []
pygameIMGS_2 = []
pygameIMGS_3 = []

for i in range(0,len(Files_1)):
    pygameIMGS_1.append(pygame.image.load(Files_1[i]).convert_alpha())

for i in range(0, len(Files_2)):
    pygameIMGS_2.append(pygame.image.load(Files_2[i]).convert_alpha())
    
for i in range(0, len(Files_3)):
    pygameIMGS_3.append(pygame.image.load(Files_3[i]).convert_alpha())



# Setup the clock for a decent framerate
clock = pygame.time.Clock()

#stimuli = Stimuli((STIM_WIDTH, STIM_HEIGHT), GREEN, (STIM_WIDTH,0))
stimuliGroup = pygame.sprite.Group()
#static_stimuli = pygame.sprite.Group()
#all_stimuli.add(stimuli)
#print((time.time()-t1))
# Variable to keep the main loop running
running = True
updateAll = True

MS_STIM1 = 10
MS_STIM2 = 10

# Main loop
while running:
    #t1 = time.time()
    # Look at every event in the queue
#     if testing == True:
#         for event in pygame.event.get():
#             # Did the user hit a key?
#             if event.type == KEYDOWN:
#                 # Was it the Escape key? If so, stop the loop.
#                 if event.key == K_ESCAPE:
#                     running = False
#             # Did the user click the window close button? If so, stop the loop.
#             elif event.type == QUIT:
#                 running = False
    
    #time.sleep(.100)
    request = server.recv_string()
    request = int(request)
    
    #All Blank
    if request == 1:
        updateAll = True
        for entity in stimuliGroup:
            entity.kill()
        screen.fill(BLACK)
        server.send_string('1')
    #North on North Config
    elif request == 2:
        LeftScreen = True
        updateAll = True
        for entity in stimuliGroup:
            entity.kill()
        #stimuli_1 = Stimuli(2, pygameIMGS_3, (0,0), MS_STIM1, 1)
        stimuli_2 = Stimuli(2, pygameIMGS_1, (STIM_WIDTH,0), MS_STIM1, 1)
        #stimuliGroup.add(stimuli_1)
        stimuliGroup.add(stimuli_2)
        screen.fill(BLACK)
        server.send_string('2')
    #North on East Config
    elif request == 3:
        LeftScreen = False
        updateAll = True
        for entity in stimuliGroup:
            entity.kill()
        #stimuli_1 = Stimuli(2, pygameIMGS_3, (STIM_WIDTH,0), MS_STIM1, 1)
        stimuli_2 = Stimuli(2, pygameIMGS_1, (0,0), MS_STIM1, 1)
        #stimuliGroup.add(stimuli_1)
        stimuliGroup.add(stimuli_2)
        screen.fill(BLACK)
        server.send_string('3')
    #North on West Config
    elif request == 5:
        LeftScreen = True
        updateAll = True
        for entity in stimuliGroup:
            entity.kill()
        #stimuli_1 = Stimuli(2, pygameIMGS_3,(0,0), MS_STIM2,4)
        #stimuli_2 = Stimuli(2, pygameIMGS_2, (STIM_WIDTH,0), MS_STIM1, 1)
        #stimuliGroup.add(stimuli_1)
        #stimuliGroup.add(stimuli_2)
        screen.fill(BLACK)
        server.send_string('5')
    #North on South Config
    elif request == 4:
        LeftScreen = False
        updateAll = True
        for entity in stimuliGroup:
            entity.kill()
        #stimuli_1 = Stimuli(2, pygameIMGS_3, (STIM_WIDTH,0), MS_STIM2, 4)
        #stimuli_2 = Stimuli(2, pygameIMGS_2, (0,0), MS_STIM1, 1)
        #stimuliGroup.add(stimuli_1)
        #stimuliGroup.add(stimuli_2)
        screen.fill(BLACK)
        server.send_string('4')
    elif request == 6:
        updateAll = True
        for entity in stimuliGroup:
            entity.kill()
        screen.fill(WHITE)
        server.send_string('6')
    elif request == 7: # Grey screen option
        updateAll = True
        for entity in stimuliGroup:
            entity.kill()
        screen.fill(GREY)
        server.send_string('7')
    elif request == 8:
        for entity in stimuliGroup:
            entity.kill()
        server.send_string('8')
        running = False
    elif request == 9: #check if running signal
        server.send_string(f'9 {PID}')
    elif request == 10: # cut signal power to monitors
        cmd = "nohup vcgencmd display_power 0 & exit"
        subprocess.Popen(cmd, shell=True)
        server.send_string('10')
        #print('ran code to kill screen')
    elif request == 11: # start signal power to monitors
        cmd = "nohup vcgencmd display_power 1 & exit"
        subprocess.Popen(cmd, shell=True)
        server.send_string('11')

    # Get the set of keys pressed and check for user input

    #t1 = time.time()
    
    #screen.fill(MIDDLE_GREY)
    #screen.fill(BLACK)
    
    for entity in stimuliGroup:
        screen.blit(entity.image, entity.rect)
    #for entity in static_stimuli:
    #    screen.blit(entity.surf, entity.rect)
    #t1=time.time()
    stimuliGroup.update()
    #t1=time.time()
    # Flip everything to the display
    #pygame.display.flip()
    if updateAll == True:
        pygame.display.flip()
        updateAll = False
    elif LeftScreen==True:
        pygame.display.update(STIM_POS_X, STIM_POS_Y,
                              STIM_WIDTH, STIM_HEIGHT)
        #updateAll = True
        #pygame.display.flip()
    elif LeftScreen==False:
        pygame.display.update(STIM_WIDTH+STIM_POS_X, STIM_POS_Y,
                              STIM_WIDTH, STIM_HEIGHT)
        #updateAll = True
        #pygame.display.flip()
    # Ensure we maintain a 30 frames per second rate
    #print((time.time()-t1)*1000)
    clock.tick(5)

pygame.quit()
server.close()
server.close()
context.term()



