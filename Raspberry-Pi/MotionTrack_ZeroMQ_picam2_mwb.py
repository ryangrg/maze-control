#!/usr/bin/env/
import numpy as np
import picamera2
import cv2
import time
from libcamera import controls
import sys
import threading
import multiprocessing as mp, ctypes
import signal
import os
import select
import zmq
import msgpack
import msgpack_numpy as m
#import ntplib

# Get PID number
PID = os.getpid()

# Global variable to stop sending images and close script when set to false once sendImage_live
# starts it's while loop sending images
send_images = False

def return_zone(x,y):
    #Reward 3
    if 0 <= x <= 47 and 0 <= y <= 47 and x <= (47-y):
        return 1
    elif 43 <= x <= 97 and 0 <= y <= 35:
        return 2
    elif 98 <= x <= 138 and 0 <= y <= 35:
        return 3
    elif 139 <= x <= 194 and 0 <= y <= 35:
        return 4
    #Reward 2
    elif 193 <= x <= 239 and 0 <= y <= 47 and (x-193) >= y:
        return 5
    elif 0 <= x <= 34 and 45 <= y <= 100:
        return 6
    elif 96 <= x <= 138 and 36 <= y <= 96:
        return 7
    elif 205 <= x <= 239 and 41 <= y <= 97:
        return 8
    elif 0 <= x <= 34 and 101 <= y <= 139:
        return 9
    elif 35 <= x <= 95 and 103 <= y <= 137:
        return 10
    elif 96 <= x <= 143 and 97 <= y <= 142:
        return 11
    elif 144 <= x <= 204 and 98 <= y <= 139:
        return 12
    elif 205 <= x <= 239 and 98 <= y <= 139:
        return 13
    elif 0 <= x <= 34 and 140 <= y <= 196:
        return 14
    elif 102 <= x <= 137 and 143 <= y <= 204:
        return 15
    elif 205 <= x <= 239 and 140 <= y <= 195:
        return 16
    #reward 4
    elif 0 <= x <= 46 and 194 <= y <= 239 and x <= (y-194):
        return 17
    elif 43 <= x <= 97 and 205 <= y <= 239:
        return 18
    elif 98 <= x <= 139 and 205 <= y <= 239:
        return 19
    elif 140 <= x <= 195 and 205 <= y <= 239:
        return 20
    #reward 1
    elif 192 <= x <= 239 and 192 <= y <= 239 and (x-192) >= (239-y):
        return 21
    else:
        return 0
    
def set_run_state(run_state):
    print('run set_run_state')
    PORT_REP = 5101
    #run_state = run_state.value

    context = zmq.Context.instance()
    server_rep = context.socket(zmq.REP)
    server_rep.bind(f'tcp://*:{PORT_REP}')
    
    # get start message and reply with PID
    msg = server_rep.recv_string()
    if msg == 'Start':
        run_state.set()
        print('set run_state')
        server_rep.send_string(str(PID))
        print(f'Starting Video stream with PID: {PID}') 
    else:
        server_rep.send_string('Closing Video: Wrong start message sent')
        sys.exit()
    
    # wait for a second for subscriber to start recv() before sending
    time.sleep(2)
    
    # wait for end message
    while run_state.is_set():
        msg = server_rep.recv_string()
        if msg == 'Stop':
            server_rep.send_string('Closing Video')
            run_state.clear()
        else:    
            server_rep.send_string("Send 'Stop' to close video")
            
def sendImage_live(sys, send_data, send_flag, send_size, end_flag, start_time):
    print('Enter sendImage_live')
    PORT_PUB = 5102
    
    context = zmq.Context.instance()
    server_pub = context.socket(zmq.PUB)
    server_pub.bind(f'tcp://*:{PORT_PUB}')
    
    start_wait = True
    run_state = mp.Event()
    
    # start thread here to check for run_state    
    run_state_thread = threading.Thread(target=set_run_state, args=(run_state,))
    run_state_thread.start()
    print('Enter wait loop to send video')
    # Wait loop that waits for send_images to be set to True before while loop executes
    while start_wait:
        if not run_state.is_set():
            time.sleep(0.1)
        else:
            start_wait = False
            break
    print('Exiting wait loop starting to send video')
    while run_state.is_set():
        if send_flag.value == 0:
            send_image = np.frombuffer(send_data.get_obj(),dtype='uint8').reshape(send_size)
            try:
                encoded_image = msgpack.packb(send_image, default=m.encode)
                server_pub.send(encoded_image)
                send_flag.value = 1
                #print('____socket sent ' + str(time.time()-start_time.value))
            except IOError as e:
                print(e)
                break
    
    run_state_thread.join()
    end_flag.value = 1
    print('Stopping sending images')
    
