"""
Standalone sim process.
  stdout → binary frames (FRAM header + RGB)
  stderr → text messages (READY, PROGRESS, DONE)
  stdin  → commands (EXEC ..., QUIT)

Physics runs flat out in main loop.
A writer thread drains a frame queue to stdout — drops frames if pipe is slow.
Physics NEVER blocks on IO.
"""

import sys, os, struct, threading, queue
import numpy as np

os.environ.setdefault("MUJOCO_GL", "wgl" if sys.platform == "win32" else "glfw")
import warnings; warnings.filterwarnings("ignore")

import robosuite  # noqa
from robosuite import load_composite_controller_config
from custom_env import CubePickPlace
from state import state

CAM_W, CAM_H = 640, 480

BIN_POS  = np.array([0.1, 0.28, 0.822])   # bin2_pos — the target bin
SAFE_Z   = 1.00
GRASP_Z  = 0.800   # target below cube so arm fully extends; bottoms out at ~0.837 which contacts cube at 0.842
HOME_POS = np.array([-0.036, -0.069, SAFE_Z])

PHASE_SEQ = [
    "above_cube", "descend", "grasp", "lift",
    "above_bin", "lower_bin", "release", "retract",
]
PHASE_STEPS = {
    "above_cube": 100,
    "descend":    180,
    "grasp":      80,   # give fingers time to fully close
    "lift":       60,
    "above_bin":  180,
    "lower_bin":  180,
    "release":    70,
    "retract":    180,
}
COLOR_TO_OBJ = {"red": "Red", "green": "Green", "yellow": "Yellow", "blue": "Blue"}

# Writer thread — drains frame queue to stdout
_frame_q = queue.Queue(maxsize=3)

def _writer():
    while True:
        item = _frame_q.get()
        if item is None:
            break
        data = item.tobytes()
        sys.stdout.buffer.write(b'FRAM' + struct.pack('<I', len(data)) + data)
        sys.stdout.buffer.flush()

threading.Thread(target=_writer, daemon=True).start()


def push_frame(frame):
    try:
        _frame_q.put_nowait(frame.copy())
    except queue.Full:
        pass  # drop — physics keeps going


def send_msg(tag, body=""):
    sys.stderr.write(f"{tag} {body}\n" if body else f"{tag}\n")
    sys.stderr.flush()


def get_cube_pos(obs, color):
    return np.array(obs[f"{COLOR_TO_OBJ[color]}_pos"])


def phase_target(phase, cube_pos):
    cx, cy = cube_pos[0], cube_pos[1]
    bx, by = BIN_POS[0], BIN_POS[1]
    return {
        "above_cube": [cx, cy - 0.02, SAFE_Z],
        "descend":    [cx, cy - 0.02, GRASP_Z],
        "grasp":      [cx, cy - 0.02, GRASP_Z],
        "lift":       [cx, cy - 0.02, SAFE_Z],
        "above_bin":  [bx, by, SAFE_Z],
        "lower_bin":  [bx, by, 0.92],   # arm physically bottoms out ~0.914 above bin
        "release":    [bx, by, 0.92],
        "retract":    list(HOME_POS),    # return to neutral home before next pick
    }[phase]


def phase_gripper(phase):
    return 1.0 if phase in ("grasp", "lift", "above_bin", "lower_bin") else -1.0


def set_cube_collision(env, color, enabled: bool):
    """Enable or disable collision on a cube's geoms."""
    val = 1 if enabled else 0
    for gid in env.obj_geom_id[COLOR_TO_OBJ[color]]:
        env.sim.model.geom_contype[gid]    = val
        env.sim.model.geom_conaffinity[gid] = val


def freeze_cube(env, color, frozen_cubes):
    """Save cube qpos and disable its collisions so the arm can phase through it."""
    joint = f"{COLOR_TO_OBJ[color]}_joint0"
    frozen_cubes[color] = env.sim.data.get_joint_qpos(joint).copy()
    set_cube_collision(env, color, False)


def apply_frozen_cubes(env, frozen_cubes):
    """Reset frozen cubes to their saved positions every step so they don't fall."""
    if not frozen_cubes:
        return
    for color, saved_qpos in frozen_cubes.items():
        joint = f"{COLOR_TO_OBJ[color]}_joint0"
        env.sim.data.set_joint_qpos(joint, saved_qpos)
        joint_id = env.sim.model.joint_name2id(joint)
        dof_start = env.sim.model.jnt_dofadr[joint_id]
        env.sim.data.qvel[dof_start:dof_start + 6] = 0.0
    env.sim.forward()


def unfreeze_all(env, frozen_cubes):
    """Re-enable collisions on all frozen cubes and clear the freeze dict."""
    for color in list(frozen_cubes.keys()):
        set_cube_collision(env, color, True)
    frozen_cubes.clear()


def teleport_cube_to_gripper(env, obs, color):
    """Move cube to EE position so it's firmly in the gripper."""
    ee   = np.array(obs["robot0_eef_pos"])
    # Place cube slightly below EE where fingers meet
    pos  = ee + np.array([0.0, 0.0, -0.05])
    quat = np.array([1.0, 0.0, 0.0, 0.0])   # neutral orientation (w,x,y,z)
    joint = f"{COLOR_TO_OBJ[color]}_joint0"
    env.sim.data.set_joint_qpos(joint, np.concatenate([pos, quat]))
    env.sim.forward()


