"""
Test Suite: HELIOS Seamless Interaction & Dyadic Conversational Dynamics
========================================================================
Validates multimodal conversational turn-taking, gaze aversion, and sibling
differentiation derived from Meta's Seamless Interaction dataset.
"""

import pytest
import time
from core.seamless_interaction import (
    SeamlessInteractionDirector,
    TurnTakingState,
    AIRI_PROFILE,
    REN_PROFILE,
)
from core.trained_body_model import TrainedBodyMovementModel
from core.character_state import VALID_ANIMATIONS


def test_sibling_profiles_differentiation():
    """Verify distinct behavioral profiles for Airi vs older brother Ren."""
    director_airi = SeamlessInteractionDirector("helios_airi")
    assert director_airi.profile.character_id == "helios_airi"
    assert director_airi.profile.nod_frequency_mult > 1.0, "Airi should have lively nodding frequency"
    assert director_airi.profile.head_tilt_max_deg > 10.0, "Airi should have expressive head tilt"

    director_ren = SeamlessInteractionDirector("helios_twin")
    assert director_ren.profile.character_id == "helios_twin"
    assert director_ren.profile.nod_frequency_mult < 1.0, "Ren should have disciplined, measured nodding"
    assert director_ren.profile.tactical_composure >= 0.9, "Ren should have high tactical composure"
    assert director_ren.profile.head_tilt_max_deg < 5.0, "Ren should maintain steady posture"


def test_seamless_turn_taking_active_listening_and_backchannel():
    """Verify attentive listening and active backchannel nod generation during user speech."""
    director = SeamlessInteractionDirector("helios_airi")
    
    # 1. User starts speaking -> listening
    directive = director.evaluate_turn_taking(event_type="user_speech", user_is_speaking=True)
    assert directive["turn_state"] in [TurnTakingState.LISTENING_ATTENTIVE.value, TurnTakingState.LISTENING_BACKCHANNEL.value]
    assert directive["animation"] in ["listening", "active_listening_nod"]
    assert directive["gaze"]["averted"] is False

    # 2. High amplitude speech after nod interval triggers active listening backchannel nod
    director.last_nod_time = time.time() - 4.0
    directive_backchannel = director.evaluate_turn_taking(
        event_type="user_speech",
        audio_amplitude=0.35,
        user_is_speaking=True,
    )
    assert directive_backchannel["turn_state"] == TurnTakingState.LISTENING_BACKCHANNEL.value
    assert directive_backchannel["animation"] == "active_listening_nod"
    assert abs(directive_backchannel["head_tilt_deg"]) <= AIRI_PROFILE.head_tilt_max_deg


def test_seamless_barge_in_interruption_detection():
    """Verify instant barge-in yielding when user interrupts while character is speaking."""
    director = SeamlessInteractionDirector("helios_airi")
    
    # System currently speaking
    director.turn_state = TurnTakingState.SPEAKING_FLOW
    
    # User abruptly starts speaking (barge-in)
    directive = director.evaluate_turn_taking(event_type="user_speech", user_is_speaking=True)
    assert directive["turn_state"] == TurnTakingState.BARGE_IN_YIELD.value
    assert directive["animation"] == "barge_in_alert"
    assert directive.get("barge_in") is True


def test_thoughtful_gaze_aversion_during_thinking():
    """Verify human gaze aversion prior during formulation/thinking phase."""
    director = SeamlessInteractionDirector("helios_twin")
    
    directive = director.evaluate_turn_taking(event_type="thinking", user_is_speaking=False)
    assert directive["turn_state"] == TurnTakingState.THINKING_AVERTED.value
    assert directive["animation"] == "thoughtful_gaze_aversion"
    assert directive["gaze"]["averted"] is True
    assert directive["gaze"]["x"] != 0.0 or directive["gaze"]["y"] != 0.0


def test_turn_yield_inquiry():
    """Verify open turn yielding and inquiry posture when handing floor to user."""
    director = SeamlessInteractionDirector("helios_airi")
    
    directive = director.evaluate_turn_taking(event_type="turn_yield", user_is_speaking=False)
    assert directive["turn_state"] == TurnTakingState.TURN_YIELDING.value
    assert directive["animation"] == "turn_yield_inquiry"


def test_trained_mlp_predicts_seamless_animations():
    """Verify the retrained 4-Head Neural MLP predicts the new dyadic animations."""
    import pickle
    from pathlib import Path
    
    weights_path = Path(__file__).resolve().parent.parent / "models" / "helios_body_movement_model.pkl"
    with open(weights_path, "rb") as f:
        bundle = pickle.load(f)
    model = TrainedBodyMovementModel(bundle)
    
    # Check predictions on conversational prompts
    pred_listening = model.predict("I have an idea for the design, listen to this", "I'm listening closely, go ahead.")
    assert pred_listening["animation"] == "active_listening_nod"
    
    pred_thinking = model.predict("How would you approach solving this complex architecture problem?", "Let me analyze that carefully and weigh the tradeoffs.")
    assert pred_thinking["animation"] == "thoughtful_gaze_aversion"
    
    pred_yield = model.predict("What are your thoughts on this direction? Do you agree?", "What do you think we should prioritize next? The floor is yours.")
    assert pred_yield["animation"] == "turn_yield_inquiry"
    
    pred_barge = model.predict("Wait stop hold on a moment", "Pausing immediately. Standing by for your instructions.")
    assert pred_barge["animation"] == "barge_in_alert"
    
    pred_tactical = model.predict("Ren, tactical briefing and status check", "All systems secure. Standing by with tactical readiness.")
    assert pred_tactical["animation"] == "tactical_composure"
