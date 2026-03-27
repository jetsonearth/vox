"""Tests for vox.diarize (mocked pyannote pipeline)."""

from unittest.mock import MagicMock, patch

from vox.diarize import DiarSegment, diarize


class FakeTrack:
    def __init__(self, start: float, end: float):
        self.start = start
        self.end = end


class FakeDiarization:
    """Mimics pyannote Annotation.itertracks(yield_label=True)."""

    def __init__(self, tracks: list[tuple[float, float, str]]):
        self._tracks = tracks

    def itertracks(self, yield_label=False):
        for start, end, speaker in self._tracks:
            yield FakeTrack(start, end), None, speaker


@patch("vox.diarize._load_pipeline")
def test_diarize_basic(mock_load):
    fake_pipeline = MagicMock()
    fake_pipeline.return_value = FakeDiarization([
        (0.0, 5.0, "SPEAKER_00"),
        (5.0, 10.0, "SPEAKER_01"),
        (10.0, 15.0, "SPEAKER_00"),
    ])
    mock_load.return_value = fake_pipeline

    segments = diarize("fake.wav", {})

    assert len(segments) == 3
    assert segments[0] == DiarSegment(0.0, 5.0, "SPEAKER_00")
    assert segments[1] == DiarSegment(5.0, 10.0, "SPEAKER_01")
    assert segments[2] == DiarSegment(10.0, 15.0, "SPEAKER_00")


@patch("vox.diarize._load_pipeline")
def test_diarize_passes_num_speakers(mock_load):
    fake_pipeline = MagicMock()
    fake_pipeline.return_value = FakeDiarization([
        (0.0, 10.0, "SPEAKER_00"),
    ])
    mock_load.return_value = fake_pipeline

    diarize("fake.wav", {}, num_speakers=2)

    fake_pipeline.assert_called_once()
    call_kwargs = fake_pipeline.call_args[1]
    assert call_kwargs["num_speakers"] == 2


@patch("vox.diarize._load_pipeline")
def test_diarize_empty(mock_load):
    fake_pipeline = MagicMock()
    fake_pipeline.return_value = FakeDiarization([])
    mock_load.return_value = fake_pipeline

    segments = diarize("fake.wav", {})
    assert segments == []
