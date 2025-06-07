import asyncio
import json
import logging
from typing import Any, Dict, Optional
import copy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RozRemembers:
    """
    A generic, message-driven state management library inspired by Redux.
    It manages a central state, processes incoming actions/commands, and
    emits events whenever the state changes. External logic (sagas/listeners)
    can subscribe to these events and dispatch new actions.
    """
    ACTION_TYPE_SET_STATE = 'SET_STATE'
    EVENT_TYPE_STATE_CHANGED = 'STATE_CHANGED'

    def __init__(self, initial_state_file_path: str):
        self._initial_state_file_path = initial_state_file_path
        self._state: Dict[str, Any] = {}
        
        self._action_queue = asyncio.Queue()
        self._event_queue = asyncio.Queue()
        
        self._processing_task: Optional[asyncio.Task] = None

    async def load_initial_state(self):
        try:
            with open(self._initial_state_file_path, 'r') as f:
                self._state = json.load(f)
            logger.info(f"Initial state loaded successfully from: {self._initial_state_file_path}")
        except FileNotFoundError:
            logger.warning(f"Initial state file not found: {self._initial_state_file_path}. Starting with an empty state.")
            self._state = {}
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in initial state file: {self._initial_state_file_path}. Starting with an empty state.")
            self._state = {}
        except Exception as e:
            logger.error(f"Unexpected error loading initial state: {e}", exc_info=True)
            self._state = {}

    def start_processing(self):
        if self._processing_task is None or self._processing_task.done():
            self._processing_task = asyncio.create_task(self._action_processor())
            logger.info("RozRemembers action processor started.")
        else:
            logger.warning("RozRemembers action processor already running.")

    async def stop_processing(self):
        if self._processing_task and not self._processing_task.done():
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
            logger.info("RozRemembers action processor stopped.")

    async def _action_processor(self):
        logger.info("Action processor is running, waiting for actions...")
        while True:
            try:
                action = await self._action_queue.get()
                logger.debug(f"Processing action: {action}")
                
                new_state = self._state
                action_type = action.get('type')

                if action_type == self.ACTION_TYPE_SET_STATE:
                    path = action.get('path')
                    value = action.get('value')
                    
                    if path is None:
                        logger.warning(f"SET_STATE action missing 'path': {action}")
                        self._action_queue.task_done()
                        continue

                    old_value_at_path = self._get_nested_value(path, current_data=self._state)
                    
                    temp_state = copy.deepcopy(self._state) 
                    
                    applied_successfully = self._set_nested_value(path, value, current_data=temp_state)

                    if applied_successfully:
                        self._state = temp_state
                        
                        await self._event_queue.put({
                            'type': self.EVENT_TYPE_STATE_CHANGED,
                            'path': path,
                            'old_value': old_value_at_path,
                            'new_value': self._get_nested_value(path, current_data=self._state),
                            'action_source': action
                        })
                        logger.debug(f"State updated for path '{path}'. Emitted {self.EVENT_TYPE_STATE_CHANGED} event.")
                    else:
                        logger.warning(f"Failed to apply state change for path '{path}' with value '{value}'.")
                else:
                    logger.warning(f"Unknown action type received: {action_type}. Action: {action}")
                
                self._action_queue.task_done()

            except asyncio.CancelledError:
                logger.info("Action processor task cancelled.")
                break
            except Exception as e:
                logger.error(f"Unhandled exception in action processor: {e}", exc_info=True)
                self._action_queue.task_done()

    def _get_nested_value(self, path: str, current_data: Dict[str, Any]) -> Any:
        parts = path.split('.')
        temp_data = current_data
        for part in parts:
            if isinstance(temp_data, dict):
                temp_data = temp_data.get(part)
            elif isinstance(temp_data, list) and part.isdigit():
                idx = int(part)
                if 0 <= idx < len(temp_data):
                    temp_data = temp_data[idx]
                else:
                    return None
            else:
                return None
            if temp_data is None:
                break
        return temp_data

    def _set_nested_value(self, path: str, value: Any, current_data: Dict[str, Any]) -> bool:
        parts = path.split('.')
        temp_data = current_data
        
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                if isinstance(temp_data, dict):
                    temp_data[part] = value
                elif isinstance(temp_data, list) and part.isdigit():
                    idx = int(part)
                    if 0 <= idx < len(temp_data):
                        temp_data[idx] = value
                    else:
                        logger.warning(f"Cannot set list index out of range for path: {path}")
                        return False
                else:
                    logger.warning(f"Cannot set value on non-container at path segment: {path}")
                    return False
            else:
                if isinstance(temp_data, dict):
                    if part not in temp_data or not isinstance(temp_data[part], (dict, list)):
                        temp_data[part] = {}
                    temp_data = temp_data[part]
                elif isinstance(temp_data, list) and part.isdigit():
                    idx = int(part)
                    if 0 <= idx < len(temp_data):
                        if not isinstance(temp_data[idx], (dict, list)):
                            temp_data[idx] = {}
                        temp_data = temp_data[idx]
                    else:
                        logger.warning(f"Cannot traverse list index out of range for path: {path}")
                        return False
                else:
                    logger.warning(f"Invalid path traversal: segment '{part}' is not a container in path '{path}'")
                    return False
        return True

    async def dispatch(self, action: Dict[str, Any]):
        await self._action_queue.put(action)
        logger.debug(f"Action dispatched: {action['type']}")

    def subscribe_events(self) -> asyncio.Queue:
        return self._event_queue

    def get_current_state(self) -> Dict[str, Any]:
        return copy.deepcopy(self._state)
