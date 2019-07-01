#!/usr/bin/env python

import rospy
import copy

import math
import random
import numpy as np
from tf.transformations import quaternion_from_euler, euler_from_quaternion

from interactive_markers.interactive_marker_server import *
from interactive_markers.menu_handler import *
from visualization_msgs.msg import *
from humanoid_league_msgs.msg import BallRelative, TeamData, Position2D, ObstaclesRelative, ObstacleRelative
from geometry_msgs.msg import Pose2D, Pose, Point, PoseStamped, Vector3


class WorldModelMarkerTest:
    def __init__(self):
        self.server = InteractiveMarkerServer("basic_controls")
        self.team_data_pub = rospy.Publisher("team_data", TeamData, queue_size=1)
        self.ground_truth_pub = rospy.Publisher("ground_truth_obstacles", ObstaclesRelative, queue_size=1)
        self.player_marker_pub = rospy.Publisher("player_marker", Marker, queue_size=1)

        self.menu_handler = MenuHandler()
        self.publish_ball = True
        # no difference in filtering obstacles or opponents
        self.publish_obstacle = True
        self.obstacle_count = 1
        self.ball_pose = Pose()  # everything should be 0
        self.obstacle_poses = list()
        self.mate_poses = list()  # the mates include the observing player!
        self.local_publishing_player_id = 0
        self.team_color = ObstacleRelative.ROBOT_MAGENTA
        self.opponent_color = ObstacleRelative.ROBOT_CYAN

        mate_1 = Pose()
        mate_1.position = Point(-4, 0, 0)
        self.mate_poses.append(mate_1)
        mate_2 = Pose()
        mate_2.orientation.w = 1
        mate_2.orientation.z = math.pi / 2
        mate_2.position.x = 0
        mate_2.position.y = -4
        self.mate_poses.append(mate_2)
        mate_3 = Pose()
        mate_3.orientation.w = 1
        mate_3.orientation.z = - math.pi
        mate_3.position.y = 0
        mate_3.position.x = 4
        #self.mate_poses.append(mate_3)
        mate_4 = Pose()
        mate_4.orientation.w = 1
        mate_4.orientation.z = - math.pi / 2
        mate_4.position.x = 0
        mate_4.position.y = 4
        #self.mate_poses.append(mate_4)

        for i in range(self.obstacle_count):
            obstacle_pose = Pose()
            obstacle_pose.position.x = 0.1 * i
            obstacle_pose.orientation.w = 1
            self.obstacle_poses.append(obstacle_pose)

        #self.spawn_ball_marker()
        self.spawn_obstacle_markers()
        self.server.applyChanges()


        # create a timer to update the published ball transform
        rospy.Timer(rospy.Duration(0.1), self.pub_timer_callback)

        # run and block until finished
        rospy.spin()

    def pub_timer_callback(self, evt):
        self.publish_player_markers()
        detection_rate = .8
        td_msg = TeamData()

        # creating a dummy pose as placeholder in the team data message
        dummy_pose = Pose()
        dummy_pose.position.x = 1000
        dummy_pose.position.y = 1000
        dummy_pose.position.z = 1000
        dummy_pose.orientation.w = 1

        letters = ('a', 'b', 'c', 'd')
        td_msg.robot_ids = list()
        for mate_id in range(len(self.mate_poses)):
            # add stuff in sight

            td_msg.robot_ids.append(mate_id)

            noisy_mate_pose = add_noise(self.mate_poses[mate_id], .1, .1, .12)  # TODO set noise everywhere to useful values


            # TODO: ball!!!

            if mate_id == self.local_publishing_player_id:
                obstacles = ObstaclesRelative()
                obstacles.header.frame_id = 'base_footprint'

            # publish obstacles as opponents
            for obstacle_id in range(self.obstacle_count):
                if randomly_in_sight(self.mate_poses[mate_id], self.obstacle_poses[obstacle_id], detection_rate):
                    obstacle_map_pose = self.obstacle_poses[obstacle_id]
                    obstacle_rel_pose = transform_to_pose(obstacle_map_pose, noisy_mate_pose)
                    if mate_id == self.local_publishing_player_id:
                        obstacle_msg = ObstacleRelative()
                        obstacle_msg.position = obstacle_rel_pose.position
                        obstacle_msg.color = self.opponent_color
                        obstacle_msg.confidence = 1
                        obstacle_msg.height = 0.8
                        obstacle_msg.width = 0.2
                        obstacles.obstacles.append(obstacle_msg)
                    td_msg.__getattribute__('opponent_robot_' + letters[obstacle_id]).append(pose_to_position2d(add_noise(obstacle_rel_pose, .1, .1, .5)))
                else:
                    td_msg.__getattribute__('opponent_robot_' + letters[obstacle_id]).append(pose_to_position2d(dummy_pose))
            # publish mates
            mate_seen_count = 0
            for detected_mate_id in range(len(self.mate_poses)):
                # ignore ourselves
                if detected_mate_id != mate_id:
                    if randomly_in_sight(self.mate_poses[mate_id], self.mate_poses[detected_mate_id], detection_rate):
                        mate_map_pose = self.mate_poses[detected_mate_id]
                        mate_rel_pose = transform_to_pose(mate_map_pose, noisy_mate_pose)
                        if mate_id == self.local_publishing_player_id:
                            obstacle_msg = ObstacleRelative()
                            obstacle_msg.position = mate_rel_pose.position
                            obstacle_msg.color = self.team_color
                            obstacle_msg.confidence = 1
                            obstacle_msg.height = 0.8
                            obstacle_msg.width = 0.2
                            obstacles.obstacles.append(obstacle_msg)
                        td_msg.__getattribute__('team_robot_' + letters[mate_seen_count]).append(pose_to_position2d(add_noise(mate_rel_pose, .1, .1, .5)))
                    else:
                        td_msg.__getattribute__('team_robot_' + letters[mate_seen_count]).append(pose_to_position2d(dummy_pose))
                    mate_seen_count += 1

            quaternion = quaternion_from_euler(0, 0, noisy_mate_pose.orientation.z)
            noisy_mate_pose.orientation.x = quaternion[0]
            noisy_mate_pose.orientation.y = quaternion[1]
            noisy_mate_pose.orientation.z = quaternion[2]
            noisy_mate_pose.orientation.w = quaternion[3]
            td_msg.robot_positions.append(pose_to_pose2d(noisy_mate_pose))

            self_marker = Marker()
            self_marker.id = 1230 + mate_id
            self_marker.action = Marker.ADD
            self_marker.type = Marker.ARROW
            self_marker.pose = noisy_mate_pose
            self_marker.scale.x = 0.05
            self_marker.scale.y = 0.05
            self_marker.scale.z = 0.5
            self.player_marker_pub.publish(self_marker)
        self.publish_ground_truth()
        self.team_data_pub.publish(td_msg)

    def spawn_ball_marker(self, position):
        int_marker = InteractiveMarker()
        int_marker.header.frame_id = "map"
        int_marker.pose.position = position
        int_marker.pose.orientation.w = 1
        int_marker.scale = 1

        int_marker.name = "ball"

        control = InteractiveMarkerControl()
        control.orientation.w = 1
        control.orientation.x = 0
        control.orientation.y = 1
        control.orientation.z = 0
        control.interaction_mode = InteractiveMarkerControl.MOVE_PLANE
        int_marker.controls.append(copy.deepcopy(control))

        # make a box which also moves in the plane
        control.markers.append(make_sphere(int_marker))
        control.always_visible = True
        int_marker.controls.append(control)

        self.server.insert(int_marker, self.ball_feedback_callback)

    def spawn_obstacle_markers(self):
        for i in range(self.obstacle_count):
            int_marker = InteractiveMarker()
            int_marker.header.frame_id = "map"
            int_marker.pose = self.obstacle_poses[i]
            int_marker.scale = 1

            int_marker.name = "obstacle_" + str(i)

            control = InteractiveMarkerControl()
            control.orientation.w = 1
            control.orientation.x = 0
            control.orientation.y = 1
            control.orientation.z = 0
            control.interaction_mode = InteractiveMarkerControl.MOVE_PLANE
            int_marker.controls.append(copy.deepcopy(control))

            # make a box which also moves in the plane
            control.markers.append(make_cube(int_marker))
            control.always_visible = True
            int_marker.controls.append(control)

            self.server.insert(int_marker, self.obstacle_feedback_callback)

    def ball_feedback_callback(self, feedback):
        self.ball_pose = feedback.pose
        self.server.applyChanges()

    def obstacle_feedback_callback(self, feedback):
        # type: (InteractiveMarkerFeedback) -> None
        self.obstacle_poses[int(feedback.marker_name[-1])] = feedback.pose
        self.server.applyChanges()

    def publish_player_markers(self):

        distance = 9
        marker_msg = Marker()
        marker_msg.type = Marker.TRIANGLE_LIST
        marker_msg.action = Marker.ADD
        marker_msg.color.a = .6
        marker_msg.color.g = 1
        marker_msg.header.frame_id = 'map'
        marker_msg.scale = Vector3(1, 1, 1)

        for player in self.mate_poses:
            marker_msg.points.append(player.position)
            for k in [1, -1]:
                angle = player.orientation.z + k * math.radians(50)
                if angle < -math.pi:
                    angle += 2 * math.pi
                if angle > math.pi:
                    angle -= 2 * math.pi

                p = Point()
                p.x = player.position.x + distance * math.cos(angle)
                p.y = player.position.y + distance * math.sin(angle)
                marker_msg.points.append(p)



        self.player_marker_pub.publish(marker_msg)

    def publish_ground_truth(self):
        gt_msg = ObstaclesRelative()

        gt_msg.header.frame_id = 'map'

        for object in self.obstacle_poses:
            obstacle_msg = ObstacleRelative()
            obstacle_msg.position = object.position
            obstacle_msg.position.z = 0
            obstacle_msg.confidence = 1
            obstacle_msg.color = ObstacleRelative.ROBOT_UNDEFINED
            gt_msg.obstacles.append(obstacle_msg)
        self.ground_truth_pub.publish(gt_msg)



