## 🤖 ROBOT ENVIRONMENT SPECIFICATION (CRITICAL)

This section defines EXACTLY how the robot simulation must be set up.

---

### 🧩 Simulation Framework

Use:

* robosuite
* Environment: **PickPlace**
* Robot: **Franka Panda**

---

### ⚙️ Initialization

```python
import robosuite as suite

env = suite.make(
    env_name="PickPlace",
    robots="Panda",
    has_renderer=True,
    has_offscreen_renderer=False,
    use_camera_obs=False,
    control_freq=20,
)
```

---

### 🟥 Objects

The environment includes 3 objects:

| robosuite name | semantic name |
| -------------- | ------------- |
| cubeA          | red           |
| cubeB          | green         |
| cubeC          | yellow        |

---

### 🧠 Object Mapping

```python
OBJECT_MAP = {
    "cubeA": "red",
    "cubeB": "green",
    "cubeC": "yellow"
}
```

All planning must use **semantic names (red, green, yellow)**.

---

### 📍 Object Positions

* Objects are assumed to be in **fixed, known positions**
* No perception is required
* Positions can be read from environment observation or hardcoded

---

### 🟫 Drawer Representation

robosuite PickPlace does NOT include a real drawer.

Therefore:

👉 The “drawer” is implemented as:

* Use the **target bin location** in PickPlace
* Treat this bin as the drawer

Additionally maintain logical state:

```python
state["drawer_open"] = False
```

---

### ⚙️ Action Space

robosuite uses:

```python
env.step(action)
```

Where:

```python
action = [dx, dy, dz, droll, dpitch, dyaw, gripper]
```

---

### 🤖 Skill Abstraction Layer

You MUST wrap low-level control into high-level skills:

---

#### pick_cube(color)

* Move toward cube position
* Close gripper
* Lift slightly

---

#### place_in_drawer(color)

* Move toward bin/drawer position
* Open gripper

---

#### open_drawer()

Logical only:

```python
state["drawer_open"] = True
```

---

### 🔁 Execution Model

Each symbolic action maps to a skill:

| Symbolic Action | Execution                             |
| --------------- | ------------------------------------- |
| pick_place(red) | pick_cube(red) → place_in_drawer(red) |
| open_drawer     | update state                          |

---

### ⚠️ Constraints

* No motion planning required
* No perception required
* No learning required
* Actions can be approximate

---

### 🎯 Goal Condition

Task is complete when:

```python
state["red_in_drawer"] == True
state["green_in_drawer"] == True
state["yellow_in_drawer"] == True
```

---

### 🔥 Key Insight

The robot is only used to:

* visually demonstrate execution
* follow LLM-generated plans

NOT to solve the planning problem.
