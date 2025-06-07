# Define different initial state payloads
import asyncio
import copy
import json
import pytest

from src.roz_remembers import RozRemembers


INITIAL_STATES = {
    "BASIC": {
        "app_version": "1.0.0",
        "user_settings": {
            "theme": "dark",
            "notifications_enabled": True
        }
    },
    "GAMEWORLD": {
        "app_version": "1.0.0",
        "user_settings": {
            "theme": "light",
            "notifications_enabled": False
        },
        "game_state": {
            "current_time": "2025-06-06T08:00:00Z",
            "active_player_id": "player_alpha"
        },
        "players": {
            "player_alpha": {
                "username": "Alpha",
                "character_id": "char_hero"
            }
        },
        "characters": {
            "char_hero": {
                "name": "Hero",
                "health": 100,
                "current_room_id": "room_start"
            }
        },
        "rooms": {
            "room_start": {
                "name": "Starting Area",
                "description": "A quiet beginning.",
                "exits": {"north": "room_forest"}
            }
        }
    }
}

@pytest.mark.asyncio
async def test_basic_state(tmp_path):
    """
    Tests the basic lifecycle of RozRemembers using the "BASIC" initial state.
    """
    # Create a temporary JSON file for this specific test
    initial_state_file = tmp_path / "basic_state.json"
    with open(initial_state_file, 'w') as f:
        json.dump(INITIAL_STATES["BASIC"], f, indent=2)

    # Initialize and load state
    store = RozRemembers(initial_state_file_path=str(initial_state_file))
    await store.load_initial_state()
    store.start_processing()

    # Assert initial state
    expected_initial_state = INITIAL_STATES["BASIC"]
    assert store.get_current_state() == expected_initial_state

    # Dispatch an action
    await store.dispatch({
        "type": store.ACTION_TYPE_SET_STATE,
        "path": "user_settings.theme",
        "value": "light"
    })
    await asyncio.sleep(0.05) # Give the processor a moment

    # Assert updated state
    updated_state = store.get_current_state()
    expected_updated_state = copy.deepcopy(INITIAL_STATES["BASIC"])
    expected_updated_state["user_settings"]["theme"] = "light"
    assert updated_state == expected_updated_state
    assert updated_state["user_settings"]["theme"] == "light"

    # Stop processing
    await store.stop_processing()
    print(f"\nTest 'test_basic_lifecycle' completed. Final state:\n{json.dumps(store.get_current_state(), indent=2)}")


@pytest.mark.asyncio
async def test_complex_state(tmp_path):
    """
    Tests a lifecycle of RozRemembers using the "GAMEWORLD" initial state.
    """
    # Create a temporary JSON file for this specific test
    initial_state_file = tmp_path / "gameworld_state.json"
    with open(initial_state_file, 'w') as f:
        json.dump(INITIAL_STATES["GAMEWORLD"], f, indent=2)

    # Initialize and load state
    store = RozRemembers(initial_state_file_path=str(initial_state_file))
    await store.load_initial_state()
    store.start_processing()

    # Assert initial state
    expected_initial_state = INITIAL_STATES["GAMEWORLD"]
    assert store.get_current_state() == expected_initial_state
    assert store.get_current_state()["game_state"]["active_player_id"] == "player_alpha"

    # Dispatch an action to move the character
    await store.dispatch({
        "type": store.ACTION_TYPE_SET_STATE,
        "path": "characters.char_hero.current_room_id",
        "value": "room_forest"
    })
    await asyncio.sleep(0.05)

    # Dispatch an action to change player's username
    await store.dispatch({
        "type": store.ACTION_TYPE_SET_STATE,
        "path": "players.player_alpha.username",
        "value": "Nehsamud"
    })
    await asyncio.sleep(0.05)

    # Assert updated state
    updated_state = store.get_current_state()
    assert updated_state["characters"]["char_hero"]["current_room_id"] == "room_forest"
    assert updated_state["players"]["player_alpha"]["username"] == "Nehsamud"

    # Stop processing
    await store.stop_processing()
    print(f"\nTest 'test_gameworld_lifecycle' completed. Final state:\n{json.dumps(store.get_current_state(), indent=2)}")

# To run these tests:
# 1. Save the above code as a Python file, e.g., `test_rozremembers.py`.
# 2. Make sure you have pytest installed: `pip install pytest pytest-asyncio`
# 3. Run pytest from your terminal in the same directory: `pytest -s -v`
#    (-s to see print statements, -v for verbose output)

