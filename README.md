# LTL LLM Interface

A collaborative robot task planner that uses Claude to generate LTL formulas from natural language, derives an execution plan from them, and runs the plan on a simulated Franka Panda robot in robosuite.

## Requirements

Python 3.11 and the following packages:

```
pip install -r requirements.txt
```

You also need an Anthropic API key. Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=your_key_here
```

## Running

```
python main.py
```

Or on Windows, run `run.bat`.

### Linux / macOS

The MuJoCo GL backend is set automatically based on your platform (`wgl` on Windows, `glfw` elsewhere). On Linux, make sure `glfw` is available — it is included with MuJoCo but requires a display (X11 or a virtual framebuffer).

## How it works

Type a natural language instruction in the chat panel, for example "place the red cube then the blue cube". Claude generates an LTL formula specifying the task constraints, the planner derives an ordered execution sequence from that formula, and the robot simulation carries it out. You can correct or refine the plan by continuing the conversation before hitting Execute.
