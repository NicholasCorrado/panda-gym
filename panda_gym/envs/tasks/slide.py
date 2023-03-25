from typing import Any, Dict

import numpy as np

from panda_gym.envs.core import Task
from panda_gym.utils import distance

class Slide(Task):
    def __init__(
        self,
        sim,
        reward_type="sparse",
        distance_threshold=0.05,
        goal_xy_range=0.3,
        goal_x_offset=0.4,
        obj_xy_range=0.3,
        fixed_goal=False,
        quadrant=False,
    ) -> None:
        super().__init__(sim)
        self.reward_type = reward_type
        self.distance_threshold = distance_threshold
        self.object_size = 0.06
        if fixed_goal:
            self.goal_range_low = np.array([goal_xy_range / 2 + goal_x_offset, 0, 0])
            self.goal_range_high = np.array([goal_xy_range / 2 + goal_x_offset, 0, 0])
        elif quadrant:
            self.goal_range_low = np.array([goal_x_offset, 0, 0])
            self.goal_range_high = np.array([goal_xy_range / 2 + goal_x_offset, goal_xy_range / 2, 0])
        else:
            self.goal_range_low = np.array([-goal_xy_range / 2 + goal_x_offset, -goal_xy_range / 2, 0])
            self.goal_range_high = np.array([goal_xy_range / 2 + goal_x_offset, goal_xy_range / 2, 0])
        self.obj_range_low = np.array([-obj_xy_range / 2, -obj_xy_range / 2, 0])
        self.obj_range_high = np.array([obj_xy_range / 2, obj_xy_range / 2, 0])
        self.table_range_low = np.array([-obj_xy_range / 2, -obj_xy_range / 2, 0])
        self.table_range_high = np.array([obj_xy_range / 2 + goal_x_offset, obj_xy_range / 2, 0])
        with self.sim.no_rendering():
            self._create_scene()
            self.sim.place_visualizer(target_position=np.zeros(3), distance=0.9, yaw=45, pitch=-30)

        self.achieved_mask = np.zeros(21, dtype=bool)
        self.goal_mask = np.zeros(21, dtype=bool)
        self.obj_mask = np.zeros(21, dtype=bool)

        self.achieved_mask[6:8 + 1] = True
        self.goal_mask[-3:] = True
        self.obj_mask[6:17 + 1] = True

    def _create_scene(self) -> None:
        self.sim.create_plane(z_offset=-0.4)
        self.sim.create_table(length=1.4, width=0.7, height=0.4, x_offset=-0.1)
        self.sim.create_cylinder(
            body_name="object",
            mass=1.0,
            radius=self.object_size / 2,
            height=self.object_size / 2,
            position=np.array([0.0, 0.0, self.object_size / 2]),
            rgba_color=np.array([0.1, 0.9, 0.1, 1.0]),
            lateral_friction=0.04,
        )
        self.sim.create_cylinder(
            body_name="target",
            mass=0.0,
            ghost=True,
            radius=self.object_size / 2,
            height=self.object_size / 2,
            position=np.array([0.0, 0.0, self.object_size / 2]),
            rgba_color=np.array([0.1, 0.9, 0.1, 0.3]),
        )

    def get_obs(self) -> np.ndarray:
        # position, rotation of the object
        object_position = np.array(self.sim.get_base_position("object"))
        object_rotation = np.array(self.sim.get_base_rotation("object"))
        object_velocity = np.array(self.sim.get_base_velocity("object"))
        object_angular_velocity = np.array(self.sim.get_base_angular_velocity("object"))
        observation = np.concatenate(
            [
                object_position,
                object_rotation,
                object_velocity,
                object_angular_velocity,
            ]
        )
        return observation

    def get_achieved_goal(self) -> np.ndarray:
        object_position = np.array(self.sim.get_base_position("object"))
        return object_position.copy()

    def reset(self) -> None:
        self.goal = self._sample_goal()
        object_position = self._sample_object()
        self.sim.set_base_pose("target", self.goal, np.array([0.0, 0.0, 0.0, 1.0]))
        self.sim.set_base_pose("object", object_position, np.array([0.0, 0.0, 0.0, 1.0]))

    def _sample_goal(self) -> np.ndarray:
        """Randomize goal."""
        goal = np.array([0.0, 0.0, self.object_size / 2])  # z offset for the cube center
        noise = self.np_random.uniform(self.goal_range_low, self.goal_range_high)
        goal += noise
        return goal.copy()

    def _sample_n_goals(self, n) -> np.ndarray:
        """Randomize goal."""
        goal = np.array([0.0, 0.0, self.object_size / 2])  # z offset for the cube center
        goal = np.tile(goal, (n, 1))
        noise = self.np_random.uniform(self.goal_range_low, self.goal_range_high, (n,3)) # extends goal region to entire table!
        goal += noise
        return goal

    def _sample_object(self) -> np.ndarray:
        """Randomize start position of object."""
        object_position = np.array([0.0, 0.0, self.object_size / 2])
        noise = self.np_random.uniform(self.obj_range_low, self.obj_range_high)
        object_position += noise
        return object_position

    def _sample_n_objects(self, n) -> np.ndarray:
        """Randomize start position of object."""
        object_position = self.np_random.uniform(self.table_range_low, self.table_range_high, (n, 3))
        object_position[:, -1] = self.object_size / 2
        return object_position

    def is_success(self, achieved_goal: np.ndarray, desired_goal: np.ndarray) -> np.ndarray:
        d = distance(achieved_goal, desired_goal)
        return np.array(d < self.distance_threshold, dtype=np.bool8)

    def compute_reward(self, achieved_goal, desired_goal, info: Dict[str, Any]) -> np.ndarray:
        d = distance(achieved_goal, desired_goal)
        if self.reward_type == "sparse":
            return -np.array(d > self.distance_threshold, dtype=np.float32)
        else:
            return -d.astype(np.float32)
