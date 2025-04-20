from typing import Literal, TypedDict, List, Dict, Any

Window = Literal["rectangular", "hann", "hamming", "blackman", "blackmanharris"]


class ADCStatus(TypedDict):
    Nbuf: int
    sample_rate: int


class CalculationStatus(TypedDict):
    Nsig: int
    Ntot: int
    window: Window
    rolling_fft: bool
    min_snr: int


class MotorStatus(TypedDict):
    freq: float


class VoltageMessage(TypedDict):
    topic: str
    payload: list[float]


class FFTMessage(TypedDict):
    topic: str
    payload: List[List[float]]
    metadata: Dict


class GenericMessage(TypedDict):
    topic: str
    payload: Any


Message = VoltageMessage | FFTMessage | GenericMessage
