"""engine_audio — módulo independente de áudio dinâmico do motor (síntese procedural)."""
from .synth import PROFILES, EngineProfile, get_profile, write_wav
from .realtime import RealtimeEngineSynth
from .session import AudioSettings, SimulationAudio

__all__ = ["PROFILES", "EngineProfile", "get_profile", "write_wav", "RealtimeEngineSynth",
           "AudioSettings", "SimulationAudio"]