def processImage(process_data, sys, process_size, end_flag,img_lock,
                 timestamp,send_data,send_size,send_flag,start_time):
    print('running process Image')
    #preapre for motion detection
    try:
        back_sub = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=int(sys.argv[2]), detectShadows=False)
    except IndexError:
        back_sub = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=int(200), detectShadows=False)
    kernel = np.ones((20,20), np.uint8)
    
    #initialize data
    x_center=120
    y_center=120
    zone = 11
    time_stamp = None
    step = 0
    black=(0,0,0)
    image_process = np.zeros(process_size,dtype=np.uint8)
    
    #new masks here
    c1 = np.array([[92,0], [92,52], [113,52], [113,41], [126,41], [126,53], [145,53], [145,0], [137,0],
                   [137,16], [101,16], [101,0]])
    c2 = np.array([[187,92], [239,92], [239,101], [223,101], [223,138], [239,138], [239,146], [187,146],
                   [187,126], [199,126], [199,113], [187,113]])
    c3 = np.array([[92,186], [114,186], [114,198], [126,198], [126,186], [147,186], [147,239], [137,239],
                   [137,221], [100,221], [100,239], [92,239]])
    c4 = np.array([[0,93], [52,93], [52,112], [43,112], [43,126], [53,126], [53,147], [0,147], [0,137],
                   [17,137], [17,102], [0,102]])
    c5 = np.array([[89,89], [152,89], [152,152], [127,152], [127,127], [142,127], [142,113], [127,113],
                   [127,98], [114,98], [114,113], [99,113], [99,127], [113, 127], [113,141], [127,141],
                   [127,141], [127,152], [89,152]])
    c6 = np.array([[115,0], [120,0], [120,7], [115,7]])
    c7 = np.array([[232,117], [239,117], [239,121], [232,121]])
    c8 = np.array([[115,232], [121,232], [121,239], [115,239]])
    c9 = np.array([[0,117], [8,117], [8,122], [0,122]])
    
    while end_flag.value == 0:
        if img_lock.value == 0:
            #print('__opencv start ' + str(time.time()-start_time.value))
            # get the image in buffer
            send_image = np.frombuffer(send_data.get_obj(),dtype='uint8').reshape(send_size)
            image_process = np.frombuffer(process_data.get_obj(),dtype='uint8').reshape(process_size)
            time_stamp = int(timestamp.value*1000) #time since start_time, unit=ms
            
            step+=1
            s4 = int(step/1000000)
            s3 = int(step%1000000/10000)
            s2 = int(step%10000/100)
            s1 = int(step%100)
            ts4 = int(time_stamp/1000000)
            ts3 = int(time_stamp%1000000/10000)
            ts2 = int(time_stamp%10000/100)
            ts1 = int(time_stamp%100)
            
            cv2.fillPoly(image_process, pts=[c1], color=black)
            cv2.fillPoly(image_process, pts=[c2], color=black)
            cv2.fillPoly(image_process, pts=[c3], color=black)
            cv2.fillPoly(image_process, pts=[c4], color=black)
            cv2.fillPoly(image_process, pts=[c6], color=black)
            cv2.fillPoly(image_process, pts=[c7], color=black)
            cv2.fillPoly(image_process, pts=[c8], color=black)
            cv2.fillPoly(image_process, pts=[c9], color=black)
            
            #southwest square
            cv2.rectangle(image_process,(29,32),(114,113),black,-1)
            #northwest square
            cv2.rectangle(image_process,(126,29),(207,113),black,-1)
            #southeast
            cv2.rectangle(image_process,(30,126),(114,208),black,-1)
            #northeast
            cv2.rectangle(image_process,(126,126),(209,209),black,-1)
            
            cv2.fillPoly(image_process, pts=[c5], color=black)
            
            fg_mask = back_sub.apply(image_process)
            fg_mask = cv2.morphologyEx(fg_mask,cv2.MORPH_CLOSE,kernel)
            fg_mask = cv2.medianBlur(fg_mask,5)

            _, fg_mask = cv2.threshold(fg_mask, 127, 255, cv2.THRESH_BINARY)
            contours, hierarchy = cv2.findContours(fg_mask,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)[-2:]
            areas = [cv2.contourArea(c) for c in contours]
            
            #if no area is detected use the previous position
            
            if len(areas)<1 or len(areas)>3:
                zone = return_zone(x_center, y_center)
                send_image[0:11,0,0]=[s1, s2, s3, s4, ts1, ts2, ts3, ts4, x_center, y_center, zone]
                #print(sys.getsizeof(data))
                np.copyto(send_data_np,send_image)
                send_flag.value = 0
                img_lock.value = 1
                #print('__opencv finish ' + str(time.time()-start_time.value))
                continue
            else:
                max_index = np.argmax(areas)
            
            
            cnt = contours[max_index]
            x,y,w,h = cv2.boundingRect(cnt)
            x_center = x + int(w/2)
            y_center = y + int(h/2)
            
            zone = return_zone(x_center, y_center)
            send_image[0:11,0,0]=[s1, s2, s3, s4, ts1, ts2, ts3, ts4, x_center, y_center, zone]
            np.copyto(send_data_np,send_image)
            send_flag.value = 0
            img_lock.value = 1            
            #print('__opencv finish ' + str(time.time()-start_time.value))
    time.sleep(5)
    print('opencv process ends')
    
    
