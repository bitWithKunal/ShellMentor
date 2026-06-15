# ShellMentor


**Professional Linux Command-Line Learning Platform**

ShellMentor is an interactive terminal-based learning platform built with Python. It helps users learn Linux commands, shell scripting concepts, text-processing utilities, and command-line workflows through lessons, challenges, missions, and hands-on practice.

---

# Features

## Interactive Learning

* Structured lessons
* Guided command-line exercises
* Progressive learning paths
* Practical examples

## Command Practice

* Dedicated practice environment
* Real datasets for experimentation
* Text-processing exercises
* Linux workflow simulations

## Challenges & Missions

* Challenge-based learning
* Mission progression system
* Skill validation exercises
* Practical problem-solving tasks

## Progress Tracking

* XP-based progression
* Achievement system
* Learning statistics
* User progress persistence

## Learning Content

Topics include:

* Linux fundamentals
* File and directory operations
* Permissions and ownership
* Process management
* Shell basics
* grep
* sed
* awk
* sort
* cut
* find
* xargs
* Shell pipelines
* Command-line data analysis
* VLSI and EDA-oriented command-line workflows

---

# Requirements

| Component        | Requirement              |
| ---------------- | ------------------------ |
| Operating System | Linux                    |
| Python           | 3.10+                    |
| Terminal         | Modern terminal emulator |

Tested on:

* Ubuntu
* Linux Mint
* Debian-based distributions

---

# Installation

## Clone Repository

```bash
git clone https://github.com/bitWithKunal/ShellMentor.git

cd ShellMentor
```

## Create Virtual Environment

```bash
python3 -m venv .venv

source .venv/bin/activate
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Launch

```bash
python main.py
```

If the launcher script is available:

```bash
chmod +x shellmentor.sh

./shellmentor.sh
```

---

# Quick Start

```bash
git clone https://github.com/bitWithKunal/ShellMentor.git

cd ShellMentor

python3 -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

python main.py
```

---

# Project Structure

```text
ShellMentor/
├── main.py
├── ui.py
├── utils.py
├── data_manager.py
├── learning.py
├── challenge.py
├── playground.py
├── progress.py
├── github_sync.py
├── sandbox.py
├── shellmentor.sh
├── requirements.txt
│
├── data/
│   ├── achievements.json
│   ├── challenges.json
│   ├── lessons.json
│   └── missions.json
│
├── themes/
│   └── themes.yaml
│
└── workspace/
    ├── constraints.sdc
    ├── employees.csv
    ├── liberty.lib
    ├── netlist.v
    ├── placement.rpt
    ├── power.rpt
    ├── routing.rpt
    ├── sales.csv
    └── timing.rpt
```

---

# Learning Modules

## Lessons

Step-by-step learning material designed to build Linux command-line proficiency.

## Playground

Hands-on environment for experimenting with commands and pipelines.

## Challenges

Problem-solving exercises focused on real command-line scenarios.

## Missions

Multi-step tasks that combine several Linux concepts into practical workflows.

## Achievements

Milestone tracking and progression rewards.

---

# Sample Learning Areas

## Linux Fundamentals

* Navigation
* File management
* Permissions
* Users and groups

## Text Processing

* grep
* sed
* awk
* sort
* uniq
* cut
* tr

## Shell Productivity

* Pipes
* Redirection
* Command chaining
* Filters

## VLSI Command-Line Workflows

Practice using:

* Timing reports
* Liberty files
* Netlists
* Constraint files
* CSV datasets

---

# Workspace

ShellMentor includes sample datasets and engineering-oriented files for practice.

Examples:

* CSV datasets
* Liberty files
* Netlists
* Timing reports
* Placement reports
* Routing reports
* SDC constraints

These files are intended for command-line exercises and learning activities.

---

# Development

Install development dependencies:

```bash
pip install -r requirements.txt
```

Run:

```bash
python main.py
```

---

# Roadmap

* [x] Interactive lessons
* [x] Challenge system
* [x] Mission system
* [x] Progress tracking
* [x] Achievement tracking
* [ ] Advanced shell scripting track
* [ ] Git learning track
* [ ] Docker learning track
* [ ] Additional VLSI workflows
* [ ] Plugin architecture

---

# Contributing

Contributions are welcome.

1. Fork the repository
2. Create a feature branch

```bash
git checkout -b feature/my-feature
```

3. Commit changes

```bash
git commit -m "Add new feature"
```

4. Push branch

```bash
git push origin feature/my-feature
```

5. Open a Pull Request

---

# License

This project is licensed under the MIT License.

Create a LICENSE file before publishing if one does not already exist.

---

# Author

**Kunal Saraswat**

GitHub:
https://github.com/bitWithKunal

Project:
https://github.com/bitWithKunal/ShellMentor

LinkedIn:
https://www.linkedin.com/in/kunalsaraswat/

---

# Acknowledgements

* Python
* Textual
* Rich
* Open Source Community

---

**ShellMentor — Learn Linux by Doing.**

