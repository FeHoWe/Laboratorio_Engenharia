"""Reprodução de áudio: usa QtMultimedia (PySide6) quando disponível; senão, sounddevice; senão, apenas arquivo WAV.

A reprodução é por empurrão (push) de blocos: cada bloco é gerado no ritmo do relógio de reprodução, e o
tempo do áudio é a referência de sincronismo com a animação do carro.
"""
from __future__ import annotations

import numpy as np


class AudioPlayer:
    """Reproduz um buffer estéreo float32 pré-renderizado (volta) ou blocos gerados sob demanda."""

    def __init__(self, sr: int = 44100):
        self.sr = sr
        self.backend = None
        self._sink = None
        self._io = None
        self._pos = 0
        self._buf = None
        self._timer = None
        self._start_pos = 0
        self.volume = 0.8
        self._inited = False

    def _init_backend(self):
        """Inicialização preguiçosa: só toca no QtMultimedia quando o áudio é realmente usado."""
        if self._inited:
            return
        self._inited = True
        import os
        if os.environ.get("NEXUS_F1_NO_AUDIO") or os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        try:
            from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices
            fmt = QAudioFormat()
            fmt.setSampleRate(self.sr); fmt.setChannelCount(2); fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            dev = QMediaDevices.defaultAudioOutput()
            if dev.isNull():
                raise RuntimeError("sem dispositivo de áudio")
            self._sink = QAudioSink(dev, fmt)
            self.backend = "qt"
        except Exception:
            try:
                import sounddevice  # noqa: F401
                self.backend = "sounddevice"
            except Exception:
                self.backend = None

    @property
    def available(self) -> bool:
        self._init_backend()
        return self.backend is not None

    def set_volume(self, v: float):
        self.volume = float(np.clip(v, 0, 1))
        if self._sink is not None:
            self._sink.setVolume(self.volume)

    def play_buffer(self, audio: np.ndarray, start_s: float = 0.0):
        """audio: (n,2) float32. Inicia no instante start_s."""
        self._init_backend()
        self.stop()
        self._buf = audio
        self._pos = int(start_s * self.sr)
        self._start_pos = self._pos
        if self.backend == "qt":
            from PySide6.QtCore import QTimer
            self._sink.setBufferSize(self.sr // 4 * 4)
            self._sink.setVolume(self.volume)
            self._io = self._sink.start()
            self._timer = QTimer()
            self._timer.setInterval(15)
            self._timer.timeout.connect(self._pump)
            self._timer.start()
        elif self.backend == "sounddevice":
            import sounddevice as sd
            sd.play(audio[self._pos:] * self.volume, self.sr)

    def _pump(self):
        if self._buf is None or self._io is None:
            return
        free = self._sink.bytesFree()
        n = min(free // 4, 4096)
        if n <= 0:
            return
        chunk = self._buf[self._pos:self._pos + n]
        if chunk.shape[0] == 0:
            self.stop()
            return
        self._pos += chunk.shape[0]
        pcm = (np.clip(chunk, -1, 1) * 32767).astype("<i2")
        self._io.write(pcm.tobytes())

    def position_s(self) -> float:
        """Relógio de áudio (aproximado): amostras já entregues menos o que ainda está no buffer."""
        if self.backend == "qt" and self._sink is not None and self._buf is not None:
            queued = (self._sink.bufferSize() - self._sink.bytesFree()) // 4
            return max(self._pos - queued, 0) / self.sr
        return self._pos / self.sr

    def stop(self):
        if self._timer is not None:
            self._timer.stop(); self._timer = None
        if self._sink is not None:
            self._sink.stop()
        if self.backend == "sounddevice":
            try:
                import sounddevice as sd
                sd.stop()
            except Exception:
                pass
        self._io = None