def randomly_in_sight(observer_pose, object_pose, detection_chance):
    # type: (Pose, Pose, float) -> bool
    return in_sight(observer_pose, object_pose) if random.random() <= detection_chance else False


def in_sight(observer_pose, object_pose):
    # type: (Pose, Pose) -> bool

    # all angles in radian!
    fov = math.radians(100)  # setting the FOV to 100 degrees

    # calculate relative position of the object
    x_dist = object_pose.position.x - observer_pose.position.x
    y_dist = object_pose.position.y - observer_pose.position.y
    angle_global = -math.atan2(y_dist, x_dist)
    angle_relative = angle_global + observer_pose.orientation.z  # this is wrong, but it isn't.
    if angle_relative < -math.pi:
        angle_relative += 2 * math.pi
    if angle_relative > math.pi:
        angle_relative -= 2 * math.pi

    return abs(angle_relative) <= fov / 2.0


def distance(pose_a, pose_b):
    # type: (Pose, Pose) -> float
    # assuming z=0
    x_dist = pose_a.position.x - pose_b.position.x
    y_dist = pose_a.position.y - pose_b.position.y
    return math.sqrt(x_dist ** 2 + y_dist ** 2)


def add_noise(in_pose, sigma_x, sigma_y, sigma_theta):
    # type: (Pose, float, float, float) -> Pose
    pose = copy.deepcopy(in_pose)
    x_offset = 1 * np.random.normal(0, sigma_x, 1)
    y_offset = 1 * np.random.normal(0, sigma_y, 1)
    theta_offset = 1 * np.random.normal(0, sigma_theta, 1)
    pose.position.x += x_offset
    pose.position.y += y_offset
    pose.orientation.z += theta_offset
    return pose