def run():
    cfg = load_composite_controller_config(robot="Panda")
    env = CubePickPlace(
        robots="Panda",
        has_renderer=False,
        has_offscreen_renderer=True,
        use_camera_obs=True,
        camera_names="agentview",
        camera_heights=CAM_H,
        camera_widths=CAM_W,
        control_freq=20,
        controller_configs=cfg,
        ignore_done=True,
    )
    obs = env.reset()
    send_msg("READY")

    plan            = []
    plan_idx        = 0
    phase           = "idle"
    phase_step      = 0
    cached_cube_pos = None
    frozen_cubes    = {}   # color -> saved qpos for non-target cubes
    carried_cube    = None  # cube being ghost-carried after a missed grasp
    tick            = 0

    cmd_q = queue.Queue()
    def _stdin():
        for line in sys.stdin:
            cmd_q.put(line.strip())
    threading.Thread(target=_stdin, daemon=True).start()

    while True:
        # Non-blocking command check
        try:
            cmd = cmd_q.get_nowait()
            if cmd == "QUIT":
                break
            elif cmd.startswith("EXEC "):
                plan            = cmd[5:].split()
                plan_idx        = 0
                phase           = "above_cube"
                phase_step      = 0
                cached_cube_pos = None
                frozen_cubes.clear()
                carried_cube    = None
                obs             = env.reset()
                state.reset_robot_state()
                state.drawer_open = True
                send_msg("PROGRESS", f"0 {plan[0]}")
        except queue.Empty:
            pass

        # Build action
        color = plan[plan_idx] if plan and plan_idx < len(plan) else None

        if phase == "idle" or color is None:
            action = np.zeros(env.action_dim)
            action[-1] = -1.0
        else:
            if phase == "above_cube":
                cached_cube_pos = get_cube_pos(obs, color)
            target = phase_target(phase, cached_cube_pos)
            ee     = np.array(obs["robot0_eef_pos"])
            action = np.zeros(env.action_dim)
            action[:3] = np.clip(np.array(target) - ee, -0.2, 0.2)
            action[-1] = phase_gripper(phase)

        obs, _, done, _ = env.step(action)

        # Keep frozen cubes pinned in place after every physics step
        apply_frozen_cubes(env, frozen_cubes)

        # Ghost-carry missed cube: track it to the EE with collision off so
        # closed fingers can't push it away
        if carried_cube:
            ee_now = np.array(obs["robot0_eef_pos"])
            carry_pos  = ee_now + np.array([0.0, 0.0, -0.05])
            carry_quat = np.array([1.0, 0.0, 0.0, 0.0])
            carry_joint = f"{COLOR_TO_OBJ[carried_cube]}_joint0"
            env.sim.data.set_joint_qpos(carry_joint, np.concatenate([carry_pos, carry_quat]))
            jid = env.sim.model.joint_name2id(carry_joint)
            env.sim.data.qvel[env.sim.model.jnt_dofadr[jid]:env.sim.model.jnt_dofadr[jid] + 6] = 0.0
            env.sim.forward()

        if done and (phase != "idle"):
            obs = env.reset()
        tick += 1

        # Push frame every 3 steps — writer drops if pipe is slow
        if tick % 3 == 0:
            frame = obs.get("agentview_image")
            if frame is not None:
                push_frame(frame)

        # Advance phase
        if phase != "idle" and color is not None:
            phase_step += 1
            if phase_step >= PHASE_STEPS[phase]:
                phase_step = 0
                idx = PHASE_SEQ.index(phase)
                next_phase = PHASE_SEQ[idx + 1] if idx + 1 < len(PHASE_SEQ) else None

                # Freeze non-target cubes when starting pick approach
                if phase == "above_cube":
                    for c in COLOR_TO_OBJ:
                        if c != color:
                            freeze_cube(env, c, frozen_cubes)

                # At end of grasp — ghost-carry cube if missed (collision off
                # so closed fingers can't knock it away; re-enabled at lift end)
                if phase == "grasp":
                    cube_pos = get_cube_pos(obs, color)
                    ee_pos   = np.array(obs["robot0_eef_pos"])
                    if np.linalg.norm(cube_pos[:2] - ee_pos[:2]) > 0.04:
                        set_cube_collision(env, color, False)
                        teleport_cube_to_gripper(env, obs, color)
                        carried_cube = color

                # After lift — unfreeze other cubes; snap carried cube into
                # place and re-enable its collision now that arm is high and
                # fingers are properly closed
                if phase == "lift":
                    unfreeze_all(env, frozen_cubes)
                    if carried_cube:
                        set_cube_collision(env, carried_cube, True)
                        teleport_cube_to_gripper(env, obs, carried_cube)
                        carried_cube = None

                if next_phase:
                    phase = next_phase
                else:
                    setattr(state, f"{color}_in_drawer", True)
                    cached_cube_pos = None
                    plan_idx += 1
                    if plan_idx < len(plan):
                        phase = "above_cube"
                        send_msg("PROGRESS", f"{plan_idx} {plan[plan_idx]}")
                    else:
                        phase = "idle"
                        plan  = []
                        send_msg("DONE")

    _frame_q.put(None)
    env.close()


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        import traceback
        send_msg("ERROR", str(e))
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
