import asyncio
import time
import cv2
import json
import pygame
from cvzone.FaceMeshModule import FaceMeshDetector
from channels.generic.websocket import AsyncWebsocketConsumer
import base64
import warn_music
import numpy as np
import threading
from django.shortcuts import render
from warn_music import play_sound
class BlinkConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cap = None
        self.detector = None
        self.M_blinkCounter = 0
        self.E_blinkCounter = 0
        self.M_counter = 0
        self.E_counter = 0
        self.light=0
        self.a = 0
        self.b = 0
        self.ratioList_M = []
        self.ratioList_L = []
        self.ratioList_R = []
        self.idList_M = [12, 15, 38, 86, 41, 179, 42, 89, 183, 96, 62, 268, 316, 271, 403, 272, 319, 407, 325, 292]
        self.start_time = time.time()  #初始化时间计数器
    @staticmethod
    def adjust_gamma(image, gamma=1.0):
        # 建立查找表：将像素值（0-255）映射到经过伽马调整后的新值
        invGamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** invGamma) * 255 for i in np.arange(256)]).astype("uint8")
        print("调用伽马矫正函数图像增强")

        # 应用查找表来调整图像
        return cv2.LUT(image, table)  # cv2.LUT 是 OpenCV 提供的函数，作用是根据查找表 table 将图像 image 的每个像素值转换为伽马校正后的新像素值。
    def play_audio(self, filename):
        warn_music.play_sound(filename)
    async def connect(self):
        await self.accept()
        try:
            threading.Thread(target=self.play_audio, args=('static/music/Image_processing.mp3',)).start()
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                raise Exception("无法打开摄像头，请检查摄像头是否被占用或权限问题。")
            self.detector = FaceMeshDetector(maxFaces=1)
            fps = 30
            frame_interval = 1 / fps
            while True:
                start_time = cv2.getTickCount()
                success, frame = self.cap.read()
                if not success:
                    raise Exception("无法读取摄像头帧，请检查摄像头是否正常工作。")
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                light = int(gray.mean())
                self.light = light

                if light < 30 and self.b == 0 :
                     # 正确使用 threading.Thread
                    threading.Thread(target=self.play_audio, args=('static/music/Lowlight_remid1.mp3',)).start()
                    self.b = 1

                if light < 25 :
                    frame = self.adjust_gamma(frame, gamma=3.0)

                ret, faces = self.detector.findFaceMesh(frame, draw=False)
                if faces:
                    face = faces[0]
                    self.draw_face_points(frame, face)

                    M_ratio = self.calculate_mouth_ratio(face)
                    self.update_mouth_blink_count(M_ratio)


                    E_ratio = self.calculate_eye_ratio(face)
                    self.update_eye_blink_count(E_ratio)
                    self.justice()
                # 将图像编码为 JPEG 格式
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])  # 降低图像质量以减少数据量
                frame_base64 = base64.b64encode(buffer).decode('utf-8')

                # 发送眨眼计数和视频帧到前端
                data = {
                    'blink_count': self.M_blinkCounter/2,
                    'eye_count': self.E_blinkCounter,
                    'light': self.light,
                    'frame': frame_base64
                }
                await self.send(text_data=json.dumps(data))
                # 计算处理时间并根据帧率调整等待时间
                end_time = cv2.getTickCount()
                elapsed_time = (end_time - start_time) / cv2.getTickFrequency()
                if elapsed_time < frame_interval:
                    await asyncio.sleep(frame_interval - elapsed_time)

        except Exception as e:
            print(f"Error occurred: {e}")
            error_data = {'error': str(e)}
            await self.send(text_data=json.dumps(error_data))
        finally:
            if self.cap:
                self.cap.release()

    def draw_face_points(self, frame, face):
        if 103 < len(face) and 397 < len(face):
            cv2.rectangle(frame, tuple(face[103]), tuple(face[397]), (0, 255, 0), 2)
            corner_length = 15
            x1, y1 = face[103]
            x2, y2 = face[397]
            cv2.line(frame, (x1, y1), (x1 + corner_length, y1), (0, 140, 255), 5)
            cv2.line(frame, (x1, y1), (x1, y1 + corner_length), (0, 140, 255), 5)
            cv2.line(frame, (x2, y1), (x2 - corner_length, y1), (0, 140, 255), 5)
            cv2.line(frame, (x2, y1), (x2, y1 + corner_length), (0, 140, 255), 5)
            cv2.line(frame, (x1, y2), (x1 + corner_length, y2), (0, 140, 255), 5)
            cv2.line(frame, (x1, y2), (x1, y2 - corner_length), (0, 140, 255), 5)
            cv2.line(frame, (x2, y2), (x2 - corner_length, y2), (0, 140, 255), 5)
            cv2.line(frame, (x2, y2), (x2, y2 - corner_length), (0, 140, 255), 5)

    def calculate_mouth_ratio(self, face):
        moth_up = tuple(face[12])
        moth_down = tuple(face[15])
        moth_left = tuple(face[62])
        moth_right = tuple(face[292])
        m_thver, __ = self.detector.findDistance(moth_up, moth_down)
        m_thhor, __ = self.detector.findDistance(moth_left, moth_right)
        ratio = 100 * m_thver / m_thhor
        self.ratioList_M.append(ratio)
        if len(self.ratioList_M) > 10:
            self.ratioList_M.pop(0)
        return sum(self.ratioList_M) / len(self.ratioList_M)

    def calculate_eye_ratio(self, face):
        left_up=tuple(face[159])
        left_down=tuple(face[23])
        left_left = tuple(face[130])
        left_right = tuple(face[243])
        right_up = tuple(face[386])
        right_down = tuple(face[253])
        right_left = tuple(face[463])
        right_right = tuple(face[359])
        lengthverL, __ = self.detector.findDistance(left_up, left_down)  # 上下边界距离
        lengthhorL, __ = self.detector.findDistance(left_left, left_right)  # 左右边界距离
        lengthverR, __ = self.detector.findDistance(right_up, right_down)  #
        lengthhorR, __ = self.detector.findDistance(right_left, right_right)
        ratioL = 100 * lengthverL / lengthhorL
        self.ratioList_L.append(ratioL)
        ratioR = 100 * lengthverR / lengthhorR
        self.ratioList_R.append(ratioR)
        if len(self.ratioList_L) > 10:
            self.ratioList_L.pop(0)
        ratioAvgL = sum(self.ratioList_L) / len(self.ratioList_L)
        if len(self.ratioList_R) > 10:
            self.ratioList_R.pop(0)
        ratioAvgR = sum(self.ratioList_R) / len(self.ratioList_R)
        return  (ratioAvgL + ratioAvgR) / 2

    def update_mouth_blink_count(self, ratio):
        if ratio > 26 and self.M_counter == 0:
            self.M_blinkCounter += 1
            self.M_counter = 1
        if self.M_counter != 0:
            self.M_counter += 1
            if self.M_counter > 10:
                self.M_counter = 0
    def update_eye_blink_count(self, ratio):
        if ratio < 38 and self.E_counter == 0:
            self.E_blinkCounter += 1
            self.E_counter = 1
        if self.E_counter != 0:
            self.E_counter += 1
            if self.E_counter > 10:
                self.E_counter = 0
    def justice(self):
        elapsed_time = time.time() - self.start_time
        if elapsed_time >= 30:
            if self.M_blinkCounter >= 20 or self.E_blinkCounter >= 20:
                pygame.mixer.init()
                threading.Thread(target=self.play_audio, args=('static/music/Sleep_warining.mp3',)).start()
                time.sleep(0.5)
            self.start_time = time.time()  # 重置开始时间
            self.M_blinkCounter = 0  # 重置闭眼次数
            self.E_blinkCounter = 0  # 重置眼睛


    async def disconnect(self, close_code):
        if self.cap:
            self.cap.release()

def index(request):
    #warn_music.play_sound('web/music/welcome.mp3')
    return render(request, 'index.html')
def contact(request):
    return render(request, 'contact.html')
def blog_1(request):
    return render(request, 'blog-1.html')
def blog_data1(request):
    return render(request, 'blog-details1.html')
def login(request):
    return render(request, 'login.html')
def map(request):
    return render(request, 'map.html')