def make_sphere(msg):
    marker = Marker()

    marker.type = Marker.SPHERE
    marker.scale.x = msg.scale * 0.13
    marker.scale.y = msg.scale * 0.13
    marker.scale.z = msg.scale * 0.13
    marker.color.r = 1.0
    marker.color.g = 0.0
    marker.color.b = 0.0
    marker.color.a = 1.0

    return marker


def make_cube(msg):
    marker = Marker()

    marker.type = Marker.CUBE
    marker.scale.x = msg.scale * 0.2
    marker.scale.y = msg.scale * 0.2
    marker.scale.z = msg.scale * 1
    marker.color.r = 1.0
    marker.color.g = 1.0
    marker.color.b = 0.0
    marker.color.a = 1.0
    marker.pose.position.z = msg.scale * 0.5

    return marker


def stamp_now(pose, frame):
    # type: (Pose, str) -> PoseStamped
    pose_stamped = PoseStamped()
    pose_stamped.pose = pose
    pose_stamped.header.frame_id = frame
    pose_stamped.header.stamp = rospy.get_rostime()
    return pose_stamped


def pose_to_pose2d(pose):
    # type: (Pose) -> Pose2D
    pose2d = Pose2D()
    pose2d.x = pose.position.x
    pose2d.y = pose.position.y
    euler = euler_from_quaternion((pose.orientation.x, pose.orientation.y, pose.orientation.z, pose.orientation.w))
    pose2d.theta = euler[2]
    return pose2d


def pose_to_position2d(pose):
    # type: (Pose) -> Position2D
    position2d = Position2D()
    position2d.confidence = 1
    position2d.pose = pose_to_pose2d(pose)
    return position2d


def transform_to_pose(detection, observer):
    # type: (Pose, Pose) -> Pose
    pose = Pose()
    # detection to planar coordinate
    r = math.sqrt((detection.position.x - observer.position.x) ** 2 + (detection.position.y - observer.position.y) ** 2)
    d = math.atan2(detection.position.y - observer.position.y, detection.position.x - observer.position.x)
    # add angle of detecting player
    d -= observer.orientation.z
    if d < -math.pi:
        d += 2 * math.pi
    if d > math.pi:
        d -= 2 * math.pi
    # back to Cartesian coordinates...
    pose.position.x = r * math.cos(d)
    pose.position.y = r * math.sin(d)

    return pose


if __name__ == "__main__":
    rospy.init_node("humanoid_league_interactive_marker")

    WorldModelMarkerTest()