if __name__ == '__main__':
      
    try:
        fps = int(sys.argv[1])
    except IndexError:
        fps = int(30)
    print('fps: ', fps)
    frameDur = tuple(map(int,[int(1000000/fps),int(1000000/fps)]))
    
    try:
        send_res = tuple(map(int,[sys.argv[3],sys.argv[4]]))
    except IndexError:
        send_res = (480,480)
    print('sent frames res: ' + str(send_res) + ' ' + str(type(send_res)))
    
    try:
        iso = int(sys.argv[5])
    except IndexError:
        iso = 800
    print('iso: ', iso)
    
    try:
        shutter_speed = int(sys.argv[6])
    except IndexError:
        shutter_speed = 8000
    print('shutter speed: ', shutter_speed)
    
    send_size = send_res + (3,) #size of sent frame
    
    process_size = (240,240,3) #size of motion tracking frame
    process_res = (240,240)
    
    #open camera connection and set configuration
    camera = picamera2.Picamera2()
    config = camera.create_video_configuration(main={"size":send_res,"format":'RGB888'},
                                               lores={"size":process_res},buffer_count=6)
    camera.configure(config)
#     camera.set_controls({"Brightness":0.1,"ExposureTime":shutter_speed, "AwbEnable": False,
#                          "AwbMode": controls.AwbModeEnum.Custom, "ColourGains": (2.0, 2.0), "Saturation": 0,
#                          "FrameDurationLimits":frameDur,"AeEnable":False,"AnalogueGain":int(iso/100)})
    camera.set_controls({"Brightness":0.1,"ExposureTime":shutter_speed, "AwbEnable": False,
                         "AwbMode": controls.AwbModeEnum.Custom,
                         "FrameDurationLimits":frameDur,"AeEnable":False,"AnalogueGain":int(iso/100)})
    camera.start()
    time.sleep(2)
    #camera.set_controls({"AwbEnable":False}) #turn off automatic white balance after camera start
    time.sleep(2)

    #create a shared memory object for motion tracking frames
    process_template = np.zeros(process_size,dtype=np.uint8).nbytes
    process_data = mp.Array(ctypes.c_uint8,process_template, lock=True) 
    process_data_np = np.frombuffer(process_data.get_obj(),dtype='uint8').reshape(process_size)
    
    #create a shared memory object for sending frames
    send_template = np.zeros(send_size,dtype=np.uint8).nbytes
    send_data = mp.Array(ctypes.c_uint8,send_template, lock=True) 
    send_data_np = np.frombuffer(send_data.get_obj(),dtype='uint8').reshape(send_size)
    
    #create other shared memory objects
    end_flag = mp.Value('i',0) #signal for closing the camera
    img_lock = mp.Value('i',1) #lock for processing the motion tracking images
    timestamp = mp.Value(ctypes.c_double,0) #timestamp of the frames
    send_flag = mp.Value('i',1) #flag for sending the image
    start_time = mp.Value(ctypes.c_double,0)
    
    
    #create processes
    #process for opencv motion track
    print('strating image proccessing process')
    p_process = mp.Process(target=processImage, args=(process_data, sys, process_size, end_flag,img_lock,
                                              timestamp,send_data,send_size,send_flag,start_time)) #create a process for image processing
    p_process.start()
    
    print('starting zmq process')
    #process for np socket
    p_send = mp.Process(target=sendImage_live, args=(sys, send_data, send_flag, send_size, end_flag, start_time))
    try:
        p_send.start()
    except err:
        print(err)
    
    print('starting video')
    
    #get npt synced time
    #c = ntplib.NTPClient()
    #response = c.request('pool.ntp.org',version=3)
    #npt_start_time = response.tx_time+response.delay/2
    
    start_time.value = time.time()
    with open("ntp_start_time.csv","w") as f:
        f.write(f"{start_time.value}")
    while end_flag.value == 0:
        (send_frame, process_frame), metadata = camera.capture_arrays(["main","lores"])
        process_frame = cv2.cvtColor(process_frame, cv2.COLOR_YUV420p2BGR)
        process_frame = process_frame[:,:process_res[1],:] #make the frame square by discarding the empty pixels
        np.copyto(process_data_np, process_frame)
        np.copyto(send_data_np, send_frame)
        
        #response = c.request('pool.ntp.org',version=3)
        timestamp.value = time.time() - start_time.value
        img_lock.value = 0   
    
    camera.close()
    print('camera closed')
    p_process.join()
    p_send.join()
    #os.kill(pid, signal.SIGTERM)

