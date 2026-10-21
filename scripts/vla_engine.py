"""
HELIOS — Root VLA Engine Wrapper (vla_engine.py)
Direct entrypoint to the Stateful VLA Execution Loop.
"""

import asyncio
import sys
from pathlib import Path

# Add ai-router to path
AI_ROUTER_DIR = Path(__file__).parent / "ai-router"
if str(AI_ROUTER_DIR) not in sys.path:
    sys.path.insert(0, str(AI_ROUTER_DIR))

from vla_engine import (
    ActionType,
    CapturedFrame,
    CoordinateNormalizer,
    DeadlockDetector,
    DeadlockDetectedError,
    HighSpeedFrameCapturer,
    InputDispatcher,
    LocalVLAOllamaClient,
    LoopStatus,
    NormalizedCoordinate,
    StatefulVLAExecutionLoop,
    VLAAction,
    main,
)

if __name__ == "__main__":
    asyncio.run(main())
