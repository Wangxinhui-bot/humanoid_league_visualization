#!/usr/bin/env python2.7
import copy
from collections import OrderedDict

import cv2
import os
import rospy
from humanoid_league_msgs.msg import BallInImage, BallsInImage
from sensor_msgs.msg import Image
from cv_bridge import CvBridge, CvBridgeError


def draw_ball(cv_img, ball):
    i = [0, 0, 0]
    i[0] = int(ball.center.x)
    i[1] = int(ball.center.y)
    i[2] = int(ball.diameter / 2.0)
    c = (255, 0, 0)
    cv2.circle(cv_img, (i[0], i[1]), i[2], c, 2)
    cv2.circle(cv_img, (i[0], i[1]), 2, (0, 0, 255), 3)


def draw_ball_candidates(cv_img, candidates):
    if len(candidates) > 0:
        for can in candidates:
            i = [0, 0, 0]
            i[0] = int(can.center.x)
            i[1] = int(can.center.y)
            i[2] = int(can.diameter / 2.0)

            if can.confidence >= 0.5:
                c = (0, 255, 0)
            else:
                c = (0, 0, 255)
                # print(p)
                # draw the outer circle
            cv2.circle(cv_img, (i[0], i[1]), i[2], c, 2)
            # draw the center of the circle
            cv2.circle(cv_img, (i[0], i[1]), 2, (0, 0, 255), 3)


class VisionViz:
    def __init__(self):
        rospy.init_node("bitbots_imageviewer")

        self.bridge = CvBridge()
        self.images = OrderedDict()
        self.ball_candidates = OrderedDict()
        self.balls = OrderedDict()

        #todo these have to be dyn reconfigurable
        self.candidates_active = True
        self.ball_active = True
        #todo add goals, obstacles and line

        self.viz_publisher = rospy.Publisher("/vision_viz_image", Image, queue_size=10)
        rospy.Subscriber("/image_raw", Image, self._image_cb, queue_size=10)
        rospy.Subscriber("/ball_candidates", BallsInImage, self._candidates_cb, queue_size=10)

        self.run()
        rospy.spin()

    def run(self):
        while not rospy.is_shutdown():
            images = copy.deepcopy(self.images)
            # print("Waiting for " + str(self.images.keys()))
            for t in images.keys():  # imgages who are wating

                if t in self.ball_candidates:  # Check if all data to draw is there

                    img = images.pop(t)  # get image from queue
                    candidates = self.ball_candidates.pop(t)
                    ball = self.balls.pop(t)
                    cv_img = self.bridge.imgmsg_to_cv2(img, "bgr8")

                    if self.candidates_active:
                        draw_ball_candidates(cv_img, candidates)
                    if self.ball_active:
                        draw_ball(cv_img, ball)

                    out_msg = self.bridge.cv2_to_compressed_imgmsg(cv_img)
                    self.viz_publisher.publish(out_msg)

    def _image_cb(self, msg):
        self.images[msg.header.stamp] = msg

        if len(self.images) >= 10:
            self.images.popitem(last=False)

    def _candidates_cb(self, msg):
        self.ball_candidates[msg.header.stamp] = msg.candidates
        if len(self.ball_candidates) > 5:
            self.ball_candidates.popitem(last=False)
