# Collaborative Task Planner

## LLM + LTL + PDDL + Franka (robosuite) + GUI

---

## 🚀 Overview

This project implements a **collaborative AI task planner** where a human and an LLM jointly construct and refine robot plans.

The system integrates:

* **LLM** → interprets instructions and proposes plans
* **LTL (Linear Temporal Logic)** → enforces ordering constraints
* **PDDL-style reasoning** → defines actions, preconditions, and effects
* **robosuite (Franka Panda)** → executes actions in simulation
* **GUI** → enables real-time human correction and visualization

---

## 🔥 CORE IDEA

The system is NOT about robotics control.

It is about:

> **Interactive planning + constraint reasoning + human correction**

---

## 🎯 TASK SETTING

Environment:

* Franka Panda robot (robosuite)
* Multiple cubes (red, green, yellow)
* A bin acting as a “drawer”

Example task:

> “Put all cubes in the drawer. First the red cube, then the green cube, then the rest.”

---

## 🧠 SYSTEM ARCHITECTURE

```id="arch1"
User → LLM → Plan → LTL → Validation → Execution → GUI Update
```

---

## 🧩 COMPONENTS

---

### 1. LLM Module

#### Input:

Natural language instruction

#### Output:

Structured plan:

```json
{
  "plan": [
    "pick_place(red)",
    "pick_place(green)",
    "pick_place(yellow)"
  ]
}
```

#### Responsibilities:

* Extract objects and ordering
* Insert required actions (e.g., open drawer)
* Support corrections

---

### 2. LTL Module

Encodes temporal constraints.

#### Example:

```text
¬place_green U place_red
¬place_yellow U place_green
```

#### Responsibilities:

* Validate ordering
* Update when plan changes
* Display in GUI

---

### 3. PDDL-Style Action Model

Define symbolic structure.

#### Predicates:

* `holding(obj)`
* `in_drawer(obj)`
* `drawer_open`

#### Actions:

**pick_cube(obj)**

* Pre: not holding(obj)
* Eff: holding(obj)

**place_in_drawer(obj)**

* Pre: holding(obj), drawer_open
* Eff: in_drawer(obj)

**open_drawer**

* Pre: drawer_closed
* Eff: drawer_open

---

### 4. Execution Layer (robosuite)

Use **robosuite PickPlace**.

```python
env = suite.make(
    env_name="PickPlace",
    robots="Panda",
    has_renderer=True,
    use_camera_obs=False,
)
```

---

#### Skill Abstraction

Each action maps to a skill:

```python
pick_cube(color)
place_in_drawer(color)
open_drawer()
```

These are implemented as:

* simple scripted motion
* or approximate env.step sequences

---

#### State Tracking

```python
state = {
    "drawer_open": False,
    "holding": None,
    "red_in_drawer": False,
    "green_in_drawer": False,
    "yellow_in_drawer": False,
}
```

---

### 5. Execution Loop

```python
for action in plan:
    execute(action)
```

---

## 🖥️ GUI REQUIREMENTS (CRITICAL)

The GUI MUST closely match the reference image.

---

## 🔵 LEFT PANEL — Chat

* Chat bubbles (user + assistant)
* Scrollable
* Input box at bottom

### Behavior:

* User gives instruction
* LLM proposes plan
* User can correct

Example:

User:

> Put all cubes in the drawer. First red, then green.

LLM:

> I will pick yellow first...

User:

> This is wrong. Red should be first.

---

## 🟡 RIGHT PANEL — Simulation

* robosuite rendering
* Franka + cubes + bin

---

## 🟢 BOTTOM RIGHT — Plan + LTL

---

### A. Plan Sequence (IMPORTANT)

* Display as **horizontal boxes**
* Each box = action

Example:

```text
[pick_place red]   [pick_place green]   [pick_place yellow]
```

Must:

* update dynamically
* reflect corrections

---

### B. LTL Display

Single block:

```text
F(place_red) ∧ F(place_green) ∧ F(place_yellow)
∧ (¬place_green U place_red)
∧ (¬place_yellow U place_green)
```

Must:

* update with plan
* always visible

---

## 🔁 INTERACTION LOOP

1. User inputs instruction
2. LLM generates plan
3. Plan displayed
4. LTL generated
5. User corrects
6. Plan updates
7. LTL updates
8. Execution runs

---

## ⚡ SIMPLIFICATIONS (INTENTIONAL)

* Fixed object positions
* No perception
* Drawer can be logical (not physical)
* Motion can be approximate

---

## 🚨 NON-NEGOTIABLE REQUIREMENTS

* GUI must match reference layout
* Plan must be editable via chat
* LTL must reflect plan ordering
* System must update dynamically

---

## 🏁 SUCCESS CRITERIA

The system should:

* Accept natural language
* Generate structured plans
* Display plan visually
* Display LTL constraints
* Allow corrections
* Update everything in real time

---

## 🔥 FINAL NOTE

> The **interaction between human, LLM, and constraints is the project**
> not the robotics implementation.

---
