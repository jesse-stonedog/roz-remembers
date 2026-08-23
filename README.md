# stonedog-remembers

A small, message-driven state management library for Python, inspired by the
predictable state-container pattern popularized by Redux. It gives you a
**centralized, observable bag of state** that you read and write through simple
**dot-path** keys (e.g. `"job.bins"`), with change events you can subscribe to
and optional JSON persistence.

It ships **two front ends over the same dot-path engine**:

* **`Store`** — a *synchronous* store. Best for ordinary synchronous code that
  just wants central, observable runtime state without an event loop.
* **`StonedogRemembers`** — an *asyncio*, Redux-style store driven by an action queue
  and an event queue. Best for long-running async applications.

Both share the exported helpers `get_nested_value(path, data)` and
`set_nested_value(path, value, data)`.

## Installation

```bash
pip install stonedog-remembers
```

The import name is `stonedog_remembers`:

```python
from stonedog_remembers import Store, StonedogRemembers, get_nested_value, set_nested_value
```

## Dot-path convention

State is a nested dict, and every read/write addresses a value by a
dot-separated `path`:

* `"user.theme"` → `state["user"]["theme"]`
* numeric segments index into lists: `"items.0.name"` → `state["items"][0]["name"]`
* **reads** of a missing or non-traversable path return `None`
  (or your supplied default on `Store.get`).
* **a stored `None` is not the same as a missing path.** `Store.get` returns
  `None` for a value somebody stored, and your default only when there is no
  value there at all — use `Store.has(path)` to ask which. (`get_nested_value`
  still returns `None` for both; it is public API and unchanged.)
* **writes** auto-create intermediate dicts as needed. A write fails
  (returns `False`) only if a segment can't be traversed or assigned — e.g. a
  list index out of range, or trying to descend into a scalar.

## Quickstart — `Store` (synchronous)

```python
from stonedog_remembers import Store

store = Store({"job": {"bins": 10, "sorted": 0}})

# read / write by dot-path
store.set("job.sorted", 1)            # -> True
store.get("job.sorted")               # -> 1
store.get("job.missing", default=0)   # -> 0 (missing path falls back)

# writes auto-create intermediate dicts
store.set("machine.state", "CARD_READY")
store.get_state()                     # deep copy of the whole state

# subscribe to change events; subscribe() returns an unsubscribe function
def on_change(event):
    print(event["path"], event["old_value"], "->", event["new_value"])

unsubscribe = store.subscribe(on_change)
store.set("job.sorted", 2)            # -> on_change fires
unsubscribe()                         # stop receiving events
```

### Persistence

`Store` reads and writes plain JSON:

```python
store.save("state.json")                 # write current state to disk
restored = Store(state_file="state.json")  # load state at construction
restored.get("job.bins")                 # -> 10

# a Store created with state_file remembers it, so save() needs no argument
live = Store(state_file="state.json")
live.set("job.sorted", 5)
live.save()                              # persists back to state.json
```

**Loading never raises.** A missing file, malformed JSON, an unreadable file, a
path that is a directory, or a JSON document that is not an object all start
from an empty state with a log line — so a first run "just works" and a
constructor is not something every caller has to wrap.

**Saving is atomic.** The state is written to a temporary file in the target's
own directory, flushed, and then `os.replace`d over the target, so a reader sees
either the old file or the new one and never a half-written one. The obvious
implementation — `open(target, "w")` — truncates *before* writing, so anything
that goes wrong after that leaves an empty file where the state used to be. That
is the one unacceptable failure for a state library, because it destroys data
that was already safe. The temporary file is in the target's directory
deliberately: `os.replace` across filesystems fails with `EXDEV`.

**Saving still raises.** A save that cannot write is a fact you need. If
persistence is a convenience in your program rather than a requirement, catch
`OSError` and carry on — that is a decision only the caller can make, and a
library that made it for you would lose data silently.

**Atomic is not synchronised.** Two processes saving at once both write complete,
valid files and the second wins entirely. That is last-writer-wins, not
corruption; this class does not lock.

## Quickstart — `StonedogRemembers` (asynchronous)

`StonedogRemembers` processes **actions** off a queue and emits **events** onto
another queue. You dispatch `SET_STATE` actions and consume `STATE_CHANGED`
events.

```python
import asyncio
from stonedog_remembers import StonedogRemembers

async def main():
    store = StonedogRemembers("initial_state.json")
    await store.load_initial_state()      # empty state if the file is absent
    store.start_processing()              # start the background action processor

    # observe state changes
    events = store.subscribe_events()     # an asyncio.Queue of event dicts

    await store.dispatch({
        "type": StonedogRemembers.ACTION_TYPE_SET_STATE,   # "SET_STATE"
        "path": "user.theme",
        "value": "dark",
    })

    event = await events.get()
    # {'type': 'STATE_CHANGED', 'path': 'user.theme',
    #  'old_value': None, 'new_value': 'dark', 'action_source': {...}}
    print(event["path"], "->", event["new_value"])
    print(store.get_current_state())      # deep copy of the whole state

    await store.stop_processing()

asyncio.run(main())
```

### The subscribe / events model

* **`Store`** notifies **synchronously**: each `set()` that changes state calls
  every subscriber callback with a `STATE_CHANGED` event
  (`{"type", "path", "old_value", "new_value"}`). A raising subscriber is
  logged and isolated — it won't break the store or other subscribers.
* **`StonedogRemembers`** is **asynchronous**: `subscribe_events()` returns an
  `asyncio.Queue`. Each applied `SET_STATE` puts a `STATE_CHANGED` event (which
  also carries `action_source`) on that queue for your consumer coroutine to
  `await`. Actions with no `path`, unknown action types, and writes that can't
  be applied are ignored and emit no event.

## Development

This is a Poetry (PEP 621) project. Tests run under pytest with a coverage gate:

```bash
pip install pytest pytest-asyncio pytest-cov
pytest        # runs the suite and enforces >=90% line coverage
```

`pythonpath = ["src"]` is set in `pyproject.toml`, so tests import
`stonedog_remembers` directly without a manual `PYTHONPATH`.

## License

MIT

## Renamed from `roz-remembers`

This library was published as **`roz-remembers`** through 0.2.0. It is the same
library under the StoneDogCode name: the distribution is now
`stonedog-remembers`, the import is `stonedog_remembers`, and the async store
class is `StonedogRemembers`.

```python
from roz_remembers import RozRemembers            # before
from stonedog_remembers import StonedogRemembers  # now
```

`RozRemembers` remains exported as a deprecated alias — it is the *same object*,
not a subclass, so `isinstance` checks and the `ACTION_TYPE_*` / `EVENT_TYPE_*`
class attributes behave identically either way.

The old [`roz-remembers`](https://pypi.org/project/roz-remembers/) distribution
stays on PyPI so existing installs keep working, but it receives no further
releases.
