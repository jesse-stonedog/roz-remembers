# roz-remembers: A Message-Driven State Management Library

---

roz-remembers is a lightweight, message-driven state management library for Python, inspired by the predictable state container pattern popularized by Redux in the JavaScript ecosystem. It's designed to provide a **centralized, immutable state** that can be updated solely through **explicit, descriptive actions**, making your application's state changes predictable, traceable, and easier to debug.

## Features

* **Centralized State:** A single source of truth for your application's state, making it easy to understand and manage.
* **Immutable State:** State is never directly modified. Instead, actions produce new state instances, ensuring data integrity and simplifying change detection.
* **Message-Driven:** All state changes are triggered by dispatching "actions"—plain Python dictionaries describing what happened.
* **Predictable Changes:** Because state changes are a result of explicit actions, it's easy to predict the outcome of any operation.
* **Asynchronous Processing:** Built with `asyncio` to handle actions in a non-blocking, concurrent manner.
* **Initial State Loading:** Supports loading initial state from a JSON file, ideal for configuration or bootstrapping.
* **Action Listeners:** Allows registration of functions that react to specific action types, enabling side effects or complex logic outside the core state update.

## Installation

Roz-Remembers can be installed using [Poetry](https://python-poetry.org/):

```bash
poetry add roz-remembers

Or [PIP](https://pypi.org/project/pip/):

```bash
pip install roz-remembers

