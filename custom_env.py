"""
CubePickPlace — PickPlace subclass that uses coloured BoxObjects
instead of the default food items (milk, bread, cereal, can).

Objects:
  Red    → index 0
  Green  → index 1
  Yellow → index 2
  Blue   → index 3
"""

import numpy as np
from robosuite.environments.manipulation.pick_place import PickPlace
from robosuite.models.objects import BoxObject
from robosuite.models.tasks import ManipulationTask
from flat_arena import FlatBinsArena


CUBE_SIZE   = [0.022, 0.022, 0.022]   # metres — roughly a small cube
CUBE_COLORS = {
    "Red":    [0.85, 0.15, 0.15, 1.0],
    "Green":  [0.15, 0.75, 0.15, 1.0],
    "Yellow": [0.95, 0.85, 0.10, 1.0],
    "Blue":   [0.15, 0.35, 0.85, 1.0],
}


class CubePickPlace(PickPlace):
    """PickPlace with 3 coloured cubes (+ 1 filler) instead of food items."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("single_object_mode", 0)
        kwargs.setdefault("object_type", None)
        kwargs.setdefault("z_rotation", 0.0)   # fixed orientation, no random spin

        super().__init__(*args, **kwargs)

    # Override names and id mapping BEFORE super().__init__ reaches _load_model
    def _pre_action(self, action, policy_step=False):
        # Patch names once the env is initialised
        return super()._pre_action(action, policy_step)

    # Called by PickPlace.__init__ — we override to inject our names
    def _check_success(self):
        return super()._check_success()

    # ── Object construction (the two override points) ────────────────────────

    def _construct_visual_objects(self):
        """No ghost/target cubes — bins start empty."""
        self.visual_objects = []

    def _construct_objects(self):
        """Replace food objects with coloured BoxObjects."""
        self.objects = []
        for name, rgba in CUBE_COLORS.items():
            obj = BoxObject(
                name=name,
                size=CUBE_SIZE,
                rgba=rgba,
            )
            self.objects.append(obj)

        # Patch the name/id maps so the rest of PickPlace still works
        self.obj_names    = list(CUBE_COLORS.keys())
        self.object_to_id = {n.lower(): i for i, n in enumerate(self.obj_names)}

    def _reset_internal(self):
        """Re-sample until no two cubes spawn within 7cm of each other."""
        for _ in range(100):
            super()._reset_internal()
            positions = [
                np.array(self.sim.data.body_xpos[self.obj_body_id[name]])
                for name in self.obj_names
            ]
            too_close = False
            for i in range(len(positions)):
                for j in range(i + 1, len(positions)):
                    if np.linalg.norm(positions[i][:2] - positions[j][:2]) < 0.07:
                        too_close = True
                        break
                if too_close:
                    break
            if not too_close:
                return

    def _load_model(self):
        """Override to use FlatBinsArena instead of BinsArena."""
        # Call grandparent to set up robot, skip PickPlace's arena creation
        from robosuite.environments.robot_env import RobotEnv
        RobotEnv._load_model(self)

        xpos = self.robots[0].robot_model.base_xpos_offset["bins"]
        self.robots[0].robot_model.set_base_xpos(xpos)

        mujoco_arena = FlatBinsArena(
            bin1_pos=self.bin1_pos,
            table_full_size=self.table_full_size,
            table_friction=self.table_friction,
        )
        mujoco_arena.set_origin([0, 0, 0])
        self.bin_size = mujoco_arena.table_full_size

        self._construct_visual_objects()
        self._construct_objects()

        self.model = ManipulationTask(
            mujoco_arena=mujoco_arena,
            mujoco_robots=[robot.robot_model for robot in self.robots],
            mujoco_objects=self.visual_objects + self.objects,
        )
        self._get_placement_initializer()